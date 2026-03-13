import pytest
from pydantic import ValidationError
from app.schemas.admin import (
    JobDescriptionRequest,
    JobDescriptionResponse,
    CandidateRegistrationRequest,
    BulkRegistrationResponse,
    ManagerRegistrationRequest,
    ManagerResponse,
    SystemInstructionsRequest,
    SystemInstructionsResponse
)

def test_job_description_request():
    valid_data = {"context": "Python developer role"}
    model = JobDescriptionRequest(**valid_data)
    assert model.context == valid_data["context"]
    
    with pytest.raises(ValidationError):
        JobDescriptionRequest()

def test_candidate_registration_request():
    valid_data = {
        "name": "Alice",
        "email": "alice@example.com",
        "phone": "9876543210",
        "datetime": "2026-02-20T10:00:00+05:30"
    }
    model = CandidateRegistrationRequest(**valid_data)
    assert model.name == "Alice"
    assert model.email == "alice@example.com"
    
    with pytest.raises(ValidationError):
        CandidateRegistrationRequest(name="Alice", email="not-an-email")

def test_manager_response():
    valid_data = {
        "id": "mgr-1",
        "email": "mgr@example.com",
        "name": "Bob",
        "role": "manager"
    }
    model = ManagerResponse(**valid_data)
    assert model.id == "mgr-1"
    assert model.role == "manager"
    
    # Defaults
    minimal_data = {"id": "mgr-2", "email": "mgr2@example.com"}
    model2 = ManagerResponse(**minimal_data)
    assert model2.role == "manager"
    assert model2.name is None

def test_system_instructions_request():
    valid_data = {"instructions": "Tell a joke."}
    model = SystemInstructionsRequest(**valid_data)
    assert model.instructions == "Tell a joke."
    
    with pytest.raises(ValidationError):
        SystemInstructionsRequest()
