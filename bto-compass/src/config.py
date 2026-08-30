import os
from dotenv import load_dotenv

load_dotenv()

DATA_PATH_CSV = "data/bto_flat_offerings_feb2026.csv"
DATA_PATH_JSON = "data/application_rates/application_rates_feb2026.json"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

WEIGHTS = {
    "affordability": 0.30,
    "location": 0.25,
    "demand": 0.20,
    "wait": 0.15,
    "lifestyle": 0.10
}
