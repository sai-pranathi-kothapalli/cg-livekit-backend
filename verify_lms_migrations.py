import asyncio
import os
import json
import hashlib
import secrets
from dotenv import load_dotenv

# Load env
load_dotenv('.env')

# We can import existing db connection if possible, but let's do it directly with supabase package to avoid app dependency issues
from supabase import create_client, Client

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(url, key)

result = {
    "api_key": {},
    "verification": {}
}

# 1. Generate and insert API key
try:
    pt_key = f"cgn_live_lms_{secrets.token_hex(24)}"
    hashed = hashlib.sha256(pt_key.encode()).hexdigest()
    
    # insert
    res = supabase.table("api_keys").insert({
        "name": "Codegnan LMS",
        "description": "Production LMS integration key",
        "hashed_key": hashed,
        "permissions": ["integration"]
    }).execute()
    
    result["api_key"] = {
        "plain_key": pt_key,
        "hashed_key": hashed,
        "inserted": True,
        "id": res.data[0]["id"] if res.data else None
    }
except Exception as e:
    result["api_key"] = {"error": str(e)}

# 2. Verify schema (we do this by trying to select the new columns)
def check_columns(table, columns):
    try:
        supabase.table(table).select(",".join(columns)).limit(1).execute()
        return True, "Found"
    except Exception as e:
        return False, str(e)


enrolled_cols = ["id", "external_student_id", "batch", "location"]
slots_cols = ["id", "slot_datetime", "batch", "location", "curriculum_topics"]
bookings_cols = ["id", "token", "batch"]

result["verification"]["enrolled_users"] = check_columns("enrolled_users", enrolled_cols)
result["verification"]["slots"] = check_columns("slots", slots_cols)
result["verification"]["interview_bookings"] = check_columns("interview_bookings", bookings_cols)

# check new tables
result["verification"]["webhooks_registry"] = check_columns("webhooks_registry", ["id", "name", "target_url"])
result["verification"]["webhook_delivery_log"] = check_columns("webhook_delivery_log", ["id", "webhook_id", "event"])

with open("verification_results.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2)

print("Done. Results saved to verification_results.json")
