import requests
import json
import time

# Provide your newly generated Webhook.site URL over here:
WEBHOOK_URL = "https://webhook.site/44e16c68-1f84-4e9c-88e7-26d87ca3a60c"
API_KEY = "cgn_live_lms_42c924d77ff184e6bd6ad649c7a8b6ad3c17b26d738d2e75"
BASE_URL = "http://localhost:8000/api/integration"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

def run_tests():
    print("=== LAYER 5 WEBHOOK & INTEGRATION TEST ===")
    
    # 1. Register Webhook
    print(f"\n1. Registering Webhook Endpoint: {WEBHOOK_URL}")
    payload = {
        "target_url": WEBHOOK_URL,
        "events": ["EVALUATION_COMPLETED"],
        "secret": "lms_secret_signing_key_777",
        # "batch_filter": "PFS-106" # Opt filter
    }
    r = requests.post(f"{BASE_URL}/register-webhook", headers=headers, json=payload)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.json()}")

    print("\n[!] The webhook is now registered in the LMS Integration layer.")
    print("    You can trigger this by completing an interview for any created LMS slot!")
    print("    If you want to view the delivery logs immediately after a test interview, check Supabase -> webhook_delivery_log.")
    print("    Also check Supabase -> slots and ensure curriculum_topics is stored correctly so prompt injection runs.")

if __name__ == "__main__":
    if "YOUR_UUID_HERE" in WEBHOOK_URL:
        print("[!] Quick Setup: Please paste your webhook.site URL into the WEBHOOK_URL string in test_layer5.py before running.")
    else:
        run_tests()
