import pytest
from unittest.mock import MagicMock, patch
from app.api.main import app
from app.utils.api_key import get_api_key

def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_ready_success(client):
    with patch("app.api.main.get_supabase") as mock_supabase:
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.limit.return_value.execute.return_value = MagicMock()
        
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}

def test_ready_failure(client):
    with patch("app.api.main.get_supabase") as mock_supabase:
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.limit.return_value.execute.side_effect = Exception("DB error")
        
        response = client.get("/ready")
        assert response.status_code == 503
        assert "Service not ready" in response.json()["detail"]

def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_get_interview_config(client):
    response = client.get("/api/public/interview-config")
    assert response.status_code == 200
    assert "require_login_for_interview" in response.json()

def test_serve_file_redirect(client):
    with patch("app.api.main.get_supabase") as mock_supabase:
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_client.storage.from_.return_value.get_public_url.return_value = "http://example.com/file"
        
        response = client.get("/api/files/test-file", follow_redirects=False)
        assert response.status_code == 307  # Temporary redirect
        assert response.headers["location"] == "http://example.com/file"

def test_get_secure_data_fail(client):
    # No API key
    response = client.get("/api/secure-data")
    assert response.status_code == 401 # Missing API Key

def test_get_secure_data_success(client):
    # Override the dependency globally on the app
    app.dependency_overrides[get_api_key] = lambda: "valid-key"
    try:
        response = client.get("/api/secure-data", headers={"X-API-Key": "valid-key"})
        assert response.status_code == 200
        assert response.json()["message"] == "Secure data accessed successfully"
    finally:
        app.dependency_overrides.pop(get_api_key, None)
