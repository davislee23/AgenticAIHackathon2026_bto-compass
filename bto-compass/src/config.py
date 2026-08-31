import os
from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel

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

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")  # "groq" or "bedrock"

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
            temperature=0.2
        )
