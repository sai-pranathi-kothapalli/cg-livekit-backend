import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta

def test_get_evaluation(client, mock_container_services):
    mock_container_services["booking"].get_booking.return_value = {
        "token": "tok1", 
        "name": "C1", 
        "email": "c1@example.com",
        "scheduled_at": "2026-03-13T10:00:00",
        "created_at": "2026-03-13T09:00:00"
    }
    # Mock transcript to be a list as per EvaluationResponse schema (List[Dict[str, Any]])
    mock_container_services["transcript"].get_transcript.return_value = [{"role": "user", "content": "hello"}]
    mock_container_services["evaluation"].get_evaluation.return_value = {
        "overall_score": 85,
        "strengths": ["Python"],
        "areas_for_improvement": ["SQL"],
        "duration_minutes": 30,
        "interview_state": {"scores": {"overall_feedback": "Good"}}
    }
    
    response = client.get("/api/interviews/evaluation/tok1")
    
    assert response.status_code == 200
    assert response.json()["overall_score"] == 85
    assert response.json()["candidate"]["name"] == "C1"

@pytest.mark.asyncio
async def test_analyze_code(client, mock_container_services):
    # analyze_code is an AsyncMock from conftest.py
    mock_container_services["evaluation"].analyze_code.return_value = "Code is good"
    
    response = client.post("/api/interviews/analyze-code", json={
        "question": "Reverse a list",
        "code": "l[::-1]",
        "language": "python"
    })
    
    assert response.status_code == 200
    assert response.json()["feedback"] == "Code is good"

def test_get_student_analytics(client, mock_container_services, mock_student_auth):
    # get_bookings_by_user_id is now a MagicMock from conftest.py
    mock_container_services["booking"].get_bookings_by_user_id.return_value = [{"token": "tok1"}]
    mock_container_services["evaluation"].get_student_analytics.return_value = {"total_interviews": 1}
    
    response = client.get("/api/interviews/api/student/analytics")
    
    assert response.status_code == 200
    assert response.json()["total_interviews"] == 1

@patch("app.api.interviews.livekit_api.LiveKitAPI")
@patch("app.api.interviews.livekit_api.AccessToken")
def test_connection_details(mock_access_token, mock_livekit_api, client, mock_container_services, mock_student_auth):
    from app.api.interviews import config
    config.livekit.url = "wss://test.livekit"
    config.livekit.api_key = "key"
    config.livekit.api_secret = "secret"
    config.REQUIRE_LOGIN_FOR_INTERVIEW = False
    
    from app.utils.datetime_utils import get_now_ist
    
    # Set scheduled_at to a future time so validation passes (using IST to match API)
    future_time = get_now_ist() + timedelta(minutes=10)
    mock_container_services["booking"].get_booking.return_value = {
        "token": "tok1", 
        "scheduled_at": future_time.isoformat()
    }
    
    # Setup mock LiveKitAPI context manager
    mock_lk_instance = mock_livekit_api.return_value
    mock_lk_instance.__aenter__.return_value = mock_lk_instance
    mock_lk_instance.room.create_room = AsyncMock()
    mock_lk_instance.room.list_participants = AsyncMock(return_value=MagicMock(participants=[]))
    mock_lk_instance.agent_dispatch.create_dispatch = AsyncMock()
    
    # Setup mock AccessToken
    mock_token_instance = mock_access_token.return_value
    mock_token_instance.with_identity.return_value = mock_token_instance
    mock_token_instance.with_name.return_value = mock_token_instance
    mock_token_instance.with_metadata.return_value = mock_token_instance
    mock_token_instance.with_grants.return_value = mock_token_instance
    mock_token_instance.to_jwt.return_value = "jwt-token"
    
    response = client.post("/api/interviews/connection-details", json={
        "token": "tok1",
        "room_config": {"agents": [{"agent_name": "test-agent"}]}
    })
    
    # If it still fails with 400, it might be because the mock didn't return properly
    assert response.status_code == 200
    assert response.json()["participantToken"] == "jwt-token"
    assert response.json()["roomName"] == "interview_tok1"

def test_connection_details_too_early(client, mock_container_services):
    from app.utils.datetime_utils import get_now_ist
    # 2 hours in future
    future_time = get_now_ist() + timedelta(hours=2)
    mock_container_services["booking"].get_booking.return_value = {
        "token": "tok-future", 
        "scheduled_at": future_time.isoformat()
    }
    
    response = client.post("/api/interviews/connection-details", json={"token": "tok-future"})
    assert response.status_code == 400
    assert "not started" in response.json()["detail"].lower()

def test_get_evaluation_not_found(client, mock_container_services):
    mock_container_services["booking"].get_booking.return_value = None
    
    response = client.get("/api/interviews/evaluation/missing")
    assert response.status_code == 404
