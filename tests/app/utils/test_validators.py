import pytest
from app.utils.validators import (
    validate_email,
    validate_phone,
    validate_string,
    validate_datetime,
    validate_resume_text,
    validate_file_size,
    validate_file_type
)
from app.utils.exceptions import ValidationError

def test_validate_email_success():
    assert validate_email("test@example.com") == "test@example.com"
    assert validate_email("  TEST@EXAMPLE.COM  ") == "test@example.com"

def test_validate_email_fail():
    with pytest.raises(ValidationError):
        validate_email("invalid-email")
    with pytest.raises(ValidationError):
        validate_email(None)

def test_validate_phone_success():
    assert validate_phone("9876543210") == "9876543210"
    assert validate_phone("+91 98765-43210") == "+91 98765-43210"

def test_validate_phone_fail():
    with pytest.raises(ValidationError):
        validate_phone("12345") # Too short
    with pytest.raises(ValidationError):
        validate_phone("abc123456789") # Non-digits

def test_validate_string_success():
    assert validate_string("  hello  ", "field") == "hello"
    assert validate_string(None, "field", required=False) == ""

def test_validate_string_fail():
    with pytest.raises(ValidationError):
        validate_string(None, "field", required=True)
    with pytest.raises(ValidationError):
        validate_string("short", "field", min_length=10)

def test_validate_datetime_success():
    assert validate_datetime("2026-03-13T12:00:00Z") == "2026-03-13T12:00:00Z"

def test_validate_datetime_fail():
    with pytest.raises(ValidationError):
        validate_datetime("not-a-date")

def test_validate_resume_text():
    text = "a" * 4000
    validated = validate_resume_text(text, max_length=3000)
    assert len(validated) == 3000

def test_validate_file_size_success():
    assert validate_file_size(1024, max_size_mb=1) == 1024

def test_validate_file_size_fail():
    with pytest.raises(ValidationError):
        validate_file_size(10 * 1024 * 1024, max_size_mb=5)

def test_validate_file_type_success():
    assert validate_file_type("application/pdf", ["application/pdf", "image/png"]) == "application/pdf"

def test_validate_file_type_fail():
    with pytest.raises(ValidationError):
        validate_file_type("text/plain", ["application/pdf"])
