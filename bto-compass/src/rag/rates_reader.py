# src/rag/rates_reader.py
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
JSON_FILE = BASE_DIR / "data" / "application_rates.json"

def get_application_rates_context() -> str:
    if not JSON_FILE.exists():
        return "No application rates data available."
    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("full_page_content", "")
    except Exception as e:
        return f"Error reading application rates file: {e}"
