import requests
import json
import time

BASE_URL = "http://localhost:8000"
API_KEY = "test-integration-key-123"

# Valid UUIDs generated for testing
SID_1 = "656d551a-0b90-4841-b328-47b1d48d6843"
SID_2 = "eb430719-61c4-4c03-a263-6f68df60dd70"
MISSING_UUID = "00000000-0000-4000-a000-000000000000"

def test_schedule_with_validation():
    print("\n--- Test 1: Enroll students ---")
    enroll_payload = {
        "batch": "TEST-VAL-102",
        "location": "test-loc",
        "students": [
            {"student_id": SID_1, "email": "v1@test.com", "name": "Valid 1", "batch": "TEST-VAL-102", "location": "test-loc"},
            {"student_id": SID_2, "email": "v2@test.com", "name": "Valid 2", "batch": "TEST-VAL-102", "location": "test-loc"}
        ]
    }
    r = requests.post(f"{BASE_URL}/api/integration/enroll-students", 
                     headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
                     data=json.dumps(enroll_payload))
    print(f"Enroll Response: {r.status_code}")
    print(r.json())

    print("\n--- Test 2: Schedule with student_ids (valid) ---")
    schedule_payload = {
        "batch": "TEST-VAL-102",
        "location": "test-loc",
        "student_ids": [SID_1, SID_2],
        "date": "2026-06-01",
        "window_start": "09:00",
        "window_end": "11:00",
        "interview_duration": 60
    }
    r = requests.post(f"{BASE_URL}/api/integration/schedule-interview",
                     headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
                     data=json.dumps(schedule_payload))
    print(f"Schedule Response: {r.status_code}")
    res = r.json()
    print(json.dumps(res, indent=2))
    assert res["success"] is True
    assert res["student_validation"]["enrolled"] == 2
    assert len(res["student_validation"]["not_enrolled"]) == 0

    print("\n--- Test 3: Schedule with mixed student_ids (one invalid) ---")
    schedule_payload["student_ids"] = [SID_1, MISSING_UUID]
    schedule_payload["date"] = "2026-06-02"
    r = requests.post(f"{BASE_URL}/api/integration/schedule-interview",
                     headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
                     data=json.dumps(schedule_payload))
    print(f"Schedule Response: {r.status_code}")
    res = r.json()
    print(json.dumps(res, indent=2))
    assert res["success"] is True
    assert res["student_validation"]["enrolled"] == 1
    assert MISSING_UUID in res["student_validation"]["not_enrolled"]

    print("\n--- Test 4: Schedule without student_ids (backward compatibility) ---")
    del schedule_payload["student_ids"]
    schedule_payload["date"] = "2026-06-03"
    r = requests.post(f"{BASE_URL}/api/integration/schedule-interview",
                     headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
                     data=json.dumps(schedule_payload))
    print(f"Schedule Response: {r.status_code}")
    res = r.json()
    print(json.dumps(res, indent=2))
    assert res["success"] is True
    assert "student_validation" not in res

    print("\n--- All tests passed! ---")

if __name__ == "__main__":
    test_schedule_with_validation()
