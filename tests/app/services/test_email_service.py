import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime
from app.services.email_service import EmailService

@pytest.fixture
def email_service():
    from app.config import get_config
    config = get_config()
    # Ensure it's enabled for most tests
    config.smtp.host = "smtp.example.com"
    config.smtp.user = "user"
    config.smtp.password = "pass"
    return EmailService(config)

@pytest.mark.asyncio
async def test_send_interview_email_success(email_service):
    with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        success, error = await email_service.send_interview_email(
            to_email="test@example.com",
            name="Test User",
            interview_url="http://join.me",
            scheduled_at=datetime.now()
        )
        assert success is True
        assert error is None
        assert mock_send.called

@pytest.mark.asyncio
async def test_send_interview_email_disabled():
    from app.config import get_config
    config = get_config()
    config.smtp.host = None # Disable
    service = EmailService(config)
    
    success, error = await service.send_interview_email(
        to_email="test@example.com",
        name="Test",
        interview_url="url",
        scheduled_at=datetime.now()
    )
    assert success is False
    assert "not configured" in error

@pytest.mark.asyncio
async def test_send_enrollment_email_success(email_service):
    with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        success, error = await email_service.send_enrollment_email(
            to_email="test@example.com",
            name="Test User",
            email="test@example.com",
            temporary_password="temp123"
        )
        assert success is True
        assert error is None
        assert mock_send.called
