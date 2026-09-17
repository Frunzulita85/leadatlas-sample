import os
import re
import csv
import asyncio
import unicodedata
from typing import List

import httpx
import requests
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database.database import get_db
from ..models.lead import LeadModel
from ..schemas.lead import LeadQuery, BulkQuery
from .auth import get_current_user
from ..db.user_repository import decrement_credits, get_credits

# ─────────────────────────────
# Config
# ─────────────────────────────

env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(env_path)

GOOGLE_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
router = APIRouter(prefix="/leads", tags=["Leads"])

PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
PLACES_DETAILS_URL = "https://places.googleapis.com/v1/places/"

# searchText: luăm id + nume + adresă + rating + nr. review-uri
PLACES_HEADERS = {
    "Content-Type": "application/json",
    "X-Goog-Api-Key": GOOGLE_API_KEY,
    "X-Goog-FieldMask": (
        "places.id,"
        "places.displayName,"
        "places.formattedAddress,"
        "places.rating,"
        "places.userRatingCount"
    ),
}

# ─────────────────────────────
# Helpers
# ─────────────────────────────

def clean_text(value: str) -> str:
    if not value:
        return ""
    value = value.replace("\n", " ").replace("|", " ")
    return " ".join(value.split())


def normalize(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def dedupe_leads(leads: List[dict]) -> List[dict]:
    unique = {}
    for lead in leads:
        key = f"{normalize(lead.get('name', ''))}-{normalize(lead.get('address', ''))}"
        if key not in unique:
            unique[key] = lead
    return list(unique.values())

# ─────────────────────────────
# Schemas
# ─────────────────────────────

class LeadCreate(BaseModel):
    name: str
    address: str
    phone: str
    web: str
    rating: float | None = None
    total_ratings: int | None = None


class BulkLeadCreate(BaseModel):
    leads: List[LeadCreate]


class Lead(BaseModel):
    name: str
    address: str
    phone: str
    web: str | None = None
    rating: float | None = None
    total_ratings: int | None = None

# ─────────────────────────────
# CRUD
# ─────────────────────────────

@router.post("")
def create_lead(lead: Lead, db: Session = Depends(get_db)):
    new_lead = LeadModel(
        name=clean_text(lead.name),
        address=clean_text(lead.address),
        phone=lead.phone,
        web=lead.web,
        rating=lead.rating,
        total_ratings=lead.total_ratings,
    )
    db.add(new_lead)
    db.commit()
    db.refresh(new_lead)
    return {"status": "success", "lead": new_lead}


@router.get("")
def get_leads(db: Session = Depends(get_db)):
    return db.query(LeadModel).all()

# ─────────────────────────────
# Place Details (single)
# ─────────────────────────────

@router.get("/details")
def get_place_details(place_id: str):
    url = f"{PLACES_DETAILS_URL}{place_id}"

    headers = {
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": (
            "nationalPhoneNumber,"
            "internationalPhoneNumber,"
            "websiteUri"
        ),
    }

    r = requests.get(url, headers=headers)

    if r.status_code != 200:
        return {"status_code": r.status_code, "error": r.text}

    data = r.json()

    return {
        "phone": data.get("nationalPhoneNumber") or "-",
        "international_phone": data.get("internationalPhoneNumber") or "-",
        "website": data.get("websiteUri") or "-",
    }

# ─────────────────────────────
# Place Details (helper for bulk)
# ─────────────────────────────

async def fetch_details(client: httpx.AsyncClient, place_id: str) -> dict:
    url = f"{PLACES_DETAILS_URL}{place_id}"
    headers = {
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": (
            "nationalPhoneNumber,"
            "websiteUri"
        ),
    }
    try:
        r = await client.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return {"phone": "-", "web": "-"}
        data = r.json()
        return {
            "phone": data.get("nationalPhoneNumber") or "-",
            "web": data.get("websiteUri") or "-",
        }
    except Exception:
        return {"phone": "-", "web": "-"}

# ─────────────────────────────
# Search (single)
# ─────────────────────────────

@router.post("/search")
def search_leads(
    payload: LeadQuery,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = user["id"]
    user_credits = get_credits(db, user_id)

    body = {"textQuery": payload.query, "languageCode": "ro"}
    response = requests.post(PLACES_SEARCH_URL, headers=PLACES_HEADERS, json=body)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=response.text)

    data = response.json()
    places = data.get("places", [])
    leads_to_save: List[dict] = []

    for p in places:
        place_id = p.get("id")
        details = get_place_details(place_id) if place_id else {
            "phone": "-",
            "website": "-",
        }

        leads_to_save.append(
            {
                "name": clean_text(p.get("displayName", {}).get("text")),
                "address": clean_text(p.get("formattedAddress")),
                "phone": details.get("phone") or "-",
                "web": details.get("website") or "-",
                "rating": p.get("rating"),
                "total_ratings": p.get("userRatingCount"),
                "place_id": place_id,
            }
        )

    unique_leads = dedupe_leads(leads_to_save)

    for lead in unique_leads:
        db.add(LeadModel(**lead))
    db.commit()

    if user_credits > 0:
        decrement_credits(db, user_id, len(unique_leads))

    new_credits = get_credits(db, user_id)

    return {
        "status": "ok",
        "found": len(unique_leads),
        "results": unique_leads,
        "credits_left": new_credits,
    }

