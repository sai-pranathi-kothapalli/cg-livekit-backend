import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from contextlib import ExitStack
from app.api.main import app
from app.services import container
from app.utils.auth_dependencies import get_current_admin, get_current_student, get_optional_student

@pytest.fixture
def mock_supabase():
    with patch("app.db.supabase.get_supabase") as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        yield mock_client

@pytest.fixture(autouse=True)
def mock_container_services():
    with ExitStack() as stack:
        # Patch the methods on the existing instances in container.py
        mock_objects = {
            "booking": [
                (container.booking_service, 'create_booking'),
                (container.booking_service, 'get_booking'),
                (container.booking_service, 'get_all_bookings'),
                (container.booking_service, 'get_bookings_by_user_id'),
                (container.booking_service, 'get_bookings_by_email'),
                (container.booking_service, 'get_user_bookings'),
                (container.booking_service, 'upload_application_to_storage'),
                (container.booking_service, 'update_booking'),
            ],
            "auth": [
                (container.auth_service, 'register_manager'),
                (container.auth_service, 'authenticate_unified'),
                (container.auth_service, 'change_user_password'),
                (container.auth_service, 'reset_password'),
                (container.auth_service, 'register_student'),
                (container.auth_service, 'generate_token'),
                (container.auth_service, 'get_user_by_email'),
                (container.auth_service, 'generate_temporary_password'),
            ],
            "admin": [
                (container.admin_service, 'authenticate'),
                (container.admin_service, 'generate_token'),
                (container.admin_service, 'delete_student_account_by_email'),
                (container.admin_service, 'delete_student_by_email'),
            ],
            "system_instructions": [
                (container.system_instructions_service, 'get_system_instructions'),
                (container.system_instructions_service, 'update_system_instructions'),
            ],
            "user": [
                (container.user_service, 'get_user'),
                (container.user_service, 'update_user'),
                (container.user_service, 'get_user_by_email'),
                (container.user_service, 'create_user'),
                (container.user_service, 'get_all_users'),
                (container.user_service, 'delete_user'),
            ],
            "slot": [
                (container.slot_service, 'get_slot'),
                (container.slot_service, 'get_slot_by_datetime'),
                (container.slot_service, 'create_slot'),
                (container.slot_service, 'get_all_slots'),
                (container.slot_service, 'update_slot'),
                (container.slot_service, 'delete_slot'),
                (container.slot_service, 'get_available_slots'),
                (container.slot_service, 'create_day_slots'),
                (container.slot_service, 'increment_booking_count'),
                (container.slot_service, 'release_slots_for_user'),
            ],
            "email": [
                (container.email_service, 'send_interview_email'),
                (container.email_service, 'send_enrollment_email', True),
            ],
            "evaluation": [
                (container.evaluation_service, 'get_evaluation'),
                (container.evaluation_service, 'get_evaluation_by_token'),
                (container.evaluation_service, 'get_evaluations_for_bookings'),
                (container.evaluation_service, 'calculate_evaluation_from_transcript'),
                (container.evaluation_service, 'get_student_analytics'),
                (container.evaluation_service, 'analyze_code', True), # True means async
                (container.evaluation_service, 'evaluate_answer', True),
                (container.evaluation_service, 'get_booking_tokens_with_evaluations'),
                (container.evaluation_service, 'delete_evaluations_by_booking_tokens'),
            ],
            "transcript": [
                (container.transcript_storage_service, 'get_transcript'),
                (container.transcript_storage_service, 'get_booking_tokens_with_transcripts'),
                (container.transcript_storage_service, 'delete_by_booking_tokens'),
            ],
            "resume": [
                (container.resume_service, 'validate_file'),
                (container.resume_service, 'extract_text'),
            ],
            "assignment": [
                (container.assignment_service, 'get_user_assignments'),
                (container.assignment_service, 'assign_slots_to_user'),
                (container.assignment_service, 'select_slot_for_user'),
                (container.assignment_service, 'cancel_other_assignments'),
                (container.assignment_service, 'get_assignments_by_email'),
            ]
        }
        
        # Mock LiveKit globally to avoid real API calls
        stack.enter_context(patch("app.api.interviews.livekit_api.LiveKitAPI", MagicMock()))
        stack.enter_context(patch("app.api.interviews.livekit_api.AccessToken", MagicMock()))
        
        # Apply all patches
        from unittest.mock import AsyncMock
        for key, targets in mock_objects.items():
            for target in targets:
                if len(target) == 3:
                    obj, method, is_async = target
                    stack.enter_context(patch.object(obj, method, AsyncMock(), create=True))
                else:
                    obj, method = target
                    stack.enter_context(patch.object(obj, method, MagicMock(), create=True))
        
        yield {
            "booking": container.booking_service,
            "auth": container.auth_service,
            "admin": container.admin_service,
            "system_instructions": container.system_instructions_service,
            "user": container.user_service,
            "slot": container.slot_service,
            "email": container.email_service,
            "evaluation": container.evaluation_service,
            "transcript": container.transcript_storage_service,
            "resume": container.resume_service,
            "assignment": container.assignment_service
        }

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def admin_user():
    return {"id": "admin-123", "role": "admin", "username": "admin"}

@pytest.fixture
def student_user():
    return {"id": "student-123", "role": "student", "email": "student@example.com"}

@pytest.fixture
def mock_admin_auth(client, admin_user):
    app.dependency_overrides[get_current_admin] = lambda: admin_user
    yield
    app.dependency_overrides.pop(get_current_admin, None)

@pytest.fixture
def mock_student_auth(client, student_user):
    app.dependency_overrides[get_current_student] = lambda: student_user
    app.dependency_overrides[get_optional_student] = lambda: student_user
    yield
    app.dependency_overrides.pop(get_current_student, None)
    app.dependency_overrides.pop(get_optional_student, None)
