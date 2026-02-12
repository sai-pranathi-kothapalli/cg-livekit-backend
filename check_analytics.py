import os
import sys
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv("/Users/codegnan4/Desktop/livekit for codegnan/backend/.env")

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")

if not url or not key:
    print("Error: SUPABASE_URL or SUPABASE_SERVICE_KEY not found in .env")
    sys.exit(1)

supabase = create_client(url, key)

email = "pranathi@codegnan.com"

# Get user
res_user = supabase.table("users").select("*").eq("email", email).execute()
if not res_user.data:
    print("No user found")
    sys.exit(1)

user = res_user.data[0]
user_id = user.get('id')

# Get bookings
res_bookings = supabase.table("interview_bookings").select("token").eq("user_id", user_id).execute()
tokens = [b["token"] for b in res_bookings.data if b.get("token")]

print(f"Found {len(tokens)} booking tokens")

# Get evaluations
if tokens:
    res_evals = supabase.table("evaluations").select("*").in_("booking_token", tokens).execute()
    valid_evals = [e for e in res_evals.data if e.get("overall_score") is not None]
    
    print(f"\nTotal evaluations: {len(res_evals.data)}")
    print(f"Valid evaluations (with scores): {len(valid_evals)}")
    
    if valid_evals:
        print("\nValid evaluation details:")
        for ev in valid_evals:
            print(f"  - Score: {ev.get('overall_score')}, Created: {ev.get('created_at')}")
            print(f"    Strengths: {ev.get('strengths')}")
            print(f"    Improvements: {ev.get('areas_for_improvement')}")
