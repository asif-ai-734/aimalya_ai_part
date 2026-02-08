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
```

Run:

```powershell
uvicorn app.main:app --reload
```

## Data

- Source JSON: `app/db/demo.json`
- SQLite DB (cache + place data): `app/db/cache.sqlite3`

## Endpoints

- `GET /dashboard/overview`
- `GET /reviews/analysis`
- `GET /insights/recommendations`
- `GET /reports/monthly`
