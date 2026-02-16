from fastapi.testclient import TestClient
from app.api.main import app
from app.utils.auth_dependencies import get_current_admin
from app.services.container import user_service, booking_service

# Mock overrides
def mock_get_current_admin():
    return {"id": "test-admin", "email": "admin@example.com", "role": "admin"}

def mock_get_user_by_email(email):
    return {"id": "test-user-id", "email": email, "name": "Test User", "phone": "1234567890"}

def mock_create_booking(**kwargs):
    return "mock-booking-token"

# Override dependencies
app.dependency_overrides[get_current_admin] = mock_get_current_admin

# Mock services
user_service.get_user_by_email = mock_get_user_by_email
booking_service.create_booking = mock_create_booking

client = TestClient(app)

def test_bulk_json():
    print("Testing /api/admin/schedule-interview/bulk-json...")
    payload = {
        "prompt": "You are a Python expert.",
        "candidates": [
            {"email": "test@example.com", "datetime": "2026-03-15T10:00:00+05:30"},
            {"email": "test2@example.com", "datetime": "2026-03-15T11:00:00"}
        ]
    }
    
    response = client.post("/api/admin/schedule-interview/bulk-json", json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code == 200:
        data = response.json()
        if data["success"] and data["total"] == 2 and data["successful"] == 2:
            print("✅ JSON Bulk Schedule Test PASSED")
        else:
            print("❌ JSON Bulk Schedule Test FAILED (Logic)")
    else:
        print("❌ JSON Bulk Schedule Test FAILED (Status Code)")

if __name__ == "__main__":
    try:
        test_bulk_json()
    except Exception as e:
        print(f"❌ Test Failed with Exception: {e}")
