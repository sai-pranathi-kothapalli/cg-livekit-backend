import pytest
import jwt
import os
from unittest.mock import MagicMock, patch
from app.services.auth_service import AuthService
from app.utils.exceptions import AgentError

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
