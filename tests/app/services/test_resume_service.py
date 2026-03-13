import pytest
from app.services.resume_service import ResumeService

@pytest.fixture
def resume_service():
    from app.config import get_config
    return ResumeService(get_config())

def test_validate_file(resume_service):
    # Valid
    valid, err = resume_service.validate_file(b"content", "test.pdf", "application/pdf")
    assert valid is True
    
    # Too large
    large_content = b"a" * (6 * 1024 * 1024)
    valid, err = resume_service.validate_file(large_content, "test.pdf")
    assert valid is False
    assert "exceeds maximum" in err
    
    # Invalid extension
    valid, err = resume_service.validate_file(b"cont", "test.txt")
    assert valid is False
    assert "not supported" in err

def test_extract_phone_number(resume_service):
    text = "Contact me at 91 98765 43210 or 040-1234567"
    assert resume_service._extract_phone_number(text) == "9876543210"
    
    text2 = "My number is +916302907829"
    assert resume_service._extract_phone_number(text2) == "6302907829"

def test_extract_date(resume_service):
    assert resume_service._extract_date("Born on 15/02/2000") == "2000-02-15"
    assert resume_service._extract_date("Date: 2026-03-12") == "2026-03-12"

def test_extract_aadhaar(resume_service):
    assert resume_service._extract_aadhaar("My Aadhaar is 1234 5678 9012") == "123456789012"
    assert resume_service._extract_aadhaar("UID: 123456789012") == "123456789012"

@pytest.mark.asyncio
async def test_parse_application_data(resume_service):
    text = """
    Full Name: Jane Doe
    Email: jane@example.com
    Mobile: 9876543210
    Date of Birth: 01/01/1995
    Skills: Python, FastAPI, SQL
    Education: B.Tech in CSE from IIT Bombay
    """
    data = await resume_service.parse_application_data(text)
    assert data["full_name"] == "Jane Doe"
    assert data["mobile_number"] == "9876543210"
    assert data["date_of_birth"] == "1995-01-01"
    assert "Python" in data["skills"]
