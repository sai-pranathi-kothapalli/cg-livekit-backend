"""
Auth-related Pydantic schemas.
Moved from app.api.main to this module without changes
to field names or validation logic.
"""

from typing import Optional, Dict, Any

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    user: Optional[Dict[str, Any]] = None
    must_change_password: Optional[bool] = None
    error: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    email: str
    old_password: str
    new_password: str


class ResetPasswordRequest(BaseModel):
    email: str
    new_password: str


class StudentRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    phone: Optional[str] = None


class AdminLoginRequest(BaseModel):
    username: str
    password: str


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

