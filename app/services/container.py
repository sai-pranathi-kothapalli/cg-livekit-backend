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

config = get_config()

# Initialize services
resume_service = ResumeService(config)
booking_service = BookingService(config)
email_service = EmailService(config)
system_instructions_service = SystemInstructionsService(config)
admin_service = AdminService(config)
auth_service = AuthService(config)
user_service = UserService(config)
slot_service = SlotService(config)
assignment_service = AssignmentService(config)
transcript_storage_service = TranscriptStorageService(config)
evaluation_service = EvaluationService(config)
