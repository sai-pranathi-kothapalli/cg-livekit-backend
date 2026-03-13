import pytest
from unittest.mock import MagicMock, patch

def test_public_schedule_interview(client, mock_container_services):
    mock_container_services["booking"].create_booking.return_value = "public-token"
    mock_container_services["email"].send_interview_email.return_value = (True, None)
    
    response = client.post("/api/bookings/schedule-interview", json={
        "name": "Public Candidate",
        "email": "p@example.com",
        "datetime": "2026-12-31T12:00:00"
    })
    
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert "public-token" in response.json()["interviewUrl"]

def test_get_booking_no_login_required(client, mock_container_services):
    # Mock config.REQUIRE_LOGIN_FOR_INTERVIEW = False
    with patch("app.api.bookings.config") as mock_config:
        mock_config.REQUIRE_LOGIN_FOR_INTERVIEW = False
        mock_container_services["booking"].get_booking.return_value = {
            "token": "tok1", "name": "C1", "email": "c1@example.com", 
            "scheduled_at": "2026-12-31T12:00:00", "created_at": "2023-01-01T10:00:00",
            "slot_id": None
        }
        
        response = client.get("/api/bookings/booking/tok1")
        
        assert response.status_code == 200
        assert response.json()["token"] == "tok1"

def test_get_booking_login_required_unauthorized(client, mock_container_services):
    with patch("app.api.bookings.config") as mock_config:
        mock_config.REQUIRE_LOGIN_FOR_INTERVIEW = True
        
        # Unauthorized (no student_auth fixture)
        response = client.get("/api/bookings/booking/tok1")
        
        assert response.status_code == 401
        assert "Authentication required" in response.json()["detail"]

def test_get_booking_login_required_authorized(client, mock_container_services, mock_student_auth):
    with patch("app.api.bookings.config") as mock_config:
        mock_config.REQUIRE_LOGIN_FOR_INTERVIEW = True
        mock_container_services["booking"].get_booking.return_value = {
            "token": "tok1", "name": "C1", "email": "student@example.com", 
            "scheduled_at": "2026-12-31T12:00:00", "created_at": "2023-01-01T10:00:00",
            "user_id": "student-123"
        }
        
        response = client.get("/api/bookings/booking/tok1")
        
        assert response.status_code == 200
        assert response.json()["token"] == "tok1"
