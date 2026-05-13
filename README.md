# ReviewIQ

Minimal FastAPI backend for review analytics with LLM caching and SQLite data store.

## Quick Start

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

```

Create `.env`:

```
GEMINI_API_KEY=your_key
GEMINI_MODEL=your_model
DB_PATH=app/db/cache.sqlite3
```

Run:

```powershell
uvicorn app.main:app --reload
```

## Data
...
- Source JSON: `app/db/demo.json`
- SQLite DB (LLM cache + persistent app data): `app/db/cache.sqlite3`
- Docker Compose stores production data in a named volume at `/data/reviewiq.sqlite3`
- Saved businesses are user-scoped through `user_id`

For production Docker runs, keep `DB_PATH=/data/reviewiq.sqlite3` and keep the
`reviewiq_data` named volume mounted at `/data`. A normal `docker compose down`
keeps named volumes, but `docker compose down -v` removes them and deletes the
SQLite database. This repo's compose file is named `dockercompose.yml`, so run it
with `docker compose -f dockercompose.yml up -d` or rename it to a standard
Compose filename such as `docker-compose.yml`.

## Endpoints

- `GET /dashboard/overview`
- `GET /reviews/analysis`
- `GET /insights/recommendations`
- `GET /reports/monthly`
- `POST /businesses/fetch`
- `GET /businesses?user_id=user_123`
- `GET /businesses/user/user_123`
- `GET /businesses/management`
- `GET /businesses/management/detail?business_name=XYZ%20Food%20Corner&overlook=overview`

Example business setup request:

`phone_no` and `website` are optional fields on each business entry.

```json
{
  "user_id": "user_123",
  "businesses": [
    {
      "name": "XYZ Food Corner",
      "category": "restaurant",
      "phone_no": "+8801712345678",
      "website": "https://xyzfood.example.com",
      "locations": [
        {
          "google_maps_url": "https://maps.google.com/...",
          "address_or_city": "Uttara, Dhaka"
        }
      ]
    }
  ]
}
```
