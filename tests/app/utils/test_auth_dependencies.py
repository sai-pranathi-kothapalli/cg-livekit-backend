import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import HTTPException
from app.utils.auth_dependencies import (
    get_auth_service,
    get_current_user,
    get_current_admin,
    get_current_student,
    get_optional_user,
    get_optional_student
)

@pytest.fixture
def mock_auth_service():
    service = MagicMock()
    return service

def test_get_auth_service():
    with patch("app.utils.auth_dependencies.AuthService") as mock_auth_cls:
        with patch("app.utils.auth_dependencies.get_config") as mock_get_config:
            mock_get_config.return_value = MagicMock()
            service = get_auth_service()
            assert mock_auth_cls.called
            assert isinstance(service, MagicMock)

@pytest.mark.asyncio
async def test_get_current_user_success(mock_auth_service):
    credentials = MagicMock()
    credentials.credentials = "valid-token"
    mock_auth_service.verify_token.return_value = {"user_id": "u1", "role": "admin"}
    mock_auth_service.get_admin_by_id.return_value = {"id": "u1", "role": "admin"}
    
    user = await get_current_user(credentials, mock_auth_service)
    assert user["id"] == "u1"
    assert user["role"] == "admin"

@pytest.mark.asyncio
async def test_get_current_user_invalid_token(mock_auth_service):
    credentials = MagicMock()
    credentials.credentials = "invalid-token"
    mock_auth_service.verify_token.return_value = None
    
    with pytest.raises(HTTPException) as excinfo:
        await get_current_user(credentials, mock_auth_service)
    assert excinfo.value.status_code == 401

@pytest.mark.asyncio
async def test_get_current_admin_success():
    user = {"role": "admin"}
    result = await get_current_admin(user)
    assert result == user

@pytest.mark.asyncio
async def test_get_current_admin_fail():
    user = {"role": "student"}
    with pytest.raises(HTTPException) as excinfo:
        await get_current_admin(user)
    assert excinfo.value.status_code == 403

@pytest.mark.asyncio
async def test_get_current_student_success():
    user = {"role": "student"}
    result = await get_current_student(user)
    assert result == user

@pytest.mark.asyncio
async def test_get_optional_user_none(mock_auth_service):
    result = get_optional_user(None, mock_auth_service)
    assert result is None

@pytest.mark.asyncio
async def test_get_optional_student_success(mock_auth_service):
    credentials = MagicMock()
    credentials.credentials = "token"
    mock_auth_service.verify_token.return_value = {"user_id": "s1", "role": "student"}
    mock_auth_service.get_student_by_id.return_value = {"id": "s1", "role": "student"}
    
    result = await get_optional_student(credentials, mock_auth_service)
    assert result["id"] == "s1"
