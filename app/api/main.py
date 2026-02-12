"""
FastAPI Application

HTTP API server for application upload and interview scheduling.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, status, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
# bson removed - using Supabase
from pydantic import BaseModel, EmailStr
from urllib.parse import urlparse
import asyncio
import random
import json
import pandas as pd
from io import BytesIO
import os
from urllib.parse import urlparse

from livekit import api as livekit_api
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import Config, get_config
from app.db.supabase import get_supabase
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
from app.schemas.admin import (
    JobDescriptionRequest,
    JobDescriptionResponse,
    CandidateRegistrationRequest,
    BulkRegistrationResponse,
    ManagerRegistrationRequest,
    ManagerResponse,
    SystemInstructionsRequest,
    SystemInstructionsResponse,
)
from app.schemas.users import (
    EnrollUserRequest,
    UpdateUserRequest,
    UserResponse,
    InterviewSummary,
    UserDetailResponse,
    BulkEnrollResponse as UserBulkEnrollResponse,
    ScheduleInterviewForUserRequest,
    BulkScheduleInterviewResponse,
)
from app.schemas.slots import CreateSlotRequest, UpdateSlotRequest, SlotResponse, CreateDaySlotsRequest, CreateDaySlotsResponse
from app.schemas.bookings import (
    ScheduleInterviewRequest,
    ScheduleInterviewResponse,
    BookingResponse,
    PaginatedCandidatesResponse,
)
from app.schemas.interviews import (
    EvaluationResponse,
    RoundEvaluationResponse,
    ConnectionDetailsRequest,
    ConnectionDetailsResponse,
)
from app.schemas.student_status import (
    AssignmentResponse,
    SelectSlotRequest,
    MyInterviewResponse,
)
from app.utils.logger import get_logger
from app.utils.auth_dependencies import get_current_admin, get_current_student, get_optional_student
from app.utils.datetime_utils import IST, get_now_ist, to_ist, parse_datetime_safe

logger = get_logger(__name__)
config = get_config()

# Rate limiter for auth endpoints (limit by IP)
limiter = Limiter(key_func=get_remote_address)

# Create FastAPI app
app = FastAPI(
    title="Interview Scheduling API",
    description="API for application upload and interview scheduling",
    version="1.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware: with allow_credentials=True, origins cannot be "*" (must be explicit).
# Include localhost (dev), common LAN origin, and cloudflared tunnel URLs.
_cors_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://192.168.1.13:3000",  # LAN access (e.g. from same network)
]
if config.server.frontend_url:
    _cors_origins.append(config.server.frontend_url.rstrip("/"))
# Extra origins from env (comma-separated), e.g. CORS_ORIGINS=http://192.168.1.5:3000,http://10.0.0.1:3000
_extra_origins = os.getenv("CORS_ORIGINS", "")
if _extra_origins:
    for o in _extra_origins.split(","):
        o = o.strip().rstrip("/")
        if o and o not in _cors_origins:
            _cors_origins.append(o)
# Allow cloudflare tunnels and any LAN IP (192.168.x.x, 10.x.x.x) with any port
_origin_regex = (
    r"https?://[a-z0-9-]+\.trycloudflare\.com|"
    r"https?://(192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3})(:\d+)?$"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

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


@app.on_event("startup")
async def startup_log_db():
    """Log Supabase connection status on startup."""
    try:
        client = get_supabase()
        logger.info("[API] Supabase client initialized successfully")
    except Exception as e:
        logger.warning(f"[API] Supabase initialization warning: {e}")


@app.get("/health")
async def health():
    """Liveness probe: returns 200 if the process is running."""
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    """Readiness probe: returns 200 if the app can serve traffic (e.g. DB reachable)."""
    try:
        client = get_supabase()
        # Quick check: query the users table
        client.table("users").select("id").limit(1).execute()
        return {"status": "ready"}
    except Exception as e:
        logger.warning(f"[API] Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Service not ready")


@app.get("/metrics", include_in_schema=False)
async def metrics():
    """Prometheus metrics for monitoring (RED, etc.)."""
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
    except Exception as e:
        logger.warning(f"[API] Metrics export failed: {e}")
        raise HTTPException(status_code=503, detail="Metrics not available")


# Helper function to get frontend URL from request dynamically
def get_frontend_url(request: Optional[Request] = None) -> str:
    """
    Get frontend URL from request origin/referer, fallback to config.
    
    Args:
        request: FastAPI Request object (optional)
        
    Returns:
        Frontend base URL (without trailing slash)
    """
    if request:
        # Try Origin header first (more reliable for CORS requests)
        origin = request.headers.get('Origin')
        if origin:
            parsed = urlparse(origin)
            base_url = f"{parsed.scheme}://{parsed.netloc}".rstrip('/')
            if base_url:
                logger.debug(f"[API] Using frontend URL from Origin header: {base_url}")
                return base_url
        
        # Fallback to Referer header
        referer = request.headers.get('Referer')
        if referer:
            parsed = urlparse(referer)
            base_url = f"{parsed.scheme}://{parsed.netloc}".rstrip('/')
            if base_url:
                logger.debug(f"[API] Using frontend URL from Referer header: {base_url}")
                return base_url
    
    # Final fallback to config
    fallback_url = config.server.frontend_url.rstrip('/') if config.server.frontend_url else ''
    if fallback_url:
        logger.debug(f"[API] Using frontend URL from config: {fallback_url}")
    return fallback_url

# Helper function for datetime validation
def validate_scheduled_time(scheduled_at: datetime) -> None:
    """
    Validate that scheduled time is at least 5 minutes in the future.
    
    Args:
        scheduled_at: Scheduled datetime to validate
        
    Raises:
        HTTPException: If scheduled time is invalid
    """
    now = get_now_ist()
    five_minutes_from_now = now + timedelta(minutes=5)
    
    if scheduled_at <= five_minutes_from_now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scheduled time must be at least 5 minutes from now"
        )


# Admin Models
class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    error: Optional[str] = None


# User Models
class RRBApplicationRequest(BaseModel):
    # Personal Details
    fullName: str
    post: str
    category: str
    dateOfBirth: str
    gender: str
    maritalStatus: str
    aadhaarNumber: str
    panNumber: str
    fatherName: str
    motherName: str
    spouseName: Optional[str] = None
    
    # Address
    correspondenceAddress1: str
    correspondenceAddress2: Optional[str] = None
    correspondenceAddress3: Optional[str] = None
    correspondenceState: str
    correspondenceDistrict: str
    correspondencePincode: str
    permanentAddress1: str
    permanentAddress2: Optional[str] = None
    permanentAddress3: Optional[str] = None
    permanentState: str
    permanentDistrict: str
    permanentPincode: str
    
    # Contact
    mobileNumber: str
    alternativeNumber: Optional[str] = None
    email: EmailStr
    
    # Educational Qualification
    sscBoard: str
    sscPassingDate: str
    sscPercentage: str
    sscClass: str
    graduationDegree: str
    graduationCollege: str
    graduationSpecialization: Optional[str] = None
    graduationPassingDate: str
    graduationPercentage: str
    graduationClass: str
    
    # Other Details
    religion: str
    religiousMinority: bool = False
    localLanguageStudied: bool = False
    localLanguageName: Optional[str] = None
    computerKnowledge: bool = False
    computerKnowledgeDetails: Optional[str] = None
    languagesKnown: Dict[str, Dict[str, bool]]
    
    # Application Specific
    stateApplyingFor: str
    regionalRuralBank: str
    examCenterPreference1: str
    examCenterPreference2: Optional[str] = None
    mediumOfPaper: str
    
    # Interview Schedule
    interviewDate: str
    interviewHour: str
    interviewMinute: str
    interviewAmpm: str


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "service": "interview-scheduling-api"}


# ==================== Authentication Endpoints ====================

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    user: Optional[Dict[str, Any]] = None
    must_change_password: Optional[bool] = None
    error: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    email: str
    old_password: str
    new_password: str


class ResetPasswordRequest(BaseModel):
    email: str
    new_password: str


class InterviewAccessConfigResponse(BaseModel):
    """Public config: whether interview link requires login (for frontend to show/hide login gate)."""
    require_login_for_interview: bool


@app.get("/api/public/interview-config", response_model=InterviewAccessConfigResponse)
async def get_interview_access_config():
    """
    Public endpoint (no auth). Returns whether interview links require login.
    Frontend uses this to decide whether to redirect to login or allow direct access.
    """
    return InterviewAccessConfigResponse(
        require_login_for_interview=config.REQUIRE_LOGIN_FOR_INTERVIEW,
    )


@app.get("/api/public/interview-config", response_model=InterviewAccessConfigResponse)
async def get_interview_access_config():
    """
    Public endpoint (no auth). Returns whether interview links require login.
    Frontend uses this to decide whether to redirect to login or allow direct access.
    """
    return InterviewAccessConfigResponse(
        require_login_for_interview=config.REQUIRE_LOGIN_FOR_INTERVIEW,
    )


class StudentRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    phone: Optional[str] = None


@app.post("/api/schedule-interview", response_model=ScheduleInterviewResponse)
async def schedule_interview(request: ScheduleInterviewRequest, http_request: Request):
    """
    Schedule an interview.
    
    Creates a booking in the database and sends confirmation email.
    """
    try:
        logger.info(f"[API] Received schedule request: {request.email} at {request.datetime}")
    except Exception:
        # function body moved to app.api.bookings; kept for backward import compatibility
        raise


@app.get("/api/booking/{token}", response_model=BookingResponse)
async def get_booking(
    token: str,
    current_student: Optional[dict] = Depends(get_optional_student)
):
    """
    Get booking details by token.
    """
    try:
        booking_service.get_booking(token)
    except Exception:
        # actual implementation lives in app.api.bookings
        raise


@app.get("/api/files/{file_id}")
async def serve_file(file_id: str):
    """Serve uploaded application file from Supabase Storage."""
    try:
        client = get_supabase()
        # Get public URL from Supabase Storage
        public_url = client.storage.from_("resumes").get_public_url(file_id)
        if public_url:
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url=public_url)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"[API] File not found or error: {file_id} {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")


@app.get("/api/evaluation/{token}", response_model=EvaluationResponse)
async def get_evaluation(token: str):
    """
    Get comprehensive evaluation data for an interview.
    
    Returns:
        Complete evaluation including transcript, metrics, rounds, and scores
    """
    try:
        # Get booking
        booking = booking_service.get_booking(token)
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview not found"
            )
        
        # Get transcript
        transcript = transcript_storage_service.get_transcript(token)
        
        # Get evaluation (may be preliminary with no score yet)
        evaluation = evaluation_service.get_evaluation(token)
        
        # If evaluation is missing OR still in preliminary "analysis in progress" state,
        # recalculate a full evaluation from the transcript.
        if transcript and (not evaluation or evaluation.get("overall_score") is None):
            logger.info(f"[API] Evaluation missing or incomplete for {token}, recalculating from transcript...")
            evaluation_id = evaluation_service.calculate_evaluation_from_transcript(
                booking_token=token,
                room_name=booking.get('room_name') or f"room_{token}",
                transcript=transcript,
            )
            if evaluation_id:
                evaluation = evaluation_service.get_evaluation(token)
        
        # Format response
        candidate_data = {
            "name": booking.get("name", ""),
            "email": booking.get("email", ""),
            "application_form": {
                "text": booking.get("application_text"),
                "url": booking.get("application_url"),
            } if booking.get("application_text") else None,
        }
        
        # Build interview metrics
        interview_metrics = None
        if evaluation:
            interview_metrics = {
                "duration_minutes": evaluation.get("duration_minutes"),
                "rounds_completed": evaluation.get("rounds_completed", 0),
                "total_questions": evaluation.get("total_questions", 0),
                "average_response_time": None,  # Can be calculated from transcript timestamps
            }
        
        # Format rounds
        rounds = []
        if evaluation and evaluation.get("rounds"):
            for round_data in evaluation["rounds"]:
                rounds.append(RoundEvaluationResponse(
                    round_number=round_data.get("round_number", 0),
                    round_name=round_data.get("round_name", ""),
                    questions_asked=round_data.get("questions_asked", 0),
                    average_rating=round_data.get("average_rating"),
                    time_spent_minutes=round_data.get("time_spent_minutes"),
                    time_target_minutes=round_data.get("time_target_minutes"),
                    topics_covered=round_data.get("topics_covered", []),
                    performance_summary=round_data.get("performance_summary"),
                    response_ratings=round_data.get("response_ratings", []),
                ))
        
        return EvaluationResponse(
            booking=BookingResponse(**booking),
            candidate=candidate_data,
            interview_metrics=interview_metrics,
            rounds=rounds,
            overall_score=evaluation.get("overall_score") if evaluation else None,
            strengths=evaluation.get("strengths", []) if evaluation else [],
            areas_for_improvement=evaluation.get("areas_for_improvement", []) if evaluation else [],
            transcript=transcript,
            communication_quality=evaluation.get("communication_quality") if evaluation else None,
            technical_knowledge=evaluation.get("technical_knowledge") if evaluation else None,
            problem_solving=evaluation.get("problem_solving") if evaluation else None,
            overall_feedback=evaluation.get("overall_feedback") if evaluation else None,
            token_usage=evaluation.get("token_usage") if evaluation else None,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to fetch evaluation: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@app.post("/api/connection-details", response_model=ConnectionDetailsResponse)
async def connection_details(
    request: ConnectionDetailsRequest,
    current_student: Optional[dict] = Depends(get_optional_student)
):
    """
    Generate LiveKit connection details for interview.
    
    Creates a participant token and room configuration with agent.
    
    If a token is provided, requires student authentication and verifies ownership.
    """
    try:
        # Validate LiveKit config
        if not config.livekit.url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="LIVEKIT_URL is not configured"
            )
        if not config.livekit.api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="LIVEKIT_API_KEY is not configured"
            )
        if not config.livekit.api_secret:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="LIVEKIT_API_SECRET is not configured"
            )
        
        # Extract agent name from request
        logger.debug(f"[API] 📥 Received connection-details request:")
        logger.debug(f"[API]   room_config: {request.room_config}")
        logger.debug(f"[API]   token: {request.token if request.token else 'None'}")
        logger.info(f"[API] 📥 Received connection-details request:")
        logger.info(f"   room_config: {request.room_config}")
        logger.info(f"   token: {request.token if request.token else 'None'}")
        
        agent_name = None
        if request.room_config and isinstance(request.room_config, dict):
            agents = request.room_config.get("agents", [])
            logger.info(f"   Found agents array: {agents}")
            if agents and len(agents) > 0:
                first_agent_dict = agents[0]
                logger.debug(f"[API] 🔍 First agent dict from request: {first_agent_dict}")
                logger.debug(f"[API]   Keys in agent dict: {list(first_agent_dict.keys())}")
                logger.info(f"[API] 🔍 First agent dict from request: {first_agent_dict}")
                logger.info(f"[API]   Keys in agent dict: {list(first_agent_dict.keys())}")
                
                # Try both snake_case and camelCase
                agent_name = first_agent_dict.get("agent_name") or first_agent_dict.get("agentName")
                if not agent_name:
                    logger.debug(f"[API]   ⚠️  Neither 'agent_name' nor 'agentName' found in dict!")
                    logger.debug(f"[API]   Available keys: {list(first_agent_dict.keys())}")
                    logger.warning(f"[API]   ⚠️  Neither 'agent_name' nor 'agentName' found in dict!")
                else:
                    logger.debug(f"[API]   ✅ Extracted agent_name: '{agent_name}'")
                    logger.info(f"[API]   ✅ Extracted agent_name: '{agent_name}'")
        
        # Use default agent name from config if not provided
        if not agent_name:
            agent_name = config.livekit.agent_name
            logger.info(f"   Using default agent_name from config: '{agent_name}'")
        else:
            logger.info(f"   ✅ Using agent_name: '{agent_name}'")
        
        # If token is provided, fetch booking to get application text and validate time window
        application_text = None
        if request.token:
            # Optional: Require student login to open interview link (configurable)
            if config.REQUIRE_LOGIN_FOR_INTERVIEW:
                if not current_student:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication required to access interview. Please log in as a student."
                    )
            else:
                logger.info("[API] Interview link open to anyone (REQUIRE_LOGIN_FOR_INTERVIEW=false)")
            
            try:
                booking = booking_service.get_booking(request.token)
                if not booking:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Interview not found"
                    )
                
                # Optional: Verify that the booking belongs to the logged-in student (only when login required)
                if config.REQUIRE_LOGIN_FOR_INTERVIEW and current_student:
                    booking_user_id = booking.get('user_id')
                    if booking_user_id:
                        # Verify that the booking belongs to the logged-in student
                        auth_user_id = current_student.get('id')
                        if booking_user_id != auth_user_id:
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail="You do not have permission to access this interview"
                            )
                        
                        logger.info(f"[API] ✅ Verified interview ownership: booking.user_id={booking_user_id}, student.user_id={auth_user_id}")
                    else:
                        # If booking has no user_id, allow access (for backward compatibility with old bookings)
                        logger.warning(f"[API] ⚠️  Booking {request.token} has no user_id - allowing access for backward compatibility")
                
                # Validate interview time window (can only join during the scheduled interview time)
                if booking.get("scheduled_at"):
                    scheduled_at_str = booking["scheduled_at"]
                    # Parse scheduled_at - handle UTC or IST format properly
                    try:
                        scheduled_at = parse_datetime_safe(scheduled_at_str)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"[API] Failed to parse scheduled_at: {e}, using fallback")
                        # Fallback: try parsing without timezone
                        naive_dt = datetime.fromisoformat(scheduled_at_str.replace('Z', '').replace('+00:00', ''))
                        scheduled_at = naive_dt.replace(tzinfo=IST)
                    
                    now = get_now_ist()
                    
                    # Get interview duration from slot if available, otherwise default to 30 minutes
                    duration_minutes = 30  # Default duration
                    slot_id = booking.get("slot_id")
                    if slot_id:
                        try:
                            slot = slot_service.get_slot(slot_id)
                            logger.info(f"[API] Slot retrieved for connection-details: slot_id={slot_id}, duration_minutes={slot.get('duration_minutes') if slot else 'N/A'}, slot_keys={list(slot.keys()) if slot else 'N/A'}")
                            if slot and slot.get("duration_minutes"):
                                duration_minutes = slot["duration_minutes"]
                                logger.info(f"[API] Using duration_minutes from slot: {duration_minutes} minutes")
                            elif slot:
                                # Calculate duration from slot start and end times if available
                                slot_datetime_str = slot.get("slot_datetime")
                                if slot_datetime_str:
                                    try:
                                        slot_start = parse_datetime_safe(slot_datetime_str)
                                        
                                        # Get end time from slot or calculate
                                        slot_end_str = slot.get("end_time")
                                        if slot_end_str:
                                            slot_end = parse_datetime_safe(slot_end_str)
                                            duration_minutes = int((slot_end - slot_start).total_seconds() / 60)
                                            logger.info(f"[API] Calculated duration_minutes from slot times: {duration_minutes} minutes")
                                    except (ValueError, TypeError) as e:
                                        logger.warning(f"[API] Failed to parse slot times: {e}")
                                        pass
                            else:
                                logger.warning(f"[API] Slot not found for slot_id: {slot_id}")
                        except Exception as e:
                            logger.warning(f"[API] Failed to get slot duration: {e}")
                    else:
                        logger.warning(f"[API] No slot_id in booking, using default duration: 30 minutes")
                    
                    interview_end_time = scheduled_at + timedelta(minutes=duration_minutes)
                    
                    # Check if current time is before scheduled time
                    if now < scheduled_at:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Interview has not started yet. Scheduled time: {scheduled_at.strftime('%Y-%m-%d %H:%M:%S IST')}"
                        )
                    
                    # Check if current time is after interview end time
                    if now > interview_end_time:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Interview window has expired. The interview was scheduled from {scheduled_at.strftime('%Y-%m-%d %H:%M:%S IST')} to {interview_end_time.strftime('%Y-%m-%d %H:%M:%S IST')}."
                        )
                    
                    logger.info(f"[API] Interview time window validated: scheduled_at={scheduled_at}, end_time={interview_end_time}, now={now}, duration={duration_minutes} minutes")
                
                if booking.get("application_text"):
                    application_text = booking["application_text"]
                    logger.info(f"[API] Found application text for token {request.token} ({len(application_text)} chars)")
            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"[API] Failed to fetch booking for application: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to validate interview: {str(e)}"
                )
        
        # Generate room details - use interview_<token> so the worker can save transcripts to MongoDB
        participant_name = "user"
        participant_identity = f"voice_assistant_user_{random.randint(1, 99999)}"
        booking_token = getattr(request, "token", None) or ""
        room_name = f"interview_{booking_token}" if booking_token else f"voice_assistant_room_{random.randint(1, 99999)}"
        
        # Create room metadata (application_text + booking_token for worker transcript storage)
        room_metadata_dict = {}
        if application_text:
            room_metadata_dict["application_text"] = application_text
        if booking_token:
            room_metadata_dict["booking_token"] = booking_token
            room_metadata_dict["token"] = booking_token
        room_metadata = json.dumps(room_metadata_dict) if room_metadata_dict else None
        
        # Create LiveKit AccessToken
        token = livekit_api.AccessToken(
            config.livekit.api_key,
            config.livekit.api_secret
        )
        token.with_identity(participant_identity)
        token.with_name(participant_name)
        token.with_ttl(timedelta(minutes=90))  # Increased to 90 minutes for 30+ min interviews
        
        # Add video grant (permissions)
        grant = livekit_api.VideoGrants(
            room=room_name,
            room_join=True,
            can_publish=True,
            can_publish_data=True,
            can_subscribe=True,
        )
        token.with_grants(grant)
        
        # [FIX] Force agent name to match what's in worker/agents/
        agent_name = "my-interviewer"
        logger.info(f"   [FIX] Using agent_name: '{agent_name}'")
        logger.debug(f"[API]   [FIX] Using agent_name: '{agent_name}'")
        
        # Set room configuration with agent
        if agent_name:
            logger.debug(f"[API] 🔧 Creating RoomConfiguration with agent dispatch:")
            logger.debug(f"[API] Agent Name: '{agent_name}'")
            logger.info(f"[API] 🔧 Creating RoomConfiguration with agent dispatch:")
            logger.info(f"   Agent Name: '{agent_name}'")
            room_config = livekit_api.RoomConfiguration()
            room_agent_dispatch = room_config.agents.add()
            room_agent_dispatch.agent_name = agent_name
            logger.debug(f"[API] RoomConfiguration created with agent: '{room_agent_dispatch.agent_name}'")
            
            if room_metadata:
                room_config.metadata = room_metadata
                logger.info(f"   Room metadata: {room_metadata[:100]}...")
            token.with_room_config(room_config)
            logger.debug(f"[API] ✅ RoomConfiguration attached to token")
            logger.info(f"[API] ✅ RoomConfiguration set with agent dispatch")
        else:
            logger.debug(f"[API] ⚠️  No agent_name provided - agent will NOT be dispatched!")
            logger.warning(f"[API] ⚠️  No agent_name provided - agent will NOT be dispatched!")
        
        # Generate JWT token
        participant_token = token.to_jwt()
        
        # Debug: Comprehensive token inspection
        try:
            import jwt
            decoded = jwt.decode(participant_token, options={"verify_signature": False})
            
            logger.debug(f"\n{'='*60}")
            logger.debug(f"[API] 🔍 TOKEN DEBUG - COMPREHENSIVE INSPECTION")
            logger.debug(f"{'='*60}")
            logger.info(f"[API] 🔍 TOKEN DEBUG - COMPREHENSIVE INSPECTION")
            
            # Show all token keys
            logger.debug(f"[API]   Token keys: {list(decoded.keys())}")
            logger.info(f"[API]   Token keys: {list(decoded.keys())}")
            
            # Check for roomConfig
            if "roomConfig" in decoded:
                logger.debug(f"[API]   ✅ roomConfig found in token!")
                logger.info(f"[API]   ✅ roomConfig found in token!")
                room_config_data = decoded.get('roomConfig', {})
                logger.debug(f"[API]   roomConfig content: {room_config_data}")
                logger.info(f"[API]   roomConfig content: {room_config_data}")
                
                # Verify agent name is in roomConfig
                if isinstance(room_config_data, dict):
                    agents = room_config_data.get('agents', [])
                    logger.debug(f"[API]   Agents array: {agents}")
                    logger.info(f"[API]   Agents array: {agents}")
                    
                    if agents and len(agents) > 0:
                        first_agent_in_token = agents[0]
                        logger.debug(f"[API]   🔍 First agent in token: {first_agent_in_token}")
                        logger.debug(f"[API]   🔍 Agent keys in token: {list(first_agent_in_token.keys()) if isinstance(first_agent_in_token, dict) else 'NOT A DICT'}")
                        logger.info(f"[API]   🔍 First agent in token: {first_agent_in_token}")
                        
                        # Check both camelCase and snake_case
                        agent_name_in_token_camel = first_agent_in_token.get('agentName', '') if isinstance(first_agent_in_token, dict) else ''
                        agent_name_in_token_snake = first_agent_in_token.get('agent_name', '') if isinstance(first_agent_in_token, dict) else ''
                        
                        agent_name_in_token = agent_name_in_token_camel or agent_name_in_token_snake
                        
                        logger.debug(f"[API]   Agent name (agentName): '{agent_name_in_token_camel}'")
                        logger.debug(f"[API]   Agent name (agent_name): '{agent_name_in_token_snake}'")
                        logger.debug(f"[API]   ✅ Agent name in token (final): '{agent_name_in_token}'")
                        logger.info(f"[API]   Agent name (agentName): '{agent_name_in_token_camel}'")
                        logger.info(f"[API]   Agent name (agent_name): '{agent_name_in_token_snake}'")
                        logger.info(f"[API]   ✅ Agent name in token (final): '{agent_name_in_token}'")
                        
                        # Compare with expected
                        logger.debug(f"[API]   Expected agent name: '{agent_name}'")
                        logger.info(f"[API]   Expected agent name: '{agent_name}'")
                        
                        if agent_name_in_token == agent_name:
                            logger.debug(f"[API]   ✅✅ MATCH! Agent name matches!")
                            logger.info(f"[API]   ✅✅ MATCH! Agent name matches!")
                        else:
                            logger.debug(f"[API]   ❌❌ MISMATCH! Expected: '{agent_name}', Got: '{agent_name_in_token}'")
                            logger.debug(f"[API]   ❌❌ Length comparison - Expected: {len(agent_name)}, Got: {len(agent_name_in_token)}")
                            logger.debug(f"[API]   ❌❌ Character-by-character:")
                            for i, (exp_char, got_char) in enumerate(zip(agent_name, agent_name_in_token)):
                                if exp_char != got_char:
                                    logger.debug(f"[API]     Position {i}: Expected '{exp_char}' (ord={ord(exp_char)}), Got '{got_char}' (ord={ord(got_char)})")
                            logger.warning(f"[API]   ❌❌ MISMATCH! Expected: '{agent_name}', Got: '{agent_name_in_token}'")
                    else:
                        logger.debug(f"[API]   ❌ No agents in roomConfig!")
                        logger.warning(f"[API]   ❌ No agents in roomConfig!")
                else:
                    logger.debug(f"[API]   ⚠️  roomConfig is not a dict: {type(room_config_data)}")
                    logger.warning(f"[API]   ⚠️  roomConfig is not a dict: {type(room_config_data)}")
            elif "grants" in decoded:
                logger.debug(f"[API]   ⚠️  roomConfig not found, but grants exist")
                logger.debug(f"[API]   Grants: {decoded.get('grants', {})}")
                logger.info(f"[API]   ⚠️  roomConfig not found, but grants exist")
                logger.info(f"[API]   Grants: {decoded.get('grants', {})}")
            else:
                logger.debug(f"[API]   ❌❌ CRITICAL: roomConfig NOT in token!")
                logger.debug(f"[API]   Available keys: {list(decoded.keys())}")
                logger.error(f"[API]   ❌❌ CRITICAL: roomConfig NOT in token!")
                logger.error(f"[API]   Available keys: {list(decoded.keys())}")
            
            logger.debug(f"{'='*60}\n")
            logger.info(f"[API] Token debug complete")
            
        except Exception as e:
            logger.debug(f"\n[API] ❌ Error decoding token: {e}")
            logger.error(f"[API] ❌ Error decoding token: {e}", exc_info=True)
        
        logger.debug(f"[API] ✅ Generated connection details:")
        logger.debug(f"[API]   Server URL: {config.livekit.url}")
        logger.debug(f"[API]   Room Name: {room_name}")
        logger.debug(f"[API]   Participant Name: {participant_name}")
        logger.debug(f"[API]   Agent Name: {agent_name}")
        logger.debug(f"[API]   Token Length: {len(participant_token)} chars")
        logger.info(f"[API] ✅ Generated connection details:")
        logger.info(f"   Server URL: {config.livekit.url}")
        logger.info(f"   Room Name: {room_name}")
        logger.info(f"   Participant Name: {participant_name}")
        logger.info(f"   Agent Name: {agent_name}")
        logger.info(f"   Token Length: {len(participant_token)} chars")
        
        # Summary before return
        logger.debug(f"\n{'='*60}")
        logger.debug(f"[API] 📊 CONNECTION DETAILS SUMMARY")
        logger.debug(f"{'='*60}")
        logger.debug(f"[API]   Room Name: {room_name}")
        logger.debug(f"[API]   Agent Name (extracted): '{agent_name}'")
        logger.debug(f"[API]   Agent Name (config): '{config.livekit.agent_name}'")
        logger.debug(f"[API]   Agent Name Match: {'✅ YES' if agent_name == config.livekit.agent_name else '❌ NO'}")
        logger.debug(f"[API]   RoomConfig Attached: {'✅ YES' if agent_name else '❌ NO (no agent_name)'}")
        logger.debug(f"{'='*60}\n")
        logger.info(f"[API] 📊 Connection details summary logged")
        
        return ConnectionDetailsResponse(
            serverUrl=config.livekit.url,
            roomName=room_name,
            participantName=participant_name,
            participantToken=participant_token,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to generate connection details: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


# ==================== Admin Endpoints ====================

@app.get("/api/admin/job-description", response_model=JobDescriptionResponse)
async def get_job_description(current_admin: dict = Depends(get_current_admin)):
    """
    Get current job description / system instructions from database.
    Requires admin authentication.
    """
    try:
        data = system_instructions_service.get_system_instructions()
        return JobDescriptionResponse(context=data.get("instructions", ""))
    except Exception as e:
        logger.error(f"[API] Error fetching system instructions: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch system instructions: {str(e)}"
        )


@app.put("/api/admin/job-description", response_model=JobDescriptionResponse)
async def update_job_description(jd: JobDescriptionRequest, current_admin: dict = Depends(get_current_admin)):
    """
    Update job description / system instructions in database.
    Requires admin authentication.
    """
    try:
        ctx_len = len(jd.context or "")
        logger.info(f"[API] Updating system instructions (received length={ctx_len})")
        
        # Save to database
        updated = system_instructions_service.update_system_instructions(instructions=jd.context)
        
        logger.info(f"[API] ✅ System instructions saved to database")
        return JobDescriptionResponse(context=updated.get("instructions", ""))
    except Exception as e:
        logger.error(f"[API] Error updating system instructions: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update system instructions: {str(e)}"
        )


@app.post("/api/admin/managers", response_model=ManagerResponse)
async def enroll_manager(
    request: ManagerRegistrationRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Enroll a new manager. Auto-generates a temporary password.
    Requires admin authentication.
    """
    try:
        logger.info(f"[API] Enrolling manager: {request.email}")
        result = auth_service.register_manager(
            name=request.name,
            email=request.email,
        )
        return ManagerResponse(**result)
    except Exception as e:
        logger.error(f"[API] Error enrolling manager: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@app.get("/api/admin/managers", response_model=List[ManagerResponse])
async def list_managers(current_admin: dict = Depends(get_current_admin)):
    """
    List all managers.
    Requires admin authentication.
    """
    try:
        client = get_supabase()
        response = client.table("users").select("*").eq("role", "manager").order("created_at", desc=True).execute()
        managers: List[ManagerResponse] = []
        for m in (response.data or []):
            managers.append(ManagerResponse(
                id=m["id"],
                username=m.get("username", ""),
                email=m.get("email", ""),
                name=m.get("name"),
                role="manager",
                created_at=m.get("created_at"),
            ))
        return managers
    except Exception as e:
        logger.error(f"[API] Error listing managers: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list managers: {str(e)}"
        )


@app.delete("/api/admin/managers/{manager_id}")
async def delete_manager(manager_id: str, current_admin: dict = Depends(get_current_admin)):
    """
    Delete a manager by ID.
    Requires admin authentication.
    """
    try:
        client = get_supabase()
        client.table("users").delete().eq("id", manager_id).eq("role", "manager").execute()
        return {"success": True, "message": f"Manager {manager_id} deleted"}
    except Exception as e:
        logger.error(f"[API] Error deleting manager: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete manager: {str(e)}"
        )


@app.get("/api/admin/system-instructions", response_model=SystemInstructionsResponse)
async def get_system_instructions(current_admin: dict = Depends(get_current_admin)):
    """
    Get current system instructions.
    Requires admin authentication.
    """
    try:
        data = system_instructions_service.get_system_instructions()
        return SystemInstructionsResponse(instructions=data.get("instructions", ""))
    except Exception as e:
        logger.error(f"[API] Error fetching system instructions: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch system instructions: {str(e)}"
        )


@app.put("/api/admin/system-instructions", response_model=SystemInstructionsResponse)
async def update_system_instructions(
    request: SystemInstructionsRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Update system instructions.
    Requires admin authentication.
    """
    try:
        updated = system_instructions_service.update_system_instructions(
            instructions=request.instructions
        )
        logger.info(f"[API] ✅ System instructions updated (length={len(request.instructions)})")
        return SystemInstructionsResponse(instructions=updated.get("instructions", ""))
    except Exception as e:
        logger.error(f"[API] Error updating system instructions: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update system instructions: {str(e)}"
        )


@app.post("/api/admin/register-candidate", response_model=ScheduleInterviewResponse)
async def register_candidate(
    request: CandidateRegistrationRequest,
    http_request: Request,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Register a single candidate and schedule interview.
    Requires admin authentication.
    """
    try:
        logger.info(f"[API] Registering candidate: {request.email}")
        
        # Parse datetime
        try:
            if 'Z' in request.datetime or '+' in request.datetime or request.datetime.count('-') > 2:
                scheduled_at = datetime.fromisoformat(request.datetime.replace('Z', '+00:00'))
            else:
                naive_dt = datetime.fromisoformat(request.datetime)
                scheduled_at = naive_dt.replace(tzinfo=IST)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid datetime format. Expected ISO format."
            )
        
        # Validate scheduled time is at least 5 minutes in the future
        validate_scheduled_time(scheduled_at)
        
        # Create booking
        token = booking_service.create_booking(
            name=request.name,
            email=request.email,
            scheduled_at=scheduled_at,
            phone=request.phone,
            application_text=None,
            application_url=None,
        )
        
        # Generate interview URL - use request origin dynamically
        base_url = get_frontend_url(http_request)
        interview_url = f"{base_url}/interview/{token}" if base_url else f"/interview/{token}"
        
        # Send email
        email_sent = False
        email_error = None
        try:
            email_sent, email_error = await email_service.send_interview_email(
                to_email=request.email,
                name=request.name,
                interview_url=interview_url,
                scheduled_at=scheduled_at,
            )
        except Exception as e:
            email_error = str(e)
            logger.warning(f"[API] Email sending failed: {email_error}")
        
        logger.info(f"[API] ✅ Candidate registered: {interview_url}")
        
        return ScheduleInterviewResponse(
            ok=True,
            interviewUrl=interview_url,
            emailSent=email_sent,
            emailError=email_error,
        )
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to register candidate: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@app.post("/api/admin/bulk-register", response_model=BulkRegistrationResponse)
async def bulk_register(
    file: UploadFile = File(...),
    http_request: Request = None,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Bulk register candidates from Excel file.
    Requires admin authentication.
    
    Expected Excel format:
    - Columns: name, email, phone, datetime
    """
    try:
        logger.info(f"[API] Bulk registration request: {file.filename}")
        
        # Read Excel file
        file_content = await file.read()
        
        try:
            df = pd.read_excel(BytesIO(file_content))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid Excel file: {str(e)}"
            )
        
        # Validate required columns
        required_columns = ['name', 'email', 'phone', 'datetime']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required columns: {', '.join(missing_columns)}"
            )
        
        total = len(df)
        successful = 0
        failed = 0
        errors = []
        
        # Process each row
        for idx, row in df.iterrows():
            try:
                # Parse datetime - handle pandas Timestamp objects directly
                datetime_value = row['datetime']
                try:
                    if isinstance(datetime_value, pd.Timestamp):
                        # Convert pandas Timestamp to Python datetime, treating as naive IST time
                        naive_dt = datetime_value.to_pydatetime().replace(tzinfo=None)
                        scheduled_at = naive_dt.replace(tzinfo=IST)
                    else:
                        # Handle string datetime values
                        datetime_str = str(datetime_value)
                        if 'Z' in datetime_str or '+' in datetime_str:
                            scheduled_at = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                        else:
                            naive_dt = datetime.fromisoformat(datetime_str)
                            scheduled_at = naive_dt.replace(tzinfo=IST)
                except ValueError:
                    errors.append(f"Row {idx + 2}: Invalid datetime format")
                    failed += 1
                    continue
                
                # Validate scheduled time is at least 5 minutes in the future
                try:
                    validate_scheduled_time(scheduled_at)
                except HTTPException as e:
                    errors.append(f"Row {idx + 2}: {e.detail}")
                    failed += 1
                    continue
                
                # Create booking
                token = booking_service.create_booking(
                    name=str(row['name']),
                    email=str(row['email']),
                    scheduled_at=scheduled_at,
                    phone=str(row['phone']),
                    application_text=None,
                    application_url=None,
                )
                
                # Generate interview URL - use request origin dynamically
                base_url = get_frontend_url(http_request)
                interview_url = f"{base_url}/interview/{token}" if base_url else f"/interview/{token}"
                
                # Send email (non-blocking)
                try:
                    await email_service.send_interview_email(
                        to_email=str(row['email']),
                        name=str(row['name']),
                        interview_url=interview_url,
                        scheduled_at=scheduled_at,
                    )
                except Exception as e:
                    logger.warning(f"[API] Email failed for {row['email']}: {str(e)}")
                
                successful += 1
                logger.info(f"[API] ✅ Registered candidate {idx + 1}/{total}: {row['email']}")
                
            except Exception as e:
                failed += 1
                error_msg = f"Row {idx + 2}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"[API] {error_msg}")
        
        logger.info(f"[API] Bulk registration complete: {successful}/{total} successful")
        
        return BulkRegistrationResponse(
            success=True,
            total=total,
            successful=successful,
            failed=failed,
            errors=errors if errors else None,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to bulk register: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@app.get("/api/admin/gemini-usage", response_model=List[BookingResponse])
async def get_gemini_usage_report(
    current_admin: dict = Depends(get_current_admin),
):
    """
    Get all interviews with token usage for reporting.
    """
    try:
        # Fetch all bookings from Supabase
        # The interview_bookings table has a 'token_usage' column (JSONB)
        bookings = booking_service.get_all_bookings()
        
        candidates = []
        for booking in bookings:
            # Only include if token_usage is present (or return all?)
            # The original aggregation was joining evaluations.
            # If token_usage is stored in booking, we use that.
            # If not, we might need to fetch evaluations separately, but let's rely on booking table for now
            # as per schema definition in SUPABASE_SCHEMA.md
            
            candidates.append(BookingResponse(
                token=booking.get('token', ''),
                name=booking.get('name', ''),
                email=booking.get('email', ''),
                phone=booking.get('phone', ''),
                scheduled_at=str(booking.get('scheduled_at', '')),
                created_at=str(booking.get('created_at', '')),
                application_text=booking.get('application_text'),
                application_url=booking.get('application_url'),
                token_usage=booking.get('token_usage'),
                slot_id=booking.get('slot_id'),
                application_form_submitted=booking.get('application_form_submitted')
            ))
        
        return candidates
    except Exception as e:
        logger.error(f"[API] Error fetching usage report: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/admin/candidates", response_model=PaginatedCandidatesResponse)
async def get_all_candidates(
    current_admin: dict = Depends(get_current_admin),
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    status_filter: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
):
    """
    Get paginated list of registered candidates.
    Requires admin authentication.
    
    Args:
        page: Page number (1-indexed, default 1)
        page_size: Items per page (default 20, max 100)
        search: Search by name or email (optional)
        status_filter: Filter by status (optional)
        sort_by: Sort field (created_at, scheduled_at, name, email)
        sort_order: Sort order (asc or desc)
    """
    try:
        # Validate pagination params
        page = max(1, page)
        page_size = min(max(1, page_size), 100)  # Cap at 100
        
        logger.info(f"[API] Fetching candidates: page={page}, size={page_size}, search={search}")
        
        # Build query filter
        query_filter = {}
        if search:
            # Case-insensitive search on name or email
            query_filter["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}},
            ]
        if status_filter:
            query_filter["status"] = status_filter
        
        # Determine sort direction
        sort_direction = -1 if sort_order == "desc" else 1
        valid_sort_fields = ["created_at", "scheduled_at", "name", "email"]
        if sort_by not in valid_sort_fields:
            sort_by = "created_at"
        
        # Get total count
        total = booking_service.col.count_documents(query_filter)
        
        # Calculate pagination
        total_pages = max(1, (total + page_size - 1) // page_size)
        skip = (page - 1) * page_size
        
        # Fetch paginated results with evaluation data (for token_usage)
        pipeline = [
            {"$match": query_filter},
            {"$sort": {sort_by: sort_direction}},
            {"$skip": skip},
            {"$limit": page_size},
            {
                "$lookup": {
                    "from": "interview_evaluations",
                    "localField": "token",
                    "foreignField": "booking_token",
                    "as": "evaluation"
                }
            },
            {
                "$addFields": {
                    "token_usage": {"$arrayElemAt": ["$evaluation.token_usage", 0]}
                }
            }
        ]
        cursor = booking_service.col.aggregate(pipeline)
        
        # Convert to BookingResponse format
        candidates = []
        for doc in cursor:
            booking = booking_service._doc_to_booking(doc)
            if booking:
                candidates.append(BookingResponse(
                    token=booking.get('token', ''),
                    name=booking.get('name', ''),
                    email=booking.get('email', ''),
                    phone=booking.get('phone', ''),
                    scheduled_at=booking.get('scheduled_at', ''),
                    created_at=booking.get('created_at', ''),
                    application_text=booking.get('application_text'),
                    application_url=booking.get('application_url'),
                    token_usage=doc.get('token_usage'),
                ))
        
        logger.info(f"[API] ✅ Returning {len(candidates)} candidates (page {page}/{total_pages}, total {total})")
        
        return PaginatedCandidatesResponse(
            items=candidates,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )
    except Exception as e:
        logger.error(f"[API] Error fetching candidates: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch candidates: {str(e)}"
        )


# ==================== User Endpoints ====================

@app.post("/api/user/application", response_model=ScheduleInterviewResponse)
async def submit_rrb_application(request: RRBApplicationRequest, http_request: Request):
    """
    Submit RRB PO application form and schedule interview.
    """
    try:
        logger.info(f"[API] RRB application submitted: {request.email}")
        
        # Convert application data to JSON string for storage
        application_data = request.dict()
        application_text = json.dumps(application_data, indent=2)
        
        # Parse interview datetime
        try:
            # Combine date and time
            date_str = request.interviewDate
            hour = int(request.interviewHour)
            if request.interviewAmpm == 'PM' and hour != 12:
                hour += 12
            elif request.interviewAmpm == 'AM' and hour == 12:
                hour = 0
            
            datetime_str = f"{date_str}T{hour:02d}:{request.interviewMinute}:00"
            naive_dt = datetime.fromisoformat(datetime_str)
            scheduled_at = naive_dt.replace(tzinfo=IST)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid datetime format: {str(e)}"
            )
        
        # Validate scheduled time is at least 5 minutes in the future
        validate_scheduled_time(scheduled_at)
        
        # Create booking with application data
        token = booking_service.create_booking(
            name=request.fullName,
            email=request.email,
            scheduled_at=scheduled_at,
            phone=request.mobileNumber,
            application_text=application_text,
            application_url=None,
        )
        
        # Generate interview URL - use request origin dynamically
        base_url = get_frontend_url(http_request)
        interview_url = f"{base_url}/interview/{token}" if base_url else f"/interview/{token}"
        
        # Send email
        email_sent = False
        email_error = None
        try:
            email_sent, email_error = await email_service.send_interview_email(
                to_email=request.email,
                name=request.fullName,
                interview_url=interview_url,
                scheduled_at=scheduled_at,
            )
        except Exception as e:
            email_error = str(e)
            logger.warning(f"[API] Email sending failed: {email_error}")
        
        logger.info(f"[API] ✅ RRB application submitted: {interview_url}")
        
        return ScheduleInterviewResponse(
            ok=True,
            interviewUrl=interview_url,
            emailSent=email_sent,
            emailError=email_error,
        )
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to submit application: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@app.get("/api/user/application/{token}")
async def get_application_by_token(token: str):
    """
    Get application by token.
    """
    try:
        booking = booking_service.get_booking(token)
        
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found"
            )
        
        # Parse application_text if available
        application_data = None
        if booking.get("application_text"):
            try:
                application_data = json.loads(booking["application_text"])
            except json.JSONDecodeError:
                # If not JSON, return as is
                application_data = {"raw_text": booking["application_text"]}
        
        return {
            "token": booking.get("token"),
            "application_data": application_data,
            "scheduled_at": booking.get("scheduled_at"),
            "created_at": booking.get("created_at"),
        }
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to fetch application: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@app.post("/api/admin/users", response_model=UserResponse)
async def enroll_user(
    request: EnrollUserRequest, 
    background_tasks: BackgroundTasks,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Enroll a new user (without scheduling interview).
    Creates student account with temporary password and sends email.
    """
    try:
        logger.info(f"[API] Enrolling user: {request.email}")
        
        # Generate temporary password
        temporary_password = auth_service.generate_temporary_password()
        
        # Create student account with temporary password
        try:
            student = auth_service.register_student(
                email=request.email,
                password=temporary_password,
                name=request.name,
                phone=request.phone,
                must_change_password=True  # Force password change on first login
            )
        except Exception as e:
            error_msg = str(e)
            # Check if student already exists
            if "already registered" in error_msg.lower() or "unique constraint" in error_msg.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"User with email {request.email} already exists"
                )
            raise
        
        # Validate or Auto-assign slots
        target_slot_ids = request.slot_ids
        if not target_slot_ids:
            # Auto-assign all active slots for the next 2 days
            try:
                now = get_now_ist()
                two_days_from_now = now + timedelta(days=2)
                all_slots = slot_service.get_all_slots(status='active', include_past=False)
                
                target_slot_ids = []
                for slot in all_slots:
                    try:
                        slot_dt_str = slot['slot_datetime']
                        if slot_dt_str.endswith('Z') or '+' in slot_dt_str:
                            slot_dt = to_ist(datetime.fromisoformat(slot_dt_str.replace('Z', '+00:00')))
                        else:
                            slot_dt = datetime.fromisoformat(slot_dt_str).replace(tzinfo=IST)
                        
                        if slot_dt >= now and slot_dt <= two_days_from_now and slot.get('current_bookings', 0) < slot.get('max_capacity', 1):
                            target_slot_ids.append(slot['id'])
                    except Exception:
                        continue
                logger.info(f"[API] Auto-assigned {len(target_slot_ids)} slots to user {request.email}")
            except Exception as e:
                logger.error(f"[API] Failed to auto-assign slots: {str(e)}")
        else:
            # Validate slots if provided manually
            if len(target_slot_ids) < 10:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="At least 10 slots must be assigned to the user"
                )
            
            # Validate all slots exist and are in the next 2 days
            two_days_from_now = get_now_ist() + timedelta(days=2)
            for slot_id in target_slot_ids:
                slot = slot_service.get_slot(slot_id)
                if not slot:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Slot {slot_id} not found"
                    )
                if slot['status'] != 'active':
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Slot {slot_id} is not active"
                    )
                # Parse slot datetime and check if within next 2 days
                try:
                    slot_datetime_str = slot['slot_datetime']
                    if slot_datetime_str.endswith('Z') or '+' in slot_datetime_str:
                        slot_datetime = to_ist(datetime.fromisoformat(slot_datetime_str.replace('Z', '+00:00')))
                    else:
                        slot_datetime = datetime.fromisoformat(slot_datetime_str).replace(tzinfo=IST)
                    
                    if slot_datetime > two_days_from_now:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"All slots must be within the next 2 days. Slot {slot_id} is beyond that."
                        )
                except (ValueError, KeyError, TypeError):
                    pass
        
        # Create enrolled_users record
        user = user_service.create_user(
            name=request.name,
            email=request.email,
            phone=request.phone,
            notes=request.notes,
        )
        
        # Assign slots to user
        if target_slot_ids:
            try:
                assignment_service.assign_slots_to_user(user['id'], target_slot_ids)
                logger.info(f"[API] ✅ Assigned {len(target_slot_ids)} slots to user {user['id']}")
            except Exception as e:
                logger.warning(f"[API] ⚠️ Failed to assign slots: {str(e)}")
        
        # Send enrollment email in background using FastAPI BackgroundTasks
        logger.info(f"[API] 📧 Preparing to send enrollment email to {request.email}")
        logger.info("[API] 📧 Temporary password generated (redacted)")
        
        # Send enrollment email - try to send it, but don't block if it fails
        # We'll send it in background but also track the status
        email_sent = False
        email_error = None
        
        async def send_enrollment_email_bg():
            nonlocal email_sent, email_error
            try:
                logger.debug(f"[API] 📧 ===== BACKGROUND TASK EXECUTING ===== {request.email}")
                logger.info(f"[API] 📧 ===== BACKGROUND TASK EXECUTING ===== {request.email}")
                logger.debug(f"[API] 📧 Background task STARTED - sending enrollment email to {request.email}")
                logger.info(f"[API] 📧 Background task started - sending enrollment email to {request.email}")
                
                logger.debug(f"[API] 📧 About to call email_service.send_enrollment_email...")
                success, error = await email_service.send_enrollment_email(
                    to_email=request.email,
                    name=request.name,
                    email=request.email,
                    temporary_password=temporary_password,
                )
                
                email_sent = success
                email_error = error
                
                if success:
                    logger.debug(f"[API] ✅ Enrollment email sent successfully to {request.email}")
                    logger.info(f"[API] ✅ Enrollment email sent successfully to {request.email}")
                else:
                    logger.debug(f"[API] ❌ Enrollment email failed to send to {request.email}: {error}")
                    logger.error(f"[API] ❌ Enrollment email failed to send to {request.email}: {error}")
            except Exception as e:
                email_error = str(e)
                logger.debug(f"[API] ❌ Exception while sending enrollment email to {request.email}: {str(e)}")
                logger.error(f"[API] ❌ Exception while sending enrollment email to {request.email}: {str(e)}", exc_info=True)
        
        # Create background task - ensure it's scheduled
        try:
            task = asyncio.create_task(send_enrollment_email_bg())
            # Give it a moment to start
            await asyncio.sleep(0.1)  # Small delay to let task start
            logger.debug(f"[API] 📧 Email task created and scheduled: {task} for {request.email}")
            logger.info(f"[API] 📧 Email task created for {request.email}")
        except Exception as e:
            email_error = f"Failed to create email task: {str(e)}"
            logger.debug(f"[API] ❌ {email_error}")
            logger.error(f"[API] ❌ {email_error}", exc_info=True)
        logger.debug(f"[API] 📧 Enrollment email task added to background tasks for {request.email}")
        logger.info(f"[API] 📧 Enrollment email task added to background tasks for {request.email}")
        
        logger.debug(f"[API] ✅ User enrolled: {request.email}")
        logger.info(f"[API] ✅ User enrolled: {request.email}")
        
        # Add email status to response (ensure optional fields for UserResponse)
        user_dict = dict(user)
        user_dict.setdefault('updated_at', None)
        user_dict['email_sent'] = email_sent
        user_dict['email_error'] = email_error
        # Do not include temporary_password in response (security)

        return UserResponse(**user_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to enroll user: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


class BulkEnrollResponse(BaseModel):
    success: bool
    total: int
    successful: int
    failed: int
    errors: Optional[List[str]] = None


@app.post("/api/admin/users/bulk-enroll", response_model=BulkEnrollResponse)
async def bulk_enroll_users(
    file: UploadFile = File(...),
    current_admin: dict = Depends(get_current_admin)
):
    """
    Bulk enroll users from Excel file.
    Expected format: name, email, phone (optional), notes (optional) columns.
    Creates student accounts with temporary passwords and sends emails in background.
    """
    try:
        logger.info(f"[API] Bulk enrolling users from file: {file.filename}")
        
        # Read Excel file
        try:
            contents = await file.read()
            df = pd.read_excel(BytesIO(contents))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read Excel file: {str(e)}"
            )
        
        # Validate required columns
        required_columns = ['name', 'email']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required columns: {', '.join(missing_columns)}. Expected columns: {', '.join(required_columns)} (phone and notes are optional)"
            )
        
        total = len(df)
        successful = 0
        failed = 0
        errors = []
        
        # Get active slots for next 2 days for auto-assignment
        now_dt = get_now_ist()
        two_days_from_now = now_dt + timedelta(days=2)
        all_slots = slot_service.get_all_slots(status='active', include_past=False)
        auto_assign_slot_ids = []
        for slot in all_slots:
            try:
                slot_dt_str = slot['slot_datetime']
                if slot_dt_str.endswith('Z') or '+' in slot_dt_str:
                    slot_dt = to_ist(datetime.fromisoformat(slot_dt_str.replace('Z', '+00:00')))
                else:
                    slot_dt = datetime.fromisoformat(slot_dt_str).replace(tzinfo=IST)
                
                if slot_dt >= now_dt and slot_dt <= two_days_from_now and slot.get('current_bookings', 0) < slot.get('max_capacity', 1):
                    auto_assign_slot_ids.append(slot['id'])
            except Exception:
                continue
        
        logger.info(f"[API] Bulk enrollment will auto-assign {len(auto_assign_slot_ids)} slots to each user")
        
        # Process each row
        for idx, row in df.iterrows():
            try:
                name = str(row['name']).strip()
                email = str(row['email']).strip()
                phone = str(row.get('phone', '')).strip() if pd.notna(row.get('phone')) else None
                notes = str(row.get('notes', '')).strip() if pd.notna(row.get('notes')) else None
                
                # Skip empty rows
                if not name or not email:
                    raise ValueError("name and email are required and cannot be empty")
                
                # Generate temporary password
                temporary_password = auth_service.generate_temporary_password()
                
                # Create student account with temporary password
                try:
                    student = auth_service.register_student(
                        email=email,
                        password=temporary_password,
                        name=name,
                        phone=phone,
                        must_change_password=True  # Force password change on first login
                    )
                except Exception as e:
                    error_msg = str(e)
                    # Check if student already exists
                    if "already registered" in error_msg.lower() or "unique constraint" in error_msg.lower():
                        raise ValueError(f"User with email {email} already exists")
                    raise ValueError(f"Failed to create student account: {str(e)}")
                
                # Create enrolled_users record
                try:
                    user = user_service.create_user(
                        name=name,
                        email=email,
                        phone=phone,
                        notes=notes,
                    )
                except Exception as e:
                    # If enrolled_user creation fails but student was created, we still count it as failed
                    error_msg = str(e)
                    if "unique constraint" in error_msg.lower() or "already exists" in error_msg.lower():
                        raise ValueError(f"Enrolled user with email {email} already exists")
                    raise ValueError(f"Failed to create enrolled user: {str(e)}")
                
                # Assign slots to user
                if auto_assign_slot_ids:
                    try:
                        assignment_service.assign_slots_to_user(user['id'], auto_assign_slot_ids)
                        logger.info(f"[API] ✅ Auto-assigned {len(auto_assign_slot_ids)} slots to user {user['id']}")
                    except Exception as e:
                        logger.warning(f"[API] ⚠️ Failed to auto-assign slots for {email}: {str(e)}")
                
                # Schedule enrollment email in background
                async def send_enrollment_email_bg(email_addr: str, name_val: str, temp_pass: str):
                    try:
                        await email_service.send_enrollment_email(
                            to_email=email_addr,
                            name=name_val,
                            email=email_addr,
                            temporary_password=temp_pass,
                        )
                        logger.info(f"[API] ✅ Bulk enrollment email sent to {email_addr}")
                    except Exception as e:
                        logger.warning(f"[API] ⚠️ Bulk enrollment email failed for {email_addr}: {str(e)}")
                
                asyncio.create_task(send_enrollment_email_bg(email, name, temporary_password))
                
                successful += 1
                logger.info(f"[API] ✅ Enrolled user {idx + 1}/{total}: {email}")
                
            except Exception as e:
                failed += 1
                error_msg = f"Row {idx + 2}: {str(e)}"  # idx + 2 because Excel rows start at 2 (1 is header)
                errors.append(error_msg)
                logger.error(f"[API] {error_msg}")
        
        # Give background tasks a moment to start
        await asyncio.sleep(0.1)
        
        logger.info(f"[API] Bulk enrollment complete: {successful}/{total} successful")
        
        return BulkEnrollResponse(
            success=True,
            total=total,
            successful=successful,
            failed=failed,
            errors=errors if errors else None,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to bulk enroll users: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@app.get("/api/admin/users", response_model=List[UserResponse])
async def get_all_users(
    current_admin: dict = Depends(get_current_admin),
    limit: Optional[int] = None,
    skip: Optional[int] = None,
):
    """
    Get all enrolled users with optional pagination.
    Query params: limit (max 500), skip. Omit for full list.
    """
    try:
        users = user_service.get_all_users(limit=limit, skip=skip)
        return [UserResponse(**user) for user in users]
    except Exception as e:
        error_msg = f"Failed to fetch users: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@app.get("/api/admin/users/{user_id}", response_model=UserDetailResponse)
async def get_user(user_id: str, current_admin: dict = Depends(get_current_admin)):
    """
    Get an enrolled user by ID with full interview history.
    Accessible to both admins and managers.
    """
    try:
        # 1. Fetch user profile
        user = user_service.get_user(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # 2. Fetch user bookings
        # Primary: bookings linked by user_id.
        # Fallback: bookings that match the user's email (older data may not have user_id populated).
        bookings = booking_service.get_user_bookings(user_id)
        if not bookings:
            user_email = (user.get("email") or "").strip()
            if user_email:
                bookings = booking_service.get_bookings_by_email(user_email)
        else:
            # Merge email-based bookings too (avoid duplicates) in case some rows missed user_id linkage.
            user_email = (user.get("email") or "").strip()
            if user_email:
                email_bookings = booking_service.get_bookings_by_email(user_email)
                seen_tokens = {b.get("token") for b in bookings if b.get("token")}
                for b in email_bookings:
                    t = b.get("token")
                    if t and t not in seen_tokens:
                        bookings.append(b)
                        seen_tokens.add(t)
        
        # 3. Fetch evaluations for those bookings
        booking_tokens = [b["token"] for b in bookings]
        evaluations = evaluation_service.get_evaluations_for_bookings(booking_tokens)
        eval_map = {e["booking_token"]: e for e in evaluations}
        
        # 4. Construct interview summaries
        interviews = []
        for booking in bookings:
            token = booking.get("token")
            evaluation = eval_map.get(token)
            
            summary = InterviewSummary(
                token=token,
                scheduled_at=booking.get("scheduled_at", ""),
                status=booking.get("status", "scheduled"),
                overall_score=evaluation.get("overall_score") if evaluation else None,
                overall_feedback=evaluation.get("overall_feedback") if evaluation else None,
                evaluation_url=f"/evaluation/{token}" if evaluation else None,
                interview_url=f"/interview/{token}" if booking.get("status") == "scheduled" else None
            )
            interviews.append(summary)
            
        # 5. Compute aggregated overall analysis (best-effort)
        overall_analysis = None
        try:
            analytics = evaluation_service.get_student_analytics(booking_tokens)
            overall_analysis = analytics.get("overall_analysis")
            # Fallback: most recent evaluation overall_feedback
            if not overall_analysis:
                scored_evals = [e for e in evaluations if e.get("overall_feedback")]
                scored_evals.sort(key=lambda x: x.get("created_at", ""))
                if scored_evals:
                    overall_analysis = scored_evals[-1].get("overall_feedback")
        except Exception as e:
            logger.warning(f"[API] Could not compute overall analysis for user {user_id}: {e}")

        # 6. Return detailed response
        user_response = UserResponse(**user)
        return UserDetailResponse(
            **user_response.dict(),
            interviews=interviews,
            overall_analysis=overall_analysis,
        )
            
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to fetch user: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@app.put("/api/admin/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    request: UpdateUserRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Update an enrolled user.
    """
    try:
        user = user_service.update_user(
            user_id=user_id,
            name=request.name,
            email=request.email,
            phone=request.phone,
            status=request.status,
            notes=request.notes,
        )
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return UserResponse(**user)
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to update user: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@app.delete("/api/admin/users/{user_id}")
async def delete_user(user_id: str, current_admin: dict = Depends(get_current_admin)):
    """
    Delete an enrolled user and all associated data: bookings, transcripts, evaluations,
    slot assignments, application form, enrolled user record, and student login account.
    """
    try:
        user = user_service.get_user(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        email = user.get("email")

        # 1. Get booking tokens for this user (before deleting bookings)
        bookings = booking_service.get_bookings_by_user_id(user_id)
        booking_tokens = [b.get("token") for b in bookings if b.get("token")]

        # 2. Delete transcripts for those bookings
        if booking_tokens:
            try:
                transcript_storage_service.delete_by_booking_tokens(booking_tokens)
            except Exception as e:
                logger.warning(f"[API] Could not delete transcripts for user {user_id}: {e}")

        # 3. Delete evaluations for those bookings
        if booking_tokens:
            try:
                evaluation_service.delete_evaluations_by_booking_tokens(booking_tokens)
            except Exception as e:
                logger.warning(f"[API] Could not delete evaluations for user {user_id}: {e}")

        # 4. Delete all bookings for this user
        try:
            booking_service.delete_bookings_by_user_id(user_id)
        except Exception as e:
            logger.warning(f"[API] Could not delete bookings for user {user_id}: {e}")

        # 5. Delete all slot assignments for this user
        try:
            assignment_service.delete_assignments_by_user_id(user_id)
        except Exception as e:
            logger.warning(f"[API] Could not delete assignments for user {user_id}: {e}")

        # 6. Delete enrolled user record
        success = user_service.delete_user(user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # 8. Delete student login account so the same email can be re-enrolled
        if email:
            try:
                auth_service.delete_student_by_email(email)
            except Exception as e:
                logger.warning(f"[API] Could not delete student auth for {email}: {e}")

        logger.info(f"[API] ✅ Deleted user {user_id} and all associated data")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to delete user: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


class RemoveStudentAuthRequest(BaseModel):
    email: str


@app.post("/api/admin/users/remove-student-auth")
async def remove_student_auth_by_email(
    request: RemoveStudentAuthRequest,
    current_admin: dict = Depends(get_current_admin),
):
    """
    Remove only the student login account for an email (cleanup when user was deleted before
    the fix that also deletes student auth). Use so the email can be re-enrolled.
    """
    email = (request.email or "").strip()
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="email is required")
    try:
        deleted = auth_service.delete_student_by_email(email)
        if deleted:
            return {"success": True, "message": f"Student login removed for {email}. You can now re-enroll this email."}
        return {"success": False, "message": f"No student account found for {email}."}
    except Exception as e:
        logger.error(f"[API] remove_student_auth: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ==================== Admin Interview Scheduling Endpoints ====================

@app.post("/api/admin/schedule-interview", response_model=ScheduleInterviewResponse)
async def schedule_interview_for_user(
    request: ScheduleInterviewForUserRequest,
    http_request: Request,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Schedule an interview for an enrolled user using a predefined slot.
    Returns interview link immediately and processes email in background.
    """
    try:
        logger.info(f"[API] Scheduling interview for user_id: {request.user_id} with slot_id: {request.slot_id}")
        
        # Get the enrolled user
        user = user_service.get_user(request.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get the slot and validate it exists
        slot = slot_service.get_slot(request.slot_id)
        if not slot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview slot not found"
            )
        
        # Check if slot is active and has available capacity
        if slot['status'] != 'active':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Slot is not available. Status: {slot['status']}"
            )
        
        if slot['current_bookings'] >= slot['max_capacity']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Slot is full. Capacity: {slot['current_bookings']}/{slot['max_capacity']}"
            )
        
        # Parse slot datetime - handle UTC or IST format properly
        try:
            slot_datetime_str = slot.get('slot_datetime') or slot.get('start_time')
            if not slot_datetime_str:
                raise ValueError("No start time found for slot")
            
            # Use parse_datetime_safe to handle both UTC and IST formats
            scheduled_at = parse_datetime_safe(slot_datetime_str)
            logger.info(f"[API] Parsed slot datetime: {slot_datetime_str} -> {scheduled_at.isoformat()} (IST)")
        except (ValueError, KeyError, TypeError) as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Invalid slot datetime format: {str(e)}"
            )
        
        # Create booking with slot_id reference
        try:
            # Resolve actual user_id from users table (if registered) to avoid FK violation
            # interview_bookings.user_id references users.id, but request.user_id is from enrolled_users
            auth_user = auth_service.get_user_by_email(user['email'])
            booking_user_id = auth_user['id'] if auth_user else None
            
            token = booking_service.create_booking(
                name=user['name'],
                email=user['email'],
                scheduled_at=scheduled_at,
                phone=user.get('phone', ''),
                application_text=None,
                application_url=None,
                slot_id=request.slot_id,
                user_id=booking_user_id,
                prompt=request.prompt,
            )
            logger.info(f"[API] ✅ Booking created successfully: token={token}, user_id={request.user_id}")
        except Exception as e:
            logger.error(f"[API] Failed to create booking: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create booking: {str(e)}"
            )
        
        # Increment slot booking count
        try:
            success = slot_service.increment_booking_count(request.slot_id)
            if success:
                logger.info(f"[API] ✅ Incremented booking count for slot {request.slot_id}")
            else:
                logger.warning(f"[API] ⚠️ Failed to increment booking count - slot may be full")
                # This shouldn't happen as we checked above, but handle it gracefully
        except Exception as e:
            logger.warning(f"[API] ⚠️ Failed to increment slot booking count: {str(e)}")
            # Don't fail the request if slot update fails, but log it
        
        # Update user status to 'interviewed'
        try:
            user_service.update_user(request.user_id, status='interviewed')
        except Exception as e:
            logger.warning(f"[API] Failed to update user status: {str(e)}")
        
        # Generate interview URL - use request origin dynamically
        base_url = get_frontend_url(http_request)
        interview_url = f"{base_url}/interview/{token}" if base_url else f"/interview/{token}"
        
        # Send email and update status in background (non-blocking)
        async def send_email_and_update_bg():
            try:
                # Send email with timeout
                email_sent, email_error = await asyncio.wait_for(
                    email_service.send_interview_email(
                        to_email=user['email'],
                        name=user['name'],
                        interview_url=interview_url,
                        scheduled_at=scheduled_at,
                    ),
                    timeout=10.0
                )
                if email_sent:
                    logger.info(f"[API] ✅ Interview email sent to {user['email']}")
                else:
                    logger.warning(f"[API] ⚠️ Interview email failed for {user['email']}: {email_error}")
            except asyncio.TimeoutError:
                logger.warning(f"[API] ⚠️ Interview email timed out for {user['email']}")
            except Exception as e:
                logger.error(f"[API] ❌ Exception sending interview email: {str(e)}", exc_info=True)
        
        # Schedule background task
        asyncio.create_task(send_email_and_update_bg())
        await asyncio.sleep(0.1)  # Small delay to ensure task is scheduled
        
        logger.info(f"[API] ✅ Interview scheduled: {interview_url}")
        
        # Return immediately with interview URL
        return ScheduleInterviewResponse(
            ok=True,
            interviewUrl=interview_url,
            emailSent=False,  # Email is sent in background
            emailError=None,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to schedule interview: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@app.post("/api/admin/schedule-interview/bulk", response_model=BulkScheduleInterviewResponse)
async def bulk_schedule_interviews(
    http_request: Request,
    file: UploadFile = File(...),
    current_admin: dict = Depends(get_current_admin)
):
    """
    Bulk schedule interviews from Excel file.
    Expected format: email, datetime columns.
    Returns immediately and processes emails in background.
    """
    try:
        logger.info(f"[API] Bulk scheduling interviews from file: {file.filename}")
        
        # Read Excel file
        try:
            contents = await file.read()
            df = pd.read_excel(BytesIO(contents))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read Excel file: {str(e)}"
            )
        
        # Validate required columns
        required_columns = ['email', 'datetime']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required columns: {', '.join(missing_columns)}. Expected columns: {', '.join(required_columns)}"
            )
        
        total = len(df)
        successful = 0
        failed = 0
        errors = []
        
        # Process each row
        for idx, row in df.iterrows():
            try:
                email = str(row['email']).lower().strip()
                datetime_str = str(row['datetime']).strip()
                
                if not email or not datetime_str:
                    raise ValueError("email and datetime are required")
                
                # Get the enrolled user by email
                user = user_service.get_user_by_email(email)
                if not user:
                    raise ValueError(f"User with email {email} not found")
                
                user_id = user['id']
                
                # Parse datetime
                try:
                    # Handle pandas datetime objects
                    if isinstance(row['datetime'], pd.Timestamp):
                        scheduled_at = row['datetime'].to_pydatetime()
                        # Ensure it's treated as IST
                        scheduled_at = to_ist(scheduled_at)
                    else:
                        # Remove timezone suffix if present and parse
                        datetime_str_clean = datetime_str
                        if datetime_str_clean.endswith('Z'):
                            datetime_str_clean = datetime_str_clean[:-1]
                        elif '+' in datetime_str_clean:
                            datetime_str_clean = datetime_str_clean.split('+')[0]
                        
                        scheduled_at = to_ist(datetime.fromisoformat(datetime_str_clean))
                except (ValueError, AttributeError) as e:
                    raise ValueError(f"Invalid datetime format: {datetime_str}")
                
                # Validate scheduled time
                now = get_now_ist()
                if scheduled_at <= now:
                    raise ValueError(f"Scheduled time must be in the future (Time in IST: {scheduled_at.strftime('%Y-%m-%d %H:%M:%S')})")
                
                # Create booking
                # Resolve actual user_id from users table (if registered) to avoid FK violation
                # interview_bookings.user_id references users.id, but user['id'] is from enrolled_users
                auth_user = auth_service.get_user_by_email(user['email'])
                booking_user_id = auth_user['id'] if auth_user else None
                
                token = booking_service.create_booking(
                    name=user['name'],
                    email=user['email'],
                    scheduled_at=scheduled_at,
                    phone=user.get('phone', ''),
                    application_text=None,
                    application_url=None,
                    user_id=booking_user_id,
                    slot_id=None, # Bulk scheduling creates direct bookings without specific pre-allocated slots
                )
                
                # Update user status
                try:
                    user_service.update_user(user_id, status='interviewed')
                except Exception:
                    pass  # Don't fail if status update fails
                
                # Generate interview URL - use request origin dynamically
                base_url = get_frontend_url(http_request)
                interview_url = f"{base_url}/interview/{token}" if base_url else f"/interview/{token}"
                
                # Schedule email in background
                async def send_email_bg(email: str, name: str, url: str, scheduled_dt: datetime):
                    try:
                        success, error_msg = await asyncio.wait_for(
                            email_service.send_interview_email(
                                to_email=email,
                                name=name,
                                interview_url=url,
                                scheduled_at=scheduled_dt,
                            ),
                            timeout=30.0
                        )
                        if success:
                            logger.info(f"[API] ✅ Bulk interview email sent to {email}")
                        else:
                            logger.warning(f"[API] ⚠️ Bulk interview email failed for {email}: {error_msg}")
                    except asyncio.TimeoutError:
                        logger.warning(f"[API] ⚠️ Bulk interview email timed out for {email} after 30s")
                    except Exception as e:
                        logger.warning(f"[API] ⚠️ Bulk interview email failed for {email}: {repr(e)}")
                
                asyncio.create_task(send_email_bg(user['email'], user['name'], interview_url, scheduled_at))
                
                successful += 1
                logger.info(f"[API] ✅ Scheduled interview {idx + 1}/{total}: {user['email']}")
                
            except Exception as e:
                failed += 1
                error_msg = f"Row {idx + 2}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"[API] {error_msg}")
        
        # Give background tasks a moment to start
        await asyncio.sleep(0.1)
        
        logger.info(f"[API] Bulk scheduling complete: {successful}/{total} successful")
        
        return BulkScheduleInterviewResponse(
            success=True,
            total=total,
            successful=successful,
            failed=failed,
            errors=errors if errors else None,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to bulk schedule interviews: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@app.post("/api/admin/slots", response_model=SlotResponse)
async def create_slot(
    request: CreateSlotRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Create a new interview slot.
    """
    try:
        # Parse datetime and ensure it's in IST
        try:
            # Parse the datetime string (may come with or without timezone)
            slot_datetime_str = request.slot_datetime.replace('Z', '+00:00')
            slot_datetime = datetime.fromisoformat(slot_datetime_str)
            
            # Convert to IST timezone
            # If datetime is naive (no timezone), assume it's already in IST
            # If datetime has timezone, convert it to IST
            start_time = to_ist(slot_datetime)
            
            logger.info(f"[API] Slot creation - Input: {request.slot_datetime}, Parsed: {slot_datetime}, IST: {start_time}")
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid datetime format. Use ISO format. Error: {str(e)}"
            )
        
        # Validate capacity
        if request.max_capacity < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Max capacity must be at least 1"
            )
        
        # Validate duration
        if request.duration_minutes < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duration must be at least 1 minute"
            )
        if request.duration_minutes > 120:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duration cannot exceed 120 minutes (2 hours)"
            )
        
        # Use provided duration (default 45 minutes if not specified)
        duration_minutes = request.duration_minutes or 45
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        # Avoid duplicate: a slot already exists at this datetime
        slot_datetime_iso = start_time.isoformat()
        existing = slot_service.get_slot_by_datetime(slot_datetime_iso)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A slot already exists at this date and time. Edit the existing slot or choose a different time."
            )
        
        logger.info(f"[API] Creating slot with duration: {duration_minutes} minutes (from request: {request.duration_minutes})")
        
        slot = slot_service.create_slot(
            start_time=start_time,
            end_time=end_time,
            max_bookings=request.max_capacity,
            notes=request.notes,
            duration_minutes=duration_minutes  # Pass duration explicitly
        )
        
        logger.info(f"[API] Slot created: id={slot.get('id')}, duration_minutes={slot.get('duration_minutes')}, stored_duration={slot.get('duration_minutes')}")
        
        slot_dict = dict(slot)
        slot_dict.setdefault('updated_at', None)
        return SlotResponse(**slot_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to create slot: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@app.get("/api/admin/slots", response_model=List[SlotResponse])
async def get_all_slots(
    slot_status: Optional[str] = None,
    include_past: bool = False,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Get all interview slots.
    """
    try:
        slots = slot_service.get_all_slots(status=slot_status, include_past=include_past)
        out = []
        for slot in slots:
            d = dict(slot)
            d.setdefault("updated_at", None)
            # Ensure datetime fields are strings for SlotResponse (MongoDB may return datetime)
            for key in ("slot_datetime", "start_time", "end_time", "created_at", "updated_at"):
                if key in d and d[key] is not None and hasattr(d[key], "isoformat"):
                    d[key] = d[key].isoformat()
            out.append(SlotResponse(**d))
        return out
    except Exception as e:
        error_msg = f"Failed to fetch slots: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@app.get("/api/admin/slots/{slot_id}", response_model=SlotResponse)
async def get_slot(
    slot_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Get an interview slot by ID.
    """
    try:
        slot = slot_service.get_slot(slot_id)
        if not slot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Slot not found"
            )
        return SlotResponse(**slot)
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to fetch slot: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@app.put("/api/admin/slots/{slot_id}", response_model=SlotResponse)
async def update_slot(
    slot_id: str,
    request: UpdateSlotRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Update an interview slot.
    """
    try:
        updates = {}
        if request.slot_datetime is not None:
            try:
                # Parse and convert to IST
                slot_datetime_str = request.slot_datetime.replace('Z', '+00:00')
                slot_datetime = datetime.fromisoformat(slot_datetime_str)
                updates['slot_datetime'] = to_ist(slot_datetime)
                # Also update start_time if it exists
                updates['start_time'] = to_ist(slot_datetime)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid datetime format. Use ISO format. Error: {str(e)}"
                )
        if request.max_capacity is not None:
            if request.max_capacity < 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Max capacity must be at least 1"
                )
            updates['max_capacity'] = request.max_capacity
        if request.status is not None:
            updates['status'] = request.status
        if request.notes is not None:
            updates['notes'] = request.notes
        
        slot = slot_service.update_slot(slot_id, updates)
        return SlotResponse(**slot)
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to update slot: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@app.delete("/api/admin/slots/{slot_id}")
async def delete_slot(
    slot_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Delete an interview slot.
    """
    try:
        slot_service.delete_slot(slot_id)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to delete slot: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@app.get("/api/slots/available", response_model=List[SlotResponse])
async def get_available_slots():
    """
    Get available slots for students (public endpoint, no auth required).
    """
    try:
        slots = slot_service.get_available_slots()
        return [SlotResponse(**slot) for slot in slots]
    except Exception as e:
        error_msg = f"Failed to fetch available slots: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@app.post("/api/admin/slots/create-day", response_model=CreateDaySlotsResponse)
async def create_day_slots(
    request: CreateDaySlotsRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Create multiple slots for a single day based on start time, end time, and interval.
    """
    try:
        # Parse date
        try:
            selected_date = datetime.strptime(request.date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD format."
            )
        
        # Parse start and end times
        try:
            start_hour, start_minute = map(int, request.start_time.split(':'))
            end_hour, end_minute = map(int, request.end_time.split(':'))
        except (ValueError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid time format. Use HH:MM format (24-hour)."
            )
        
        # Validate times
        if not (0 <= start_hour < 24 and 0 <= start_minute < 60):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start time"
            )
        if not (0 <= end_hour < 24 and 0 <= end_minute < 60):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end time"
            )
        
        # Validate interval
        if request.interval_minutes < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Interval must be at least 1 minute"
            )
        
        # Validate capacity
        if request.max_capacity < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Max capacity must be at least 1"
            )
        
        # Create start and end datetime in IST timezone
        # Admin provides time in IST, so we create it as IST-aware datetime
        start_datetime = datetime.combine(
            selected_date, 
            datetime.min.time().replace(hour=start_hour, minute=start_minute)
        ).replace(tzinfo=IST)
        end_datetime = datetime.combine(
            selected_date, 
            datetime.min.time().replace(hour=end_hour, minute=end_minute)
        ).replace(tzinfo=IST)
        
        # Ensure end time is after start time
        if end_datetime <= start_datetime:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End time must be after start time"
            )
        
        # Generate all slot times in IST
        slot_times = []
        current_time = start_datetime
        interval_delta = timedelta(minutes=request.interval_minutes)
        
        # Only create slots that stay on the target date
        target_date = selected_date
        while current_time < end_datetime:
            # Only add slots that are still on the target date
            if current_time.date() == target_date:
                slot_times.append(current_time)
            else:
                # If we've crossed to next day, stop
                break
            current_time += interval_delta
        
        # Create slots
        created_slots = []
        errors = []
        created_count = 0
        
        for slot_time in slot_times:
            try:
                # Calculate end time for the slot (start_time + interval)
                slot_end_time = slot_time + interval_delta
                
                slot = slot_service.create_slot(
                    start_time=slot_time,
                    end_time=slot_end_time,
                    max_bookings=request.max_capacity,
                    notes=request.notes
                )
                created_slots.append(slot)
                created_count += 1
            except Exception as e:
                error_msg = f"Failed to create slot at {slot_time.strftime('%Y-%m-%d %H:%M')}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"[API] {error_msg}", exc_info=True)
        
        logger.info(f"[API] ✅ Created {created_count} slots for {request.date}")
        
        return CreateDaySlotsResponse(
            success=True,
            created_count=created_count,
            slots=[SlotResponse(**slot) for slot in created_slots],
            errors=errors if errors else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to create day slots: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


# ==================== Student Application / Interview Management Endpoints ====================


@app.get("/api/student/application-form")
async def get_application_form_compat():
    """
    Backwards-compatibility shim for legacy application-form endpoint.

    The dedicated student application form feature has been removed in favor of
    simple resume upload, but some frontend code still calls this endpoint.
    We return `null` instead of 404 so the UI can treat it as "no form data".
    """
    return None


@app.post("/api/student/application-form/upload")
async def upload_application_form_compat(file: UploadFile = File(...)):
    """
    Backwards-compatibility shim for legacy application-form PDF upload.

    We no longer persist a structured application form; resume upload is handled
    separately. This endpoint now just validates that a file was provided and
    returns a success flag so existing frontend flows don't break.
    """
    try:
        if not file or not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided",
            )

        # Read the file once to consume the upload; result is ignored.
        await file.read()

        return {
            "success": True,
            "form": None,
            "extraction_error": None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] Compatibility upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process uploaded file.",
        )


