import pytest
import jwt
import os
from unittest.mock import MagicMock, patch
from app.services.auth_service import AuthService, _is_supabase_connectivity_error
from app.utils.exceptions import AgentError, SupabaseUnavailableError

@pytest.fixture
def auth_service(mock_container_services):
    from app.config import get_config
    with patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret"}):
        service = AuthService(get_config())
        service.client = MagicMock()
        return service

def test_password_logic(auth_service):
    password = "secretpassword"
    pw_hash = auth_service.hash_password(password)
    assert auth_service.verify_password(password, pw_hash) is True
    assert auth_service.verify_password("wrong", pw_hash) is False

def test_token_logic(auth_service):
    user_id = "user-1"
    role = "admin"
    token = auth_service.generate_token(user_id, role, username="admin")
    assert isinstance(token, str)
    
    payload = auth_service.verify_token(token)
    assert payload["user_id"] == user_id
    assert payload["role"] == role
    assert payload["username"] == "admin"

def test_authenticate_unified_email(auth_service):
    mock_response = MagicMock()
    pw_hash = auth_service.hash_password("password123")
    mock_response.data = [{"id": "u1", "email": "test@example.com", "password_hash": pw_hash}]
    query = auth_service.client.table.return_value.select.return_value
    query.eq.return_value = query
    query.execute.return_value = mock_response
    
    result = auth_service.authenticate_unified("test@example.com", "password123")
    assert result["id"] == "u1"

def test_authenticate_student(auth_service):
    mock_response = MagicMock()
    pw_hash = auth_service.hash_password("password123")
    mock_response.data = [{"id": "s1", "email": "s@e.com", "role": "student", "password_hash": pw_hash}]
    query = auth_service.client.table.return_value.select.return_value
    query.eq.return_value = query
    query.execute.return_value = mock_response
    
    result = auth_service.authenticate_student("s@e.com", "password123")
    assert result["id"] == "s1"
    assert result["role"] == "student"

def test_register_student_success(auth_service):
    # Mock no existing user
    mock_check = MagicMock()
    mock_check.data = []
    
    query = auth_service.client.table.return_value.select.return_value
    query.eq.return_value = query
    query.execute.return_value = mock_check
    
    # Mock insert
    mock_insert = MagicMock()
    auth_service.client.table.return_value.insert.return_value.execute.return_value = mock_insert
    
    result = auth_service.register_student("new@e.com", "pass123", "New Student")
    assert result["email"] == "new@e.com"
    assert "password_hash" in result

def test_reset_password(auth_service):
    mock_response = MagicMock()
    mock_response.data = [{"email": "test@e.com"}]
    query = auth_service.client.table.return_value.update.return_value
    query.eq.return_value = query
    query.in_.return_value = query
    query.execute.return_value = mock_response
    
    assert auth_service.reset_password("test@e.com", "newpass") is True

def test_register_manager_success(auth_service):
    # Mock no existing user
    mock_check = MagicMock()
    mock_check.data = []
    auth_service.client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_check

    # Mock insert
    mock_insert = MagicMock()
    mock_insert.data = [{"id": "mgr-1", "name": "Mgr", "email": "mgr@e.com"}]
    auth_service.client.table.return_value.insert.return_value.execute.return_value = mock_insert
    
    result = auth_service.register_manager("Mgr", "mgr@e.com")
    assert result["email"] == "mgr@e.com"
    # The actual field in AuthService is 'temp_password'
    assert "temp_password" in result

def test_authenticate_admin_failure(auth_service):
    # Mock user not found
    mock_response = MagicMock()
    mock_response.data = []
    auth_service.client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
    
    result = auth_service.authenticate_admin("admin", "wrong")
    assert result is None

def test_change_user_password_student(auth_service):
    # Mock student auth success
    mock_student = {"id": "s1", "email": "s@e.com", "role": "student"}
    with patch.object(auth_service, "authenticate_student", return_value=mock_student):
        # Mock update
        mock_update = MagicMock()
        mock_update.data = [{"id": "s1"}]
        auth_service.client.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_update
        
        result = auth_service.change_user_password("s@e.com", "old", "new")
        assert result is True

def test_delete_user_by_email(auth_service):
    mock_response = MagicMock()
    auth_service.client.table.return_value.delete.return_value.eq.return_value.execute.return_value = mock_response
    
    auth_service.delete_user_by_email("test@e.com")
    assert auth_service.client.table.return_value.delete.called

def test_connectivity_error_detection():
    # Test connectivity error detection
    e = Exception("SSL handshake failed")
    assert _is_supabase_connectivity_error(e) is True
    
    e2 = Exception("Regular error")
    assert _is_supabase_connectivity_error(e2) is False

def test_authenticate_unified_not_found(auth_service):
    # Mock user not found
    mock_response = MagicMock()
    mock_response.data = []
    auth_service.client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
    
    result = auth_service.authenticate_unified("unknown@e.com", "pass")
    assert result is None

@pytest.mark.asyncio
async def test_auth_service_connectivity_error_handling(auth_service):
    # Mock supabase connectivity error
    auth_service.client.table.side_effect = Exception("525 SSL handshake failed")
    
    with pytest.raises(SupabaseUnavailableError):
        auth_service.authenticate_unified("test@e.com", "pass")
