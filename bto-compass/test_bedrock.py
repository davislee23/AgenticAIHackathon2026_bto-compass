import os
from dotenv import load_dotenv

# Load variables from .env
load_dotenv()

from src.llm import get_llm

def test_connection():
    try:
        print("Initializing Bedrock LLM...")
        llm = get_llm()
        
        print("Sending test prompt to AWS Bedrock...")
        response = llm.invoke("Hello! Respond in one short sentence confirming Bedrock is active.")
        
        print("\n--- Success! ---")
        print("Response:", response.content)
    except Exception as e:
        print("\n--- Connection Failed ---")
        print("Error details:", str(e))

if __name__ == "__main__":
    test_connection()
