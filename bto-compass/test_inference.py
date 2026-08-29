import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq()
model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

print("Sending a real inference request to Groq...")
response = client.chat.completions.create(
    model=model_name,
    messages=[{"role": "user", "content": "Write a 5-word sentence."}],
    max_tokens=10
)
print("Response:", response.choices[0].message.content)

