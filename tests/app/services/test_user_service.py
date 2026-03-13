import pytest
from unittest.mock import MagicMock
from app.services.user_service import UserService
from app.utils.exceptions import AgentError
@pytest.fixture
def user_service(mock_container_services):
    from app.config import get_config
    service = UserService(get_config())
    service.client = MagicMock()
    return service

def test_create_user_success(user_service):
    mock_response = MagicMock()
    mock_user = {"id": "user-1", "name": "Test User", "email": "test@example.com", "status": "enrolled"}
    mock_response.data = [mock_user]
    user_service.client.table.return_value.insert.return_value.execute.return_value = mock_response
    
    result = user_service.create_user("Test User", "test@example.com")
    assert result["name"] == "Test User"
    assert result["email"] == "test@example.com"

def test_get_user_by_email(user_service):
    mock_response = MagicMock()
    mock_user = {"id": "user-1", "email": "test@example.com"}
    mock_response.data = [mock_user]
    query = user_service.client.table.return_value.select.return_value
    query.eq.return_value = query
    query.execute.return_value = mock_response
    
    result = user_service.get_user_by_email("test@example.com")
    assert result["id"] == "user-1"

def test_get_user_by_id(user_service):
    mock_response = MagicMock()
    mock_user = {"id": "user-1"}
    mock_response.data = [mock_user]
    query = user_service.client.table.return_value.select.return_value
    query.eq.return_value = query
    query.execute.return_value = mock_response
    
    result = user_service.get_user("user-1")
    assert result["id"] == "user-1"

def test_get_all_users(user_service):
    mock_response = MagicMock()
    mock_users = [{"id": "u1"}, {"id": "u2"}]
    mock_response.data = mock_users
    query = user_service.client.table.return_value.select.return_value
    query.order.return_value = query
    query.limit.return_value = query
    query.execute.return_value = mock_response
    
    result = user_service.get_all_users(limit=10)
    assert len(result) == 2

def test_count_users(user_service):
    mock_response = MagicMock()
    mock_response.count = 5
    user_service.client.table.return_value.select.return_value.execute.return_value = mock_response
    
    assert user_service.count_users() == 5

def test_update_user_success(user_service):
    mock_response = MagicMock()
    mock_user = {"id": "user-1", "name": "Updated Name"}
    mock_response.data = [mock_user]
    query = user_service.client.table.return_value.update.return_value
    query.eq.return_value = query
    query.execute.return_value = mock_response
    
    result = user_service.update_user("user-1", name="Updated Name")
    assert result["name"] == "Updated Name"

def test_delete_user_success(user_service):
    mock_response = MagicMock()
    query = user_service.client.table.return_value.delete.return_value
    query.eq.return_value = query
    query.execute.return_value = mock_response
    
    assert user_service.delete_user("user-1") is True
