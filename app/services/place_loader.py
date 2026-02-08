#app.services.place_loader.py
import json
from pathlib import Path 


DATA_PATH= Path("app/db/demo.json")

def load_place_data():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["result"]