@app.get("/api/student/my-assignments", response_model=List[AssignmentResponse])
async def get_my_assignments(current_student: dict = Depends(get_current_student)):
    """
    Get all slot assignments for the current student.
    Returns only assigned (not yet selected) slots.
    """
    try:
        student_id = current_student['id']
        assignments = assignment_service.get_user_assignments(student_id, status='assigned')
        
        # Format response
        result = []
        for assignment in assignments:
            slot_data = assignment.get('interview_slots')
            if slot_data:
                # Handle nested slot data
                if isinstance(slot_data, dict):
                    slot = SlotResponse(**slot_data)
                elif isinstance(slot_data, list) and len(slot_data) > 0:
                    slot = SlotResponse(**slot_data[0])
                else:
                    continue
                
                result.append(AssignmentResponse(
                    id=assignment['id'],
                    user_id=assignment['user_id'],
                    slot_id=assignment['slot_id'],
                    status=assignment['status'],
                    assigned_at=assignment['assigned_at'],
                    selected_at=assignment.get('selected_at'),
                    slot=slot
                ))
        
        return result
        
    except Exception as e:
        error_msg = f"Failed to fetch assignments: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@app.post("/api/student/select-slot", response_model=ScheduleInterviewResponse)
async def select_slot(
    request: SelectSlotRequest,
    http_request: Request,
    current_student: dict = Depends(get_current_student)
):
    """
    Select a slot for the authenticated student. 
    Accepts slot_id and optional prompt. Creates a booking and cancel other assignments.
    """
    try:
        student_email = current_student['email']
        auth_user_id = current_student['id']
        
        # Get enrolled_user for fallback name/phone
        enrolled_user = user_service.get_user_by_email(student_email)
        
        print("JWT USER:", auth_user_id)
        slot_id = request.slot_id
        prompt = request.prompt
        
        # 2. Check if application form is completed
        application_form = application_form_service.get_form_by_user_id(auth_user_id)
        if not application_form or application_form.get('status') != 'submitted':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please complete and submit your application form before selecting a slot."
            )

        # 3. Get slot details and verify availability
        slot = slot_service.get_slot(slot_id)
        if not slot:
            raise HTTPException(status_code=404, detail="Slot not found")
            
        if slot['status'] != 'active':
            raise HTTPException(status_code=400, detail="Slot is not available")
            
        if slot['current_bookings'] >= slot['max_capacity']:
            raise HTTPException(status_code=400, detail="Slot is full")

        # 4. Check for existing assignment for this slot
        assignments = assignment_service.get_user_assignments(auth_user_id, status='assigned')
        assignment = next((a for a in assignments if a['slot_id'] == slot_id), None)
        
        # If no assignment exists but slot is public/available, we can create one or allow it?
        # Current logic seems to prefer assignments. If none found, we'll try to create a virtual one.
        if not assignment:
            logger.info(f"[API] Student {auth_user_id} selecting slot directly: {slot_id}")
            try:
                new_assignments = assignment_service.assign_slots_to_user(auth_user_id, [slot_id])
                if new_assignments:
                    assignment = new_assignments[0]
                else:
                    raise HTTPException(status_code=500, detail="Failed to create slot assignment")
            except Exception as e:
                logger.error(f"[API] Failed to create assignment: {str(e)}")
                raise HTTPException(status_code=500, detail="Failed to create slot assignment")

        # 5. Parse slot datetime
        slot_datetime_str = slot.get('slot_datetime') or slot.get('start_time')
        scheduled_at = parse_datetime_safe(slot_datetime_str)

        # 6. Create booking
        token = booking_service.create_booking(
            name=current_student.get('name', enrolled_user.get('name', 'Student')),
            email=student_email,
            scheduled_at=scheduled_at,
            phone=current_student.get('phone', enrolled_user.get('phone', '')),
            application_text=application_form.get('application_text') if application_form else None,
            application_url=None,
            slot_id=slot_id,
            user_id=auth_user_id, # Use Auth ID for the booking record
            assignment_id=assignment['id'],
            application_form_id=application_form.get('id') if application_form else None,
            prompt=prompt # Include the prompt from the request
        )

        # 7. Update status: mark assignment used, cancel others, increment count
        assignment_service.select_slot_for_user(auth_user_id, assignment['id'])
        assignment_service.cancel_other_assignments(auth_user_id, assignment['id'])
        slot_service.increment_booking_count(slot_id)
        user_service.update_user(auth_user_id, interview_status='slot_selected')

        # 8. Generate interview URL and send email
        base_url = get_frontend_url(http_request)
        interview_url = f"{base_url}/interview/{token}" if base_url else f"/interview/{token}"
        
        async def send_email_bg():
            try:
                await email_service.send_interview_email(
                    to_email=student_email,
                    name=enrolled_user.get('name', 'Student'),
                    interview_url=interview_url,
                    scheduled_at=scheduled_at,
                )
            except Exception as e:
                logger.warning(f"[API] ⚠️ Failed to send interview email: {e}")
        
        asyncio.create_task(send_email_bg())
        
        return ScheduleInterviewResponse(
            ok=True,
            interviewUrl=interview_url,
            emailSent=True, # We've queued it
            emailError=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to select slot: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )

