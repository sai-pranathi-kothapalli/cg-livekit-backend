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
    assert len(response.json()["upcoming"]) == 1

    files = {"file": ("form.pdf", b"content", "application/pdf")}
    response = client.post("/api/student/application-form/upload", files=files)
    assert response.status_code == 200
    assert response.json()["success"] is True

def test_select_slot_full(client, mock_container_services, mock_student_auth):
    mock_container_services["user"].get_user_by_email.return_value = {"id": "u1", "email": "s@e.com"}
    mock_container_services["slot"].get_slot.return_value = {
        "id": "s1", "current_bookings": 5, "max_capacity": 5, "status": "active"
    }
    mock_container_services["assignment"].get_user_assignments.return_value = [{"slot_id": "s1"}]
    
    response = client.post("/api/student/select-slot", json={"slot_id": "s1"})
    assert response.status_code == 400
    assert "full" in response.json()["detail"]

def test_select_slot_not_assigned(client, mock_container_services, mock_student_auth):
    mock_container_services["user"].get_user_by_email.return_value = {"id": "u1", "email": "s@e.com"}
    mock_container_services["assignment"].get_user_assignments.return_value = [] # No assignment
    # Logic tries to auto-assign. If that fails or we mock it to fail:
    mock_container_services["assignment"].assign_slots_to_user.return_value = []
    
    response = client.post("/api/student/select-slot", json={"slot_id": "slot-unassigned"})
    # Implementation returns 400 if user isn't eligible for auto-assignment or 500 on direct failure
    assert response.status_code in [400, 500]

def test_get_my_interview_complex(client, mock_container_services, mock_student_auth):
    # Test completed and missed paths
    mock_container_services["user"].get_user_by_email.return_value = {"id": "u1", "email": "student@example.com"}
    mock_container_services["slot"].get_slot.return_value = {"id": "s1", "duration_minutes": 30}
    
    # One completed, one missed (scheduled in the past)
    # Use explicit IST offset to avoid any ambiguity
    mock_container_services["booking"].get_bookings_by_email.return_value = [
        {"token": "tok-comp", "status": "completed", "scheduled_at": "2020-03-10T10:00:00+05:30", "slot_id": "s1"},
        {"token": "tok-miss", "status": "scheduled", "scheduled_at": "2020-03-10T11:00:00+05:30", "slot_id": "s2"}
    ]
    mock_container_services["booking"].get_bookings_by_user_id.return_value = []
    
    # Mock completion evidence
    mock_container_services["evaluation"].get_booking_tokens_with_evaluations.return_value = {"tok-comp"}
    mock_container_services["transcript"].get_booking_tokens_with_transcripts.return_value = set()
    
    response = client.get("/api/student/my-interview")
    assert response.status_code == 200
    data = response.json()
    assert len(data.get("completed", [])) >= 1
    assert len(data.get("missed", [])) >= 1

def test_get_my_assignments_error(client, mock_container_services, mock_student_auth):
    mock_container_services["assignment"].get_user_assignments.side_effect = Exception("DB Error")
    response = client.get("/api/student/my-assignments")
    assert response.status_code == 500
