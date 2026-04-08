import httpx
import asyncio

async def test_schedule():
    url = "http://localhost:8000/api/integration/schedule-interview"
    headers = {
        "X-API-Key": "cgn_live_lms_a49dfa338a492e21ef0c0e51ce2d4dbfd897bc7628540b35",
        "Content-Type": "application/json"
    }
    payload = {
        "batch": "TEST-BATCH",
        "location": "test-loc",
        "date": "2026-05-01",
        "window_start": "10:00",
        "window_end": "11:00",
        "interview_duration": 30,
        "curriculum_topics": "Test Topics",
        "capacity": 5,
        "student_id": "test-student-123"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=payload, timeout=10.0)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.json()}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_schedule())
