import re
import html
from typing import Optional


def sanitize_string(
    value: str,
    max_length: int = 10000,
    strip_html: bool = True,
    strip_null_bytes: bool = True
) -> str:
    """
    General-purpose string sanitizer.
    - Strips leading/trailing whitespace
    - Removes null bytes (can break DB queries)
    - Optionally strips HTML tags (prevents XSS)
    - Truncates to max_length (prevents payload abuse)
    """
    if not isinstance(value, str):
        return str(value)

    # Strip whitespace
    value = value.strip()

    # Remove null bytes — these can break PostgreSQL and bypass filters
    if strip_null_bytes:
        value = value.replace('\x00', '')

    # Strip HTML tags to prevent XSS
    if strip_html:
        value = re.sub(r'<[^>]+>', '', value)

    # Truncate to max length
    if len(value) > max_length:
        value = value[:max_length]

    return value


def sanitize_email(email: str) -> str:
    """
    Sanitize and validate an email address.
    - Lowercase
    - Strip whitespace
    - Basic format check
    """
    if not isinstance(email, str):
        raise ValueError("Email must be a string")
        
    email = email.strip().lower()

    # Remove null bytes
    email = email.replace('\x00', '')

    # Basic format validation
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        raise ValueError(f"Invalid email format: {email}")

    # Max length check (emails shouldn't be longer than 254 chars per RFC)
    if len(email) > 254:
        raise ValueError("Email address too long")

    return email


def sanitize_name(name: str, max_length: int = 200) -> str:
    """
    Sanitize a person's name.
    - Strip HTML
    - Remove control characters
    - Limit length
    """
    name = sanitize_string(name, max_length=max_length, strip_html=True)

    # Remove control characters (but keep spaces, hyphens, apostrophes, dots)
    name = re.sub(r'[^\w\s\'\-\.\,]', '', name, flags=re.UNICODE)

    return name


def sanitize_code(code: str, max_length: int = 50000) -> str:
    """
    Sanitize code input from the IDE/compiler.
    - Do NOT strip HTML (code may contain < > characters legitimately)
    - Remove null bytes
    - Limit length (50KB max)
    """
    if not isinstance(code, str):
        return str(code)

    code = code.replace('\x00', '')

    if len(code) > max_length:
        code = code[:max_length]

    return code


def sanitize_phone(phone: str) -> str:
    """Sanitize phone number — keep only digits, +, -, spaces, parens."""
    if not phone:
        return ""
    phone = phone.strip()
    phone = re.sub(r'[^\d\+\-\s\(\)]', '', phone)

    if len(phone) > 50:
        raise ValueError("Phone number too long")

    return phone


def sanitize_uuid(value: str) -> str:
    """Validate and sanitize a UUID string."""
    if not isinstance(value, str):
        raise ValueError("UUID must be a string")
        
    value = value.strip().lower()

    if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', value):
        raise ValueError(f"Invalid UUID format: {value}")

    return value


def sanitize_for_llm(text: str, max_length: int = 20000) -> str:
    """
    Sanitize text before sending to an LLM.
    - Prevent oversized inputs
    - Remove null bytes and hidden control characters
    """
    if not isinstance(text, str):
        return str(text)

    # Remove null bytes and control characters (keep newlines and tabs)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    # Truncate
    if len(text) > max_length:
        text = text[:max_length] + "\n[TRUNCATED — input exceeded maximum length]"

    return text
