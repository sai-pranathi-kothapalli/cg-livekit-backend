import os
import supabase
from dotenv import load_dotenv

load_dotenv('.env')

supabase_client = supabase.create_client(
    os.environ.get("SUPABASE_URL"),
    os.environ.get("SUPABASE_SERVICE_KEY")
)

tables = ["users", "enrolled_users", "slots", "interview_bookings", "evaluations", "transcripts", "api_keys", "webhooks"]

for t in tables:
    try:
        res = supabase_client.table(t).select("*").limit(1).execute()
        print(f"\n--- TABLE: {t} ---")
        if res.data:
            for k in res.data[0].keys():
                print(k)
        else:
            print("Empty table, but exists or could not infer columns.")
    except Exception as e:
        print(f"Table {t} error/not found: {e}")
