from app.db.supabase import get_supabase
from app.config import get_config

def check_slots():
    client = get_supabase()
    response = client.table('slots').select('*').eq('batch', 'TEST-BATCH').execute()
    if response.data:
        for slot in response.data:
            print(f"Slot ID: {slot.get('id')}, Student ID: {slot.get('student_id')}")
    else:
        print("No slots found for TEST-BATCH")

if __name__ == "__main__":
    check_slots()
