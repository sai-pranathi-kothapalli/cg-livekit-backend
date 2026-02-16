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
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, EmailStr, Field
from urllib.parse import urlparse
import asyncio
import random
import json
import pandas as pd
from io import BytesIO
import os
from urllib.parse import urlparse

from livekit import api as livekit_api
from slowapi.errors import RateLimitExceeded

from app.config import Config, get_config
from app.db.supabase import get_supabase
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
from app.utils.logger import get_logger
from app.utils.auth_dependencies import get_current_admin, get_current_student, get_optional_student
from app.utils.datetime_utils import IST, get_now_ist, to_ist, parse_datetime_safe
from app.utils.api_key import get_api_key

logger = get_logger(__name__)
config = get_config()

from app.utils.limiter import limiter
from slowapi import _rate_limit_exceeded_handler

# Create FastAPI app
app = FastAPI(
    title="Interview Scheduling API",
    description="API for application upload and interview scheduling",
    version="1.0.0",
)

app.state.limiter = limiter

app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Log detailed validation errors for debugging 400s."""
    errors = exc.errors()
    logger.error(f"[API] Validation Error: {json.dumps(errors, indent=2)}")
    return Response(
        content=json.dumps({"detail": errors, "message": "Validation failed"}),
        status_code=status.HTTP_400_BAD_REQUEST,
        media_type="application/json"
    )

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

from app.services.container import (
    resume_service,
    booking_service,
    email_service,
    system_instructions_service,
    admin_service,
    auth_service,
    user_service,
    slot_service,
    assignment_service,
    transcript_storage_service,
    evaluation_service,
)


# Include routers
from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.api.bookings import router as bookings_router
from app.api.interviews import router as interviews_router
from app.api.slots import router as slots_router
from app.api.users import router as users_router
from app.api.resume import router as resume_router
from app.api.student import router as student_router

app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
app.include_router(admin_router, prefix="/api/admin", tags=["Admin"])
app.include_router(bookings_router, prefix="/api/bookings", tags=["Bookings"])
app.include_router(interviews_router, prefix="/api/interviews", tags=["Interviews"])
app.include_router(slots_router, prefix="/api/slots", tags=["Slots"])
app.include_router(users_router, prefix="/api/users", tags=["Users"])
app.include_router(resume_router, prefix="/api/resume", tags=["Resume"])
app.include_router(student_router, prefix="/api/student", tags=["Student"])


@app.on_event("startup")
async def startup_log_db():
    """Log Supabase connection status on startup."""
    try:
        client = get_supabase()
        logger.info("[API] Supabase client initialized successfully")
    except Exception as e:
        logger.warning(f"[API] Supabase initialization warning: {e}")


@app.get("/health", tags=["System"])
async def health():
    """Liveness probe: returns 200 if the process is running."""
    return {"status": "ok"}


@app.get("/ready", tags=["System"])
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




# Admin Models
class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    error: Optional[str] = None


@app.get("/", tags=["System"])
async def root():
    """Health check endpoint"""
    return {"status": "ok", "service": "interview-scheduling-api"}


@app.get("/api/secure-data", tags=["System"])
async def get_secure_data(api_key: str = Depends(get_api_key)):
    """
    Example protected endpoint.
    Requires valid X-API-Key header.
    """
    return {
        "message": "Secure data accessed successfully",
        "timestamp": get_now_ist().isoformat(),
        "method": "API Key"
    }


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


@app.get("/api/public/interview-config", response_model=InterviewAccessConfigResponse, tags=["Config"])
async def get_interview_access_config():
    """
    Public endpoint (no auth). Returns whether interview links require login.
    Frontend uses this to decide whether to redirect to login or allow direct access.
    """
    return InterviewAccessConfigResponse(
        require_login_for_interview=config.REQUIRE_LOGIN_FOR_INTERVIEW,
    )


@app.get("/api/files/{file_id}", tags=["Bookings"])
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


# ==================== Student Analytics Endpoints ====================




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.api.main:app",
        host=config.server.host,
        port=config.server.port,
        reload=True,
    )

