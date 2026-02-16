"""
Auth-related Pydantic schemas.
Moved from app.api.main to this module without changes
to field names or validation logic.
"""

from typing import Optional, Dict, Any

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    username: str = Field(..., example="test@example.com")
    password: str = Field(..., example="password123")


class LoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    user: Optional[Dict[str, Any]] = None
    must_change_password: Optional[bool] = None
    error: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    email: EmailStr = Field(..., example="test@example.com")
    old_password: str = Field(..., example="oldpassword123")
    new_password: str = Field(..., min_length=12, description="New password must be at least 12 characters.", example="newpassword123")


class ResetPasswordRequest(BaseModel):
    email: str = Field(..., example="test@example.com")
    new_password: str = Field(..., example="resetpassword123")


class StudentRegisterRequest(BaseModel):
    email: EmailStr = Field(..., example="newstudent@example.com")
    password: str = Field(..., example="password123456")
    name: str = Field(..., example="John Doe")
    phone: Optional[str] = Field(None, example="1234567890")


class AdminLoginRequest(BaseModel):
    username: str = Field(..., example="admin")
    password: str = Field(..., example="adminpassword")


class AdminLoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    error: Optional[str] = None


__all__ = [
    "LoginRequest",
    "LoginResponse",
    "ChangePasswordRequest",
    "ResetPasswordRequest",
    "StudentRegisterRequest",
    "AdminLoginRequest",
    "AdminLoginResponse",
]

