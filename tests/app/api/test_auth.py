import pytest
from unittest.mock import MagicMock

def test_login_success_student(client, mock_container_services):
    mock_container_services["auth"].authenticate_unified.return_value = {
        "id": "s1", "role": "student", "email": "s@example.com", "name": "Student"
    }
    mock_container_services["auth"].generate_token.return_value = "student-token"
    
    response = client.post("/api/auth/login", json={"username": "s@example.com", "password": "password"})
    
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["token"] == "student-token"
    assert response.json()["user"]["role"] == "student"

def test_login_success_admin(client, mock_container_services):
    mock_container_services["auth"].authenticate_unified.return_value = {
        "id": "a1", "role": "admin", "username": "admin", "email": "admin@example.com"
    }
    mock_container_services["auth"].generate_token.return_value = "admin-token"
    
    response = client.post("/api/auth/login", json={"username": "admin", "password": "password"})
    
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["token"] == "admin-token"
    assert response.json()["user"]["role"] == "admin"

def test_login_failure(client, mock_container_services):
    mock_container_services["auth"].authenticate_unified.return_value = None
    
    response = client.post("/api/auth/login", json={"username": "wrong", "password": "wrong"})
    
    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["error"] == "Invalid credentials"

def test_change_password(client, mock_container_services):
    mock_container_services["auth"].change_user_password.return_value = True
    
    response = client.post("/api/auth/change-password", json={
        "email": "test@example.com", "old_password": "old", "new_password": "newpassword123"
    })
    
    assert response.status_code == 200
    assert response.json()["success"] is True

def test_reset_password(client, mock_container_services):
    mock_container_services["auth"].get_user_by_email.return_value = {"role": "student"}
    mock_container_services["auth"].reset_password.return_value = True
    
    response = client.post("/api/auth/reset-password", json={
        "email": "test@example.com", "new_password": "resetpassword123"
    })
    
    assert response.status_code == 200
    assert response.json()["success"] is True

def test_student_register(client, mock_container_services):
    mock_container_services["auth"].register_student.return_value = {
        "id": "s2", "email": "new@example.com", "name": "New student"
    }
    mock_container_services["auth"].generate_token.return_value = "new-token"
    
    response = client.post("/api/auth/student/register", json={
        "email": "new@example.com", "password": "password123456", "name": "New student"
    })
    
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["token"] == "new-token"

def test_admin_login(client, mock_container_services):
    # This uses admin_service instead of auth_service
    # Wait, the code in auth.py uses admin_service for /admin/login
    from app.services import container
    container.admin_service.authenticate.return_value = {"username": "admin"}
    container.admin_service.generate_token.return_value = "admin-login-token"
    
    response = client.post("/api/auth/admin/login", json={"username": "admin", "password": "password"})
    
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["token"] == "admin-login-token"
