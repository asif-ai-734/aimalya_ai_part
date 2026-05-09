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

## Endpoints

- `GET /dashboard/overview`
- `GET /reviews/analysis`
- `GET /insights/recommendations`
- `GET /reports/monthly`
- `POST /businesses/fetch`
- `GET /businesses?user_id=user_123`
- `GET /businesses/user/user_123`
- `GET /businesses/management?user_id=user_123`
- `GET /businesses/management/user_123`

Example business setup request:

```json
{
  "user_id": "user_123",
  "businesses": [
    {
      "name": "XYZ Food Corner",
      "category": "restaurant",
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
