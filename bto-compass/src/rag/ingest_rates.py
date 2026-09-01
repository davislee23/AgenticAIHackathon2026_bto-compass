# src/rag/ingest_rates.py
import os
import sys
import json
import re
import requests
from pathlib import Path
from datetime import datetime

# Add project root directory to Python import path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import streamlit as st

URL_FILE = BASE_DIR / "data" / "rates_url.txt"
JSON_FILE = BASE_DIR / "data" / "application_rates.json"

def clean_url_string(raw_url: str) -> str:
    """Strips Markdown link syntax, brackets, and quotes from a URL string."""
    md_match = re.search(r'https?://[^\s\)]+', raw_url)
    if md_match:
        return md_match.group(0).rstrip(']')
    return raw_url.strip(" []()'\"")

def get_firecrawl_api_key() -> str:
    """Retrieves Firecrawl API key from environment variables or Streamlit secrets."""
    key = os.getenv("FIRECRAWL_API_KEY")
    if not key and hasattr(st, "secrets") and "FIRECRAWL_API_KEY" in st.secrets:
        key = st.secrets["FIRECRAWL_API_KEY"]
    return key

def ingest_full_page():
    api_key = get_firecrawl_api_key()
    if not api_key:
        print("❌ Error: FIRECRAWL_API_KEY is missing. Add it to .env or Streamlit secrets.")
        return

    if not URL_FILE.exists():
        print(f"❌ Error: {URL_FILE} not found.")
        return

    with open(URL_FILE, "r", encoding="utf-8") as f:
        raw_input = f.read().strip()

    url = clean_url_string(raw_input)
    print(f"🌍 Target URL: {url}")

    endpoint = "https://api.firecrawl.dev/v1/scrape"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "url": url,
        "formats": ["markdown"]
    }

    print("🔥 Scraping entire webpage via Firecrawl...")
    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()

        if data.get("success") and "data" in data:
            page_data = data["data"]
            markdown_content = page_data.get("markdown", "")
            
            # Store everything verbatim in JSON
            output_payload = {
                "source_url": url,
                "scraped_at": datetime.now().isoformat(),
                "total_characters": len(markdown_content),
                "metadata": page_data.get("metadata", {}),
                "full_page_content": markdown_content
            }

            with open(JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(output_payload, f, indent=4, ensure_ascii=False)

            print(f"✅ Success! Saved all {len(markdown_content)} characters directly to {JSON_FILE.name}")
        else:
            print(f"❌ Firecrawl API returned unsuccessful response: {data}")

    except Exception as e:
        print(f"❌ Scrape failed: {e}")

if __name__ == "__main__":
    ingest_full_page()
