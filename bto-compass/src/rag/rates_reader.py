# src/rag/rates_reader.py
import json
from pathlib import Path

# Dynamically locate project root (folder containing app.py)
current_dir = Path(__file__).resolve().parent
project_root = current_dir
while project_root != project_root.parent:
    if (project_root / "app.py").exists():
        break
    project_root = project_root.parent

JSON_FILE = project_root / "data" / "application_rates.json"

def get_application_rates_context() -> str:
    """Reads scraped HDB application rates with reliable path resolution."""
    if not JSON_FILE.exists():
        return "Data unavailable in live feed."
    
    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        if isinstance(data, dict):
            content = (
                data.get("full_page_content") or 
                data.get("markdown") or 
                data.get("content")
            )
            if content:
                return str(content)
            return json.dumps(data, indent=2)

        if isinstance(data, list):
            return json.dumps(data, indent=2)

        return str(data)

    except Exception as e:
        return f"Error reading application rates file: {e}"
