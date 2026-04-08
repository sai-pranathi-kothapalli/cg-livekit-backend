import pytest
from pydantic import ValidationError
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    ChangePasswordRequest,
    StudentRegisterRequest,
    AdminLoginRequest,
    AdminLoginResponse
)

def test_login_request():
    valid_data = {"username": "user", "password": "pass"}
    model = LoginRequest(**valid_data)
    assert model.username == "user"
    
    with pytest.raises(ValidationError):
        LoginRequest(username="user")

def test_change_password_request():
    valid_data = {
        "email": "test@example.com",
        "old_password": "old",
        "new_password": "newpassword123" # Min 12 chars
    }
    model = ChangePasswordRequest(**valid_data)
    assert model.new_password == "newpassword123"
    
    with pytest.raises(ValidationError):
        ChangePasswordRequest(
            email="test@example.com",
            old_password="old",
            new_password="short"
        )

def test_student_register_request():
    valid_data = {
        "email": "student@example.com",
        "password": "pass",
        "name": "John Doe"
    }
    model = StudentRegisterRequest(**valid_data)
    assert model.name == "John Doe"
    
    with pytest.raises(ValidationError):
        StudentRegisterRequest(email="not-email", password="pass", name="John")

def test_admin_login_request():
    valid_data = {"username": "admin", "password": "pass"}
    model = AdminLoginRequest(**valid_data)
    assert model.username == "admin"