@app.get("/api/student/my-interview", response_model=MyInterviewResponse)
async def get_my_interview(http_request: Request, current_student: dict = Depends(get_current_student)):
    """
    Get student's interview status across all stages (enrolled/scheduled/completed).
    """
    try:
        student_id = current_student['id']
        student_email = current_student['email']
        
        # Get enrolled_user for legacy data fallback
        enrolled_user = user_service.get_user_by_email(student_email)
        
        # Get current time
        now = get_now_ist()
        logger.info(f"[API] Current IST time: {now.isoformat()}")
        
        logger.info(f"[API] Checking bookings by email: {student_email}")
        email_bookings = booking_service.get_bookings_by_email(student_email)
        logger.info(f"[API] Found {len(email_bookings)} bookings by email: {student_email}")
        
        # Use student_id (auth ID) as primary, but fallback to enrolled_user_id for legacy cleanup
        user_id = student_id
        legacy_user_id = enrolled_user['id'] if enrolled_user else None
        
        user_id_bookings = booking_service.get_bookings_by_user_id(user_id)
        if legacy_user_id and legacy_user_id != user_id:
            legacy_bookings = booking_service.get_bookings_by_user_id(legacy_user_id)
            user_id_bookings.extend(legacy_bookings)
            
        logger.info(f"[API] Found {len(user_id_bookings)} total bookings by user IDs")
        seen_tokens = set()
        all_bookings_data = []
        for booking in email_bookings + user_id_bookings:
            token = booking.get('token')
            if token and token not in seen_tokens:
                seen_tokens.add(token)
                slot = slot_service.get_slot(booking['slot_id']) if booking.get('slot_id') else None
                booking['slot'] = slot
                booking['interview_slots'] = slot
                all_bookings_data.append(booking)
        for booking in email_bookings:
            if not booking.get('user_id') and user_id and booking.get('token'):
                try:
                    booking_service.update_booking(booking['token'], user_id=user_id)
                    booking['user_id'] = user_id
                    logger.info(f"[API] ✅ Updated booking {booking['token']} with user_id: {user_id}")
                except Exception as e:
                    logger.warning(f"[API] Failed to update booking {booking.get('token')}: {e}")
        if not enrolled_user:
            logger.warning(f"[API] No enrolled_user for email {student_email}, using email-based bookings only")
        class MockResult:
            def __init__(self, data):
                self.data = data
        all_bookings = MockResult(all_bookings_data)
        logger.info(f"[API] Total unique bookings found: {len(all_bookings_data)}")
        completed_tokens = set()
        if all_bookings.data:
            booking_tokens = [b.get('token') for b in all_bookings.data if b.get('token')]
            if booking_tokens:
                try:
                    evaluation_tokens = evaluation_service.get_booking_tokens_with_evaluations(booking_tokens)
                    transcript_tokens = transcript_storage_service.get_booking_tokens_with_transcripts(booking_tokens)
                    completed_status_tokens = {b.get('token') for b in all_bookings.data if b.get('status') == 'completed'}
                    completed_tokens = evaluation_tokens | transcript_tokens | completed_status_tokens
                    logger.info(f"[API] Completed: {len(completed_tokens)} (evals: {len(evaluation_tokens)}, transcripts: {len(transcript_tokens)}, status: {len(completed_status_tokens)})")
                except Exception as e:
                    logger.warning(f"[API] Failed to fetch completion evidence: {e}")
        
        # Separate upcoming, missed, and completed interviews
        upcoming_bookings = []
        missed_bookings = []
        completed_bookings = []
        
        if all_bookings.data:
            for booking in all_bookings.data:
                try:
                    # Parse the stored datetime - handle UTC or IST format properly
                    scheduled_at_str = booking['scheduled_at']
                    scheduled_at = parse_datetime_safe(scheduled_at_str)
                    booking_token = booking.get('token')
                    booking_status = booking.get('status', 'scheduled')
                    
                    # Get interview duration from slot if available, otherwise default to 30 minutes
                    duration_minutes = 30  # Default duration
                    slot_data = booking.get('interview_slots')
                    if slot_data:
                        if slot_data.get('duration_minutes'):
                            duration_minutes = slot_data['duration_minutes']
                        elif slot_data.get('end_time') and slot_data.get('slot_datetime'):
                            # Calculate duration from slot start and end times
                            try:
                                slot_start_str = slot_data.get('slot_datetime', '')
                                slot_end_str = slot_data.get('end_time', '')
                                if slot_start_str and slot_end_str:
                                    slot_start = parse_datetime_safe(slot_start_str)
                                    slot_end = parse_datetime_safe(slot_end_str)
                                    duration_minutes = int((slot_end - slot_start).total_seconds() / 60)
                            except (ValueError, TypeError) as e:
                                logger.warning(f"[API] Failed to calculate duration from slot times: {e}")
                                pass  # Use default duration if calculation fails
                    
                    # Calculate interview end time
                    interview_end_time = scheduled_at + timedelta(minutes=duration_minutes)
                    
                    # Debug logging for timezone issues
                    logger.info(f"[API] Booking {booking_token}: scheduled_at_str={scheduled_at_str}, parsed_ist={scheduled_at.isoformat()}, end_time={interview_end_time.isoformat()}, now_ist={now.isoformat()}, duration={duration_minutes}min")
                    
                    # Check if interview window has passed (end time, not start time)
                    time_diff = (interview_end_time - now).total_seconds() / 60  # minutes
                    logger.info(f"[API] Booking {booking_token}: Time difference = {time_diff:.1f} minutes (negative = past, positive = future)")
                    
                    if interview_end_time < now:
                        # Interview window has passed - check if it was completed
                        logger.info(f"[API] Booking {booking_token}: Interview window has passed (end_time < now)")
                        logger.info(f"[API] Booking {booking_token}: booking_status={booking_status}, in_completed_tokens={booking_token in completed_tokens}")
                        
                        # Mark as completed if:
                        # 1. Booking status is 'completed', OR
                        # 2. There's an evaluation record (interview was actually conducted), OR
                        # 3. There's a transcript (interview was conducted)
                        is_completed = (
                            booking_status == 'completed' or 
                            booking_token in completed_tokens or
                            booking.get('status') == 'completed'
                        )
                        
                        if is_completed:
                            logger.info(f"[API] Booking {booking_token}: Marking as COMPLETED")
                            completed_bookings.append(booking)
                        else:
                            # Interview window passed but not completed = missed
                            logger.info(f"[API] Booking {booking_token}: Marking as MISSED (no completion evidence)")
                            missed_bookings.append(booking)
                    else:
                        # Interview window hasn't passed yet = upcoming
                        logger.info(f"[API] Booking {booking_token}: Marking as UPCOMING (end_time >= now)")
                        upcoming_bookings.append(booking)
                except (ValueError, KeyError, TypeError) as e:
                    # If we can't parse the date, log the error with full details and skip it
                    booking_token = booking.get('token', 'unknown')
                    scheduled_at_str = booking.get('scheduled_at', 'N/A')
                    logger.error(f"[API] Failed to parse booking date for token {booking_token}: {e}")
                    logger.error(f"[API] Raw scheduled_at value: {scheduled_at_str} (type: {type(scheduled_at_str)})")
                    logger.error(f"[API] Full booking data: {booking}")
                    # Skip this booking - don't include it in any category
                    pass
        
        # Build upcoming interviews list
        upcoming = []
        for booking in sorted(upcoming_bookings, key=lambda x: x.get('scheduled_at', '')):
            slot_data = booking.get('interview_slots')
            base_url = get_frontend_url(http_request)
            interview_url = f"{base_url}/interview/{booking['token']}" if base_url else f"/interview/{booking['token']}"
            
            upcoming.append({
                'booking': {
                    'token': booking['token'],
                    'scheduled_at': booking['scheduled_at'],
                    'interview_url': interview_url,
                    'name': booking.get('name'),
                    'email': booking.get('email'),
                },
                'slot': slot_data if slot_data else None,
            })
        
        # Build missed interviews list
        missed = []
        for booking in sorted(missed_bookings, key=lambda x: x.get('scheduled_at', ''), reverse=True):
            slot_data = booking.get('interview_slots')
            base_url = get_frontend_url(http_request)
            interview_url = f"{base_url}/interview/{booking['token']}" if base_url else f"/interview/{booking['token']}"
            
            missed.append({
                'booking': {
                    'token': booking['token'],
                    'scheduled_at': booking['scheduled_at'],
                    'interview_url': interview_url,
                    'name': booking.get('name'),
                    'email': booking.get('email'),
                    'status': booking.get('status', 'scheduled'),
                },
                'slot': slot_data if slot_data else None,
            })
        
        # Build completed interviews list
        completed = []
        for booking in sorted(completed_bookings, key=lambda x: x.get('scheduled_at', ''), reverse=True):
            slot_data = booking.get('interview_slots')
            base_url = get_frontend_url(http_request)
            evaluation_url = f"{base_url}/evaluation/{booking['token']}" if base_url else f"/evaluation/{booking['token']}"
            
            completed.append({
                'booking': {
                    'token': booking['token'],
                    'scheduled_at': booking['scheduled_at'],
                    'evaluation_url': evaluation_url,
                    'name': booking.get('name'),
                    'email': booking.get('email'),
                    'status': booking.get('status', 'completed'),
                },
                'slot': slot_data if slot_data else None,
            })
        
        return MyInterviewResponse(
            upcoming=upcoming,
            missed=missed,
            completed=completed
        )
        
    except Exception as e:
        error_msg = f"Failed to fetch interview status: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )



# ==================== Student Analytics Endpoints ====================

@app.get("/api/student/analytics")
async def get_student_analytics(current_student: dict = Depends(get_current_student)):
    """
    Get analytics and progress for the current logged-in student.
    """
    try:
        user_id = current_student.get("id") or current_student.get("user_id")
        email = current_student.get("email")
        
        # 1. Get all bookings for this student
        # Try by user_id first (preferred for enrolled users)
        bookings = []
        if user_id:
            bookings = booking_service.get_bookings_by_user_id(user_id)
        
        # If no bookings found by user_id, try by email (fallback for older bookings or pre-enrollment)
        if not bookings and email:
            bookings = booking_service.get_bookings_by_email(email)
            
        booking_tokens = [b["token"] for b in bookings if b.get("token")]
        
        # 2. Calculate analytics using the service
        analytics = evaluation_service.get_student_analytics(booking_tokens)
        
        return analytics
        
    except Exception as e:
        logger.error(f"[API] Error fetching student analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch analytics: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.api.main:app",
        host=config.server.host,
        port=config.server.port,
        reload=True,
    )

