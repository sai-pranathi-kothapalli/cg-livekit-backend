import pytest

def test_get_my_assignments(client, mock_container_services, mock_student_auth):
    # Student.py expects 'interview_slots' key in assignment for SlotResponse
    mock_container_services["assignment"].get_user_assignments.return_value = [
        {
            "id": "as1",
            "user_id": "student-123",
            "slot_id": "slot-1",
            "status": "assigned",
            "assigned_at": "2026-03-13T10:00:00Z",
            "interview_slots": {
                "id": "slot-1",
                "slot_datetime": "2026-03-15T10:00:00+05:30",
                "status": "active",
                "current_bookings": 0,
                "max_capacity": 10,
                "created_at": "2026-03-13T10:00:00Z"
            }
        }
    ]
    
    response = client.get("/api/student/my-assignments")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["slot"]["id"] == "slot-1"

def test_select_slot_success(client, mock_container_services, mock_student_auth):
    mock_container_services["user"].get_user_by_email.return_value = {"id": "u1", "email": "student@example.com", "name": "Student"}
    mock_container_services["slot"].get_slot.return_value = {
        "id": "slot-1",
        "slot_datetime": "2026-03-15T10:00:00+05:30",
        "status": "active",
        "current_bookings": 0,
        "max_capacity": 10,
        "created_at": "2026-03-13T10:00:00Z"
    }
    mock_container_services["assignment"].get_user_assignments.return_value = [
        {"id": "as1", "user_id": "student-123", "slot_id": "slot-1", "status": "assigned"}
    ]
    mock_container_services["booking"].create_booking.return_value = "tok123"
    
    response = client.post("/api/student/select-slot", json={"slot_id": "slot-1"})
    assert response.status_code == 200
    assert response.json()["ok"] is True

def test_get_my_interview(client, mock_container_services, mock_student_auth):
    mock_container_services["user"].get_user_by_email.return_value = {"id": "u1", "email": "student@example.com"}
    mock_container_services["booking"].get_bookings_by_email.return_value = [
        {"token": "tok1", "status": "scheduled", "scheduled_at": "2026-03-15T10:00:00", "slot_id": "s1"}
    ]
    mock_container_services["booking"].get_bookings_by_user_id.return_value = []
    mock_container_services["slot"].get_slot.return_value = {
        "id": "s1",
        "slot_datetime": "2026-03-15T10:00:00+05:30",
        "status": "active",
        "current_bookings": 1,
        "max_capacity": 10,
        "created_at": "2026-03-13T10:00:00Z"
    }
    
    response = client.get("/api/student/my-interview")
    assert response.status_code == 200
    assert "upcoming" in response.json()

def test_upload_application_form_compat(client):
    files = {"file": ("form.pdf", b"content", "application/pdf")}
    response = client.post("/api/student/application-form/upload", files=files)
    assert response.status_code == 200
    assert response.json()["success"] is True
