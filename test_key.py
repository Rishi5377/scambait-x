import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

print(f"🔑 Checking GEMINI_API_KEY: {api_key[:10]}... (Total len: {len(api_key) if api_key else 0})")

if not api_key:
    print("❌ Key NOT found in .env")
    exit(1)

genai.configure(api_key=api_key)

models_to_test = ["gemini-1.5-flash", "gemini-pro"]

print("\n📜 Listing Available Models for this Key:")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"   - {m.name}")
except Exception as e:
    print(f"❌ Could not list models: {e}")
