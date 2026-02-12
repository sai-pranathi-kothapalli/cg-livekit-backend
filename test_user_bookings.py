import os
import sys
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv("/Users/codegnan4/Desktop/livekit for codegnan/backend/.env")

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")

supabase = create_client(url, key)

email = "pranathi@codegnan.com"

# Get user
res_user = supabase.table("users").select("*").eq("email", email).execute()
if not res_user.data:
    print("No user found")
    sys.exit(1)

user = res_user.data[0]
user_id = user.get('id')

print(f"User ID: {user_id}")
print(f"User Email: {user.get('email')}")

# Get bookings
res_bookings = supabase.table("interview_bookings").select("*").eq("user_id", user_id).execute()
print(f"\nBookings found: {len(res_bookings.data)}")

for booking in res_bookings.data:
    print(f"  - Token: {booking.get('token')}, Scheduled: {booking.get('scheduled_at')}, Status: {booking.get('status')}")

# Get tokens
tokens = [b["token"] for b in res_bookings.data if b.get("token")]
print(f"\nTokens: {tokens}")

# Get evaluations
if tokens:
    res_evals = supabase.table("evaluations").select("*").in_("booking_token", tokens).execute()
    print(f"\nEvaluations found: {len(res_evals.data)}")
    for ev in res_evals.data:
        print(f"  - Token: {ev.get('booking_token')}, Score: {ev.get('overall_score')}")
