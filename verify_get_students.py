import requests
import json
import uuid

BASE_URL = "http://localhost:8000"
API_KEY = "test-integration-key-123"

def test_get_students():
    batch_name = f"GET-TEST-{uuid.uuid4().hex[:6].upper()}"
    print(f"\n--- Testing with batch: {batch_name} ---")

    # 1. Enroll some students
    print("\n--- Step 1: Enroll 2 students ---")
    enroll_payload = {
        "batch": batch_name,
        "location": "test-loc",
        "students": [
            {"student_id": str(uuid.uuid4()), "email": f"s1-{batch_name}@test.com", "name": "Student One", "batch": batch_name, "location": "test-loc"},
            {"student_id": str(uuid.uuid4()), "email": f"s2-{batch_name}@test.com", "name": "Student Two", "batch": batch_name, "location": "test-loc"}
        ]
    }
    r = requests.post(f"{BASE_URL}/api/integration/enroll-students", 
                     headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
                     data=json.dumps(enroll_payload))
    print(f"Enroll Response: {r.status_code}")
    print(r.json())

    # 2. Get students for this batch
    print("\n--- Step 2: GET students for this batch ---")
    r = requests.get(f"{BASE_URL}/api/integration/students?batch={batch_name}",
                    headers={"X-API-Key": API_KEY})
    print(f"GET Response: {r.status_code}")
    res = r.json()
    print(json.dumps(res, indent=2))
    assert res["success"] is True
    assert res["total"] == 2
    assert len(res["students"]) == 2
    assert res["students"][0]["batch"] == batch_name

    # 3. Get students for non-existent batch
    print("\n--- Step 3: GET students for non-existent batch ---")
    r = requests.get(f"{BASE_URL}/api/integration/students?batch=NON-EXISTENT-BATCH",
                    headers={"X-API-Key": API_KEY})
    print(f"GET Response: {r.status_code}")
    res = r.json()
    print(json.dumps(res, indent=2))
    assert res["success"] is True
    assert res["total"] == 0
    assert len(res["students"]) == 0

    # 4. Unauthorized access
    print("\n--- Step 4: Unauthorized access (no API key) ---")
    r = requests.get(f"{BASE_URL}/api/integration/students?batch={batch_name}")
    print(f"GET Response: {r.status_code}")
    # FastAPI returns 400 or 422 if a required Header is missing
    assert r.status_code in [400, 401, 422]

    print("\n--- All tests passed! ---")

if __name__ == "__main__":
    test_get_students()
