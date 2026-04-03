from app.config import get_config
from app.services.resume_service import ResumeService
from app.services.booking_service import BookingService
from app.services.email_service import EmailService
from app.services.system_instructions_service import SystemInstructionsService
from app.services.admin_service import AdminService
from app.services.auth_service import AuthService
from app.services.user_service import UserService
from app.services.slot_service import SlotService
from app.services.assignment_service import AssignmentService
from app.services.transcript_storage_service import TranscriptStorageService
from app.services.evaluation_service import EvaluationService
from app.services.otp_service import OTPService
from app.db.supabase import get_supabase
from app.utils.integration_auth import IntegrationAuth
from app.services.webhook_service import WebhookService

config = get_config()

# Initialize services
resume_service = ResumeService(config)
slot_service = SlotService(config)
booking_service = BookingService(config, slot_service)
email_service = EmailService(config)
system_instructions_service = SystemInstructionsService(config)
admin_service = AdminService(config)
auth_service = AuthService(config)
user_service = UserService(config)
assignment_service = AssignmentService(config)
transcript_storage_service = TranscriptStorageService(config)
evaluation_service = EvaluationService(config)
otp_service = OTPService(config)
integration_auth = IntegrationAuth(get_supabase())
webhook_service = WebhookService(get_supabase())
