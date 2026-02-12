
import os
import sys
import json
import asyncio
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

async def check_user_full_details(email):
    print(f"\nChecking ALL details for user: {email}")
    try:
        # 1. User Info
        res = supabase.table("users").select("*").eq("email", email).execute()
        if not res.data:
            print("No users found with this email.")
            return
            
        user = res.data[0]
        user_id = user.get('id')
        print(f"User ID: {user_id}, Role: {user.get('role')}")

        # 2. Application Form
        res_form = supabase.table("application_forms").select("*").eq("user_id", user_id).execute()
        if res_form.data:
            form = res_form.data[0]
            print(f"Application Form found: ID={form.get('id')}, Status={form.get('status')}")
        else:
            print("Application Form NOT found for this user.")

        # 3. Analytics Sim
        # Get bookings
        res_bookings = supabase.table("interview_bookings").select("token").eq("user_id", user_id).execute()
        tokens = [b["token"] for b in res_bookings.data if b.get("token")]
        print(f"Tokens found: {len(tokens)}")
        
        if tokens:
            res_evals = supabase.table("evaluations").select("*").in_("booking_token", tokens).execute()
            print(f"Evaluations found: {len(res_evals.data)}")
            for ev in res_evals.data:
                print(f"  - Eval ID: {ev.get('id')}, Score: {ev.get('overall_score')}, Analysis Exists: {ev.get('overall_analysis') is not None}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_user_full_details("pranathi@codegnan.com"))
