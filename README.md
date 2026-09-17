# LeadAtlas Sample — FastAPI Backend Module

This repository contains a clean, modular code sample extracted from my SaaS project **LeadAtlas.io**.  
It demonstrates how I design production-ready backend services using **FastAPI**, **async pipelines**,  
**Google Places API integration**, **data cleaning**, **deduplication**, **pagination**, and **CSV export**.

---

## 🚀 Features Demonstrated

### 🔹 Google Places API Integration
- Text search (`searchText`)
- Place details (phone, website)
- Async bulk queries using `httpx.AsyncClient`

### 🔹 Data Processing & Cleaning
- Unicode normalization
- Address/name cleaning
- Custom deduplication logic based on normalized keys

### 🔹 Database Operations
- SQLAlchemy ORM models
- CRUD endpoints
- Bulk insert with dedupe
- Database-level dedupe endpoint

### 🔹 Credits System (SaaS Logic)
- User authentication
- Credit consumption per search
- Stripe-ready architecture (not included in this sample)

### 🔹 CSV Export
- UTF‑8 safe CSV generation
- Clean formatting for external tools

### 🔹 Pagination
- Simple and efficient paginated endpoint

---

## 📁 Structure