# ─────────────────────────────
# Bulk Search (advanced)
# ─────────────────────────────

async def fetch_query(client: httpx.AsyncClient, query: str) -> dict:
    body = {"textQuery": query, "languageCode": "en"}
    try:
        r = await client.post(
            PLACES_SEARCH_URL, headers=PLACES_HEADERS, json=body, timeout=10
        )
        if r.status_code != 200:
            return {"places": []}
        return r.json()
    except Exception:
        return {"places": []}


@router.post("/search/bulk-advanced")
async def bulk_search_advanced(
    payload: BulkQuery,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = user["id"]
    user_credits = get_credits(db, user_id)

    queries = payload.queries

    async with httpx.AsyncClient() as client:
        responses = await asyncio.gather(
            *[fetch_query(client, q) for q in queries]
        )

        all_places_raw: List[dict] = []

        for data in responses:
            for p in data.get("places", []):
                all_places_raw.append(
                    {
                        "name": clean_text(p.get("displayName", {}).get("text")),
                        "address": clean_text(p.get("formattedAddress")),
                        "rating": p.get("rating"),
                        "total_ratings": p.get("userRatingCount"),
                        "place_id": p.get("id"),
                    }
                )

        unique_places = dedupe_leads(all_places_raw)

        details_results = await asyncio.gather(
            *[
                fetch_details(client, lead["place_id"])
                for lead in unique_places
                if lead.get("place_id")
            ]
        )

    detailed_leads: List[dict] = []
    idx = 0
    for lead in unique_places:
        if lead.get("place_id"):
            det = details_results[idx]
            idx += 1
            lead["phone"] = det["phone"]
            lead["web"] = det["web"]
        else:
            lead["phone"] = "-"
            lead["web"] = "-"
        detailed_leads.append(lead)

    for lead in detailed_leads:
        exists = (
            db.query(LeadModel)
            .filter(
                LeadModel.name == lead["name"],
                LeadModel.address == lead["address"],
            )
            .first()
        )
        if not exists:
            db.add(LeadModel(**lead))

    db.commit()

    if user_credits > 0:
        decrement_credits(db, user_id, len(detailed_leads))

    new_credits = get_credits(db, user_id)

    return {
        "status": "ok",
        "queries": len(queries),
        "found": len(detailed_leads),
        "results": detailed_leads,
        "credits_left": new_credits,
    }

# ─────────────────────────────
# Export CSV
# ─────────────────────────────

@router.get("/export_csv")
def export_csv(db: Session = Depends(get_db)):
    leads = db.query(LeadModel).all()
    filename = "bulk_results.csv"

    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["nr", "name", "address", "rating", "user_ratings_total"],
            delimiter=";",
            quotechar='"',
            quoting=csv.QUOTE_ALL,
            lineterminator="\n",
        )

        writer.writeheader()

        for i, lead in enumerate(leads, start=1):
            writer.writerow(
                {
                    "nr": i,
                    "name": clean_text(lead.name),
                    "address": clean_text(lead.address),
                    "rating": lead.rating or "",
                    "user_ratings_total": lead.total_ratings or "",
                }
            )

    return StreamingResponse(
        open(filename, "rb"),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

# ─────────────────────────────
# Pagination
# ─────────────────────────────

@router.get("/paginated")
def get_paginated_leads(
    page: int = 1,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    offset = (page - 1) * limit
    leads = db.query(LeadModel).offset(offset).limit(limit).all()
    total = db.query(LeadModel).count()

    return {
        "page": page,
        "limit": limit,
        "total": total,
        "results": leads,
    }

# ─────────────────────────────
# Dedupe DB
# ─────────────────────────────

@router.delete("/dedupe")
def dedupe_database(db: Session = Depends(get_db)):
    leads = db.query(LeadModel).all()
    seen = {}
    duplicates = []

    for lead in leads:
        key = f"{normalize(lead.name)}-{normalize(lead.address)}"
        if key in seen:
            duplicates.append(lead.id)
        else:
            seen[key] = lead.id

    if duplicates:
        db.query(LeadModel).filter(
            LeadModel.id.in_(duplicates)
        ).delete(synchronize_session=False)
        db.commit()

    return {
        "status": "success",
        "removed": len(duplicates),
        "remaining": len(seen),
    }
