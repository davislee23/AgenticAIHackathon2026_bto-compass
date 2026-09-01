import os
from dotenv import load_dotenv
from pathlib import Path
import streamlit as st
from langchain_core.language_models import BaseChatModel

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH_CSV = BASE_DIR / "data" / "bto_flat_offerings_feb2026.csv"
DATA_PATH_JSON = BASE_DIR / "data" / "application_rates.json"
DATA_PATH_JSON = BASE_DIR / "data" / "application_rates_feb2026.json"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

WEIGHTS = {
    "affordability": 0.30,
    "location": 0.25,
    "demand": 0.20,
    "wait": 0.15,
    "lifestyle": 0.10
}

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")  # "groq" or "bedrock"

# Extract API key from OS environment or Streamlit Secrets
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY and hasattr(st, "secrets"):
    GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")

GROQ_MODEL = os.getenv("GROQ_MODEL") or (
    st.secrets.get("GROQ_MODEL") if hasattr(st, "secrets") else "llama-3.3-70b-versatile"
)

def get_llm() -> BaseChatModel:
    """Returns the LLM based on the configured environment provider."""
    if LLM_PROVIDER.lower() == "bedrock":
        from langchain_aws import ChatBedrock
        return ChatBedrock(
            model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
            model_kwargs={"temperature": 0.2}
        )
    else:
        from langchain_groq import ChatGroq
        return ChatGroq(
            model_name=GROQ_MODEL,  # Uses the variable
            temperature=0.0
        )
