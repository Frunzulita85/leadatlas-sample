import stripe
import os
from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from backend.api.database.database import get_db
from backend.api.db.user_repository import increment_credits
from fastapi import Response

router = APIRouter(prefix="/stripe")

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig, os.getenv("STRIPE_WEBHOOK_SECRET")
        )
    except Exception:
        return {"status": "invalid"}

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        # Metadata trimisă din create-checkout-session
        user_id = session["metadata"]["userId"]
        price_id = session["metadata"]["priceId"]

        # Mapare corectă pe PRICE ID (din prices.csv)
        credits_map = {
            "price_1TYLHDGxhy4IvzTDYzAXF5L3": 200,   # 200 credits
            "price_1TYLFpGxhy4IvzTD4V10dU7C": 500,   # 500 credits
            "price_1TYLIrGxhy4IvzTDv7xe1efi": 2000,  # 2000 credits
        }

        credits = credits_map.get(price_id)

        if credits:
            increment_credits(db, user_id, credits)

    return Response(status_code=200)

