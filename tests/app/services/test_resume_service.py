import pytest
import os
from unittest.mock import MagicMock, patch
from app.services.resume_service import ResumeService

@pytest.fixture
def resume_service():
    config = MagicMock()
    return ResumeService(config=config)

@pytest.mark.asyncio
async def test_parse_application_data(resume_service):
    text = "Name: John Doe\nEmail: john@example.com\nPhone: 9876543210\nAadhaar: 1234 5678 9012"
    result = await resume_service.parse_application_data(text)
    # The parser returns a flat dict of extracted fields
    assert result["full_name"] == "John Doe"

def test_extract_text_mock(resume_service):
    # Mock extract_text which uses PdfReader/Document
    content = b"pdf content"
    with patch.object(resume_service, "_extract_pdf_text", return_value=("Extracted PDF Text", None)):
        text, err = resume_service.extract_text(content, "test.pdf", "application/pdf")
        assert text == "Extracted PDF Text"
        assert err is None

def test_extract_phone_number(resume_service):
    text = "My phone is +91-9876543210"
    phone = resume_service._extract_phone_number(text)
    assert "9876543210" in phone

def test_extract_aadhaar(resume_service):
    text = "Aadhaar: 1234 5678 9012"
    aadhaar = resume_service._extract_aadhaar(text)
    assert "123456789012" in aadhaar
