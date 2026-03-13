import pytest
from unittest.mock import MagicMock, patch
from app.services.admin_service import AdminService
from app.utils.exceptions import AgentError

@pytest.fixture
def admin_service(mock_container_services):
    from app.config import get_config
    service = AdminService(get_config())
    service.client = MagicMock()
    return service

def test_verify_password(admin_service):
    password = "adminpassword"
    password_hash = admin_service.hash_password(password)
    assert admin_service.verify_password(password, password_hash) is True
    assert admin_service.verify_password("wrongpassword", password_hash) is False

def test_authenticate_success(admin_service):
    password = "adminpassword"
    password_hash = admin_service.hash_password(password)
    
    mock_response = MagicMock()
    mock_response.data = [{"id": "admin-1", "username": "admin", "password_hash": password_hash, "created_at": "2026-02-14T10:00:00Z"}]
    
    query = admin_service.client.table.return_value.select.return_value
    query.eq.return_value = query
    query.execute.return_value = mock_response
    
    result = admin_service.authenticate("admin", password)
    assert result is not None
    assert result["username"] == "admin"
    assert result["id"] == "admin-1"

def test_authenticate_fail_user_not_found(admin_service):
    mock_response = MagicMock()
    mock_response.data = []
    query = admin_service.client.table.return_value.select.return_value
    query.eq.return_value = query
    query.execute.return_value = mock_response
    
    result = admin_service.authenticate("nonexistent", "password")
    assert result is None

def test_authenticate_fail_wrong_password(admin_service):
    password_hash = admin_service.hash_password("correctpassword")
    mock_response = MagicMock()
    mock_response.data = [{"id": "admin-1", "username": "admin", "password_hash": password_hash}]
    query = admin_service.client.table.return_value.select.return_value
    query.eq.return_value = query
    query.execute.return_value = mock_response
    
    result = admin_service.authenticate("admin", "wrongpassword")
    assert result is None

def test_create_admin_user_success(admin_service):
    mock_response = MagicMock()
    mock_response.data = [{"id": "a1", "username": "newadmin"}]
    admin_service.client.table.return_value.insert.return_value.execute.return_value = mock_response
    
    result = admin_service.create_admin_user("newadmin", "newpassword")
    assert result["username"] == "newadmin"
    assert "id" in result

def test_generate_token(admin_service):
    token = admin_service.generate_token()
    assert len(token) > 0
    assert isinstance(token, str)
