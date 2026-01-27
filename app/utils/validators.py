"""
Input Validation Utilities

Comprehensive validation functions for all input types
with proper error handling and type checking.
"""

import re
from typing import Any, Optional, List
from email.utils import parseaddr

from app.utils.exceptions import ValidationError


def validate_email(email: str, field_name: str = "email") -> str:
    """
    Validate email address format.
    
    Args:
        email: Email address to validate
        field_name: Name of the field for error messages
        
    Returns:
        Validated email address
        
    Raises:
        ValidationError: If email is invalid
    """
    if not email or not isinstance(email, str):
        raise ValidationError(f"{field_name} is required and must be a string", field_name)
    
    email = email.strip().lower()
    
    # Basic format check
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        raise ValidationError(f"Invalid {field_name} format", field_name)
    
    # Use email.utils for additional validation
    name, addr = parseaddr(email)
    if not addr or '@' not in addr:
        raise ValidationError(f"Invalid {field_name} format", field_name)
    
    return email


def validate_phone(phone: str, field_name: str = "phone") -> str:
    """
    Validate phone number format.
    
    Args:
        phone: Phone number to validate
        field_name: Name of the field for error messages
        
    Returns:
        Validated phone number
        
    Raises:
        ValidationError: If phone is invalid
    """
    if not phone or not isinstance(phone, str):
        raise ValidationError(f"{field_name} is required and must be a string", field_name)
    
    phone = phone.strip()
    
    # Remove common separators
    phone_clean = re.sub(r'[\s\-\(\)\+]', '', phone)
    
    # Check if it contains only digits
    if not phone_clean.isdigit():
        raise ValidationError(f"{field_name} must contain only digits and common separators", field_name)
    
    # Check minimum length (at least 10 digits)
    if len(phone_clean) < 10:
        raise ValidationError(f"{field_name} must be at least 10 digits", field_name)
    
    # Check maximum length (reasonable limit)
    if len(phone_clean) > 15:
        raise ValidationError(f"{field_name} must not exceed 15 digits", field_name)
    
    return phone


def validate_string(
    value: Any,
    field_name: str,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    required: bool = True,
) -> str:
    """
    Validate string value.
    
    Args:
        value: Value to validate
        field_name: Name of the field for error messages
        min_length: Minimum length requirement
        max_length: Maximum length requirement
        required: Whether the field is required
        
    Returns:
        Validated string
        
    Raises:
        ValidationError: If validation fails
    """
    if value is None or value == "":
        if required:
            raise ValidationError(f"{field_name} is required", field_name)
        return ""
    
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string", field_name)
    
    value = value.strip()
    
    if min_length and len(value) < min_length:
        raise ValidationError(
            f"{field_name} must be at least {min_length} characters",
            field_name
        )
    
    if max_length and len(value) > max_length:
        raise ValidationError(
            f"{field_name} must not exceed {max_length} characters",
            field_name
        )
    
    return value


def validate_datetime(datetime_str: str, field_name: str = "datetime") -> str:
    """
    Validate datetime string format (ISO 8601).
    
    Args:
        datetime_str: Datetime string to validate
        field_name: Name of the field for error messages
        
    Returns:
        Validated datetime string
        
    Raises:
        ValidationError: If datetime is invalid
    """
    if not datetime_str or not isinstance(datetime_str, str):
        raise ValidationError(f"{field_name} is required and must be a string", field_name)
    
    datetime_str = datetime_str.strip()
    
    # Try to parse as ISO 8601
    try:
        from datetime import datetime
        datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
    except ValueError:
        raise ValidationError(
            f"{field_name} must be a valid ISO 8601 datetime string",
            field_name
        )
    
    return datetime_str


def validate_resume_text(resume_text: Optional[str], max_length: int = 3000) -> Optional[str]:
    """
    Validate application text content.
    
    Args:
        resume_text: Application text to validate (kept as resume_text for backward compatibility)
        max_length: Maximum allowed length
        
    Returns:
        Validated application text (truncated if necessary)
        
    Raises:
        ValidationError: If validation fails
    """
    if resume_text is None:
        return None
    
    if not isinstance(resume_text, str):
        raise ValidationError("resume_text must be a string", "resume_text")
    
    resume_text = resume_text.strip()
    
    if len(resume_text) > max_length:
        # Truncate to max_length
        resume_text = resume_text[:max_length]
    
    return resume_text


def validate_file_size(file_size: int, max_size_mb: int = 5, field_name: str = "file") -> int:
    """
    Validate file size.
    
    Args:
        file_size: File size in bytes
        max_size_mb: Maximum size in megabytes
        field_name: Name of the field for error messages
        
    Returns:
        Validated file size
        
    Raises:
        ValidationError: If file size exceeds limit
    """
    if not isinstance(file_size, int) or file_size < 0:
        raise ValidationError(f"{field_name} size must be a positive integer", field_name)
    
    max_size_bytes = max_size_mb * 1024 * 1024
    
    if file_size > max_size_bytes:
        raise ValidationError(
            f"{field_name} size must not exceed {max_size_mb}MB",
            field_name
        )
    
    return file_size


def validate_file_type(
    file_type: str,
    allowed_types: List[str],
    field_name: str = "file"
) -> str:
    """
    Validate file MIME type.
    
    Args:
        file_type: MIME type to validate
        allowed_types: List of allowed MIME types
        field_name: Name of the field for error messages
        
    Returns:
        Validated file type
        
    Raises:
        ValidationError: If file type is not allowed
    """
    if not file_type or not isinstance(file_type, str):
        raise ValidationError(f"{field_name} type is required", field_name)
    
    file_type = file_type.lower().strip()
    
    if file_type not in [t.lower() for t in allowed_types]:
        raise ValidationError(
            f"{field_name} type must be one of: {', '.join(allowed_types)}",
            field_name
        )
    
    return file_type

