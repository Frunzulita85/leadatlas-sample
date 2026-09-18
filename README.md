# LeadAtlas Sample — FastAPI Backend Module

This repository contains a modular backend component extracted from **LeadAtlas.io**.  
It demonstrates production-ready API patterns using **FastAPI**, **async pipelines**,  
**Google Places API integration**, **in-memory & DB deduplication**, **credit tracking**, and **data export**.

---

## 🚀 Key Features

### 🔹 Google Places API (New V1) Integration
- **Text Search & Details:** Integrates Places API V1 with custom `X-Goog-FieldMask` headers to fetch place IDs, display names, ratings, phone numbers, and websites.
- **Async Bulk Fetching:** Uses `httpx.AsyncClient` and `asyncio.gather` for concurrent multi-query execution and details extraction.

### 🔹 Data Processing & Normalization
- **Unicode Normalization:** Diacritics removal and string standardization (`NFD` decomposition).
- **In-Memory Deduplication:** Fast key-based deduplication (`normalized_name-normalized_address`) before persisting to DB.

### 🔹 Database & CRUD (SQLAlchemy)
- **ORM Persistence:** Clean separation using SQLAlchemy models and Pydantic schemas.
- **Database Deduplication:** Dedicated `/leads/dedupe` endpoint to clean up historical duplicate entries directly in PostgreSQL/SQLite.
- **Paginated Queries:** Simple limit/offset pagination endpoint.

### 🔹 SaaS Usage & Credit Tracking
- **Auth Dependency:** Route protection using custom `get_current_user` dependency.
- **Per-Lead Credit Consumption:** Automatically decrements user credits dynamically based on the number of extracted unique leads.

### 🔹 Data Export
- **UTF-8-SIG CSV Streaming:** Generates Excel-friendly CSV exports (`delimiter=";"`) via `fastapi.responses.StreamingResponse`.


