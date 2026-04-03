import urllib.request
import json
import uuid

base_url = "http://localhost:8000/api/integration"
headers = {
    "X-API-Key": "cgn_live_lms_42c924d77ff184e6bd6ad649c7a8b6ad3c17b26d738d2e75",
    "Content-Type": "application/json"
}

def do_req(url, data=None, method="GET"):
    req_data = None
    if data:
        req_data = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except:
            return e.code, e.read().decode()
    except Exception as e:
        return 0, str(e)

st_uuid1 = str(uuid.uuid4())
st_uuid2 = str(uuid.uuid4())
st_uuid3 = str(uuid.uuid4())
st_uuid4 = str(uuid.uuid4())
st_uuid5 = str(uuid.uuid4())

print("=== Test 1: Enroll 5 students ===")
students = [
    {"student_id": st_uuid1, "email": f"t1_{st_uuid1[:8]}@test.com", "name": "Student A", "batch": "PFS-106", "location": "vijayawada"},
    {"student_id": st_uuid2, "email": f"t2_{st_uuid2[:8]}@test.com", "name": "Student B", "batch": "PFS-106", "location": "vijayawada"},
    {"student_id": st_uuid3, "email": f"t3_{st_uuid3[:8]}@test.com", "name": "Student C", "batch": "PFS-106", "location": "vijayawada"},
    {"student_id": st_uuid4, "email": f"t4_{st_uuid4[:8]}@test.com", "name": "Student D", "batch": "PFS-106", "location": "vijayawada"},
    {"student_id": st_uuid5, "email": f"t5_{st_uuid5[:8]}@test.com", "name": "Student E", "batch": "PFS-106", "location": "vijayawada"}
]

code1, resp1 = do_req(f"{base_url}/enroll-students", data={"batch": "PFS-106", "location": "vijayawada", "students": students}, method="POST")
print("Status:", code1)
print("Response:", json.dumps(resp1, indent=2))

print("\n=== Test 2: Schedule interview (create slots) ===")
code2, resp2 = do_req(f"{base_url}/schedule-interview", data={
    "batch": "PFS-106",
    "location": "vijayawada",
    "date": "2026-05-01",
    "window_start": "10:00",
    "window_end": "12:00",
    "interview_duration": 60,
    "curriculum_topics": "Testing Full Capacity",
    "capacity": 2
}, method="POST")
print("Status:", code2)
print("Response:", json.dumps(resp2, indent=2))

slot_id = None
if isinstance(resp2, dict) and resp2.get("slots"):
    slot_id = resp2["slots"][0]["slot_id"]

print("\n=== Test 3: Get slots for batch ===")
code3, resp3 = do_req(f"{base_url}/slots?batch=PFS-106")
print("Status:", code3)
if isinstance(resp3, dict) and resp3.get("slots"):
    slot = next((s for s in resp3['slots'] if s.get('slot_id') == slot_id), None)
    print("Found our Slot:", slot)
else:
    print("No slots found or bad response:", resp3)

print("\n=== Test 4: Book a student ===")
if slot_id:
    code4, resp4 = do_req(f"{base_url}/book-slot", data={
        "student_id": st_uuid1,
        "batch": "PFS-106",
        "slot_id": slot_id
    }, method="POST")
    print("Status:", code4)
    print("Response:", json.dumps(resp4, indent=2))

print("\n=== Test 5: Book until full, verify 409 ===")
if slot_id:
    print("Booking Student B (should succeed):")
    code5a, resp5a = do_req(f"{base_url}/book-slot", data={
        "student_id": st_uuid2,
        "batch": "PFS-106",
        "slot_id": slot_id
    }, method="POST")
    print("Status:", code5a)
    print("Response:", json.dumps(resp5a, indent=2))
    
    print("\nBooking Student C (should fail with 409):")
    code5b, resp5b = do_req(f"{base_url}/book-slot", data={
        "student_id": st_uuid3,
        "batch": "PFS-106",
        "slot_id": slot_id
    }, method="POST")
    print("Status:", code5b)
    print("Response:", json.dumps(resp5b, indent=2))
