import os
import sys
from dotenv import load_dotenv
from groq import Groq

def validate_groq_key():
    print("\n  --- Groq API Key Network Validation ---\n")
    
    # 1. Load the environment variables
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    
    # 2. Perform syntax checks (like the script you pasted)
    if not api_key:
        print("  [FAIL] GROQ_API_KEY is missing from the .env file.")
        sys.exit(1)
        
    if not api_key.startswith("gsk_"):
        print(f"  [FAIL] Key looks invalid. It starts with '{api_key[:4]}', expected 'gsk_'.")
        print("         Did you paste it with quotes around it by mistake?")
        sys.exit(1)
        
    print(f"  [ ok ] Key syntax is correct (starts with {api_key[:7]}...)")
    
    # 3. Perform the live network authorization test
    print("  [....] Pinging Groq servers to verify authorization...")
    try:
        client = Groq()
        # Fetching the available models is the fastest, cheapest way to prove the key is valid
        client.models.list()
        print("  [ ok ] Network test passed! Your key is valid and authorized.\n")
    except Exception as e:
        print(f"  [FAIL] The server rejected your key.")
        print(f"         Error details: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    validate_groq_key()
