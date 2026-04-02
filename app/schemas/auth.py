"""
Auth-related Pydantic schemas.
Moved from app.api.main to this module without changes
to field names or validation logic.
"""

from typing import Optional, Dict, Any

from pydantic import BaseModel, EmailStr, Field, field_validator
from app.utils.sanitize import sanitize_email, sanitize_name, sanitize_phone


class LoginRequest(BaseModel):
    email: Optional[str] = None
    username: Optional[str] = None  # Backward compat with frontend
    password: str

    @field_validator('email')
    @classmethod
    def clean_email(cls, v):
        if v:
            from app.utils.sanitize import sanitize_email
            return sanitize_email(v)
        return v

    def get_login_identifier(self) -> str:
        """Return email or username, whichever was provided."""
        return self.email or self.username or ""


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


class PasswordResetRequestSchema(BaseModel):
    """Step 1: Request an OTP — user provides their email."""
    email: EmailStr

    @field_validator('email')
    @classmethod
    def clean_email(cls, v):
        return sanitize_email(v)


class PasswordResetVerifySchema(BaseModel):
    """Step 2: Verify OTP and set new password."""
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit OTP sent to email")
    new_password: str = Field(..., min_length=12, description="New password, minimum 12 characters")


class StudentRegisterRequest(BaseModel):
    email: EmailStr = Field(..., example="newstudent@example.com")
    password: str = Field(..., example="password123456")
    name: str = Field(..., example="John Doe")
    phone: Optional[str] = Field(None, example="1234567890")

    @field_validator('email')
    @classmethod
    def clean_email(cls, v):
        return sanitize_email(v)

    @field_validator('name')
    @classmethod
    def clean_name(cls, v):
        return sanitize_name(v)

    @field_validator('phone')
    @classmethod
    def clean_phone(cls, v):
        return sanitize_phone(v)


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
    "PasswordResetRequestSchema",
    "PasswordResetVerifySchema",
    "StudentRegisterRequest",
    "AdminLoginRequest",
    "AdminLoginResponse",
]

