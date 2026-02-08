#app.services.place_loader.py
import json
from pathlib import Path
from app.db.place_store import upsert_place_data, get_place_data


DATA_PATH = Path("app/db/demo.json")

async def load_place_data():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        place = json.load(f)["result"]

    # Upsert on every load so only new data is added.
    await upsert_place_data(place)

    cached = await get_place_data(place.get("place_id"))
    return cached or place
