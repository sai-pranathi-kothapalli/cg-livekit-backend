import pytest
from app.utils.exceptions import (
    ApplicationError,
    ConfigurationError,
    ValidationError,
    ServiceError,
    RepositoryError,
    AgentError,
    SupabaseUnavailableError
)

def test_application_error():
    exc = ApplicationError("message", "CODE", 404)
    assert str(exc) == "message"
    assert exc.error_code == "CODE"
    assert exc.status_code == 404

def test_validation_error():
    exc = ValidationError("invalid", "email")
    assert exc.status_code == 400
    assert exc.error_code == "VALIDATION_ERROR_EMAIL"
    assert exc.field == "email"

def test_service_error():
    exc = ServiceError("failed", "Supabase")
    assert exc.status_code == 503
    assert exc.error_code == "SERVICE_ERROR_SUPABASE"

def test_agent_error():
    exc = AgentError("crash", "LiveKit")
    assert exc.status_code == 503
    assert exc.error_code == "AGENT_ERROR_LIVEKIT"

def test_supabase_unavailable():
    exc = SupabaseUnavailableError()
    assert exc.status_code == 503
    assert exc.error_code == "SERVICE_UNAVAILABLE"
