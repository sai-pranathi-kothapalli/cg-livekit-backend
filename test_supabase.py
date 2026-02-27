import os
import httpx
from dotenv import load_dotenv

load_dotenv("c:/Users/kiran/Desktop/cg livekit/backend/.env")

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")

print(f"URL: {url}")
print(f"Key preview: {key[:10]}...")

try:
    with httpx.Client(timeout=10.0, verify=False) as client:
        print("Sending request to Supabase (verify=False)...")
        resp = client.get(f"{url}/rest/v1/", headers={"apikey": key})
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text[:100]}")
except Exception as e:
    print(f"Error: {e}")
