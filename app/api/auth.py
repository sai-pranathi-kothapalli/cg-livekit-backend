from fastapi import APIRouter, HTTPException, Request, status

from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    ChangePasswordRequest,
    ResetPasswordRequest,
    StudentRegisterRequest,
    AdminLoginRequest,
    AdminLoginResponse,
)
from app.services.container import (
    auth_service,
    admin_service,
)
from app.utils.logger import get_logger
from app.utils.limiter import limiter

logger = get_logger(__name__)

# All authentication-related endpoints
router = APIRouter(tags=["Auth"])


@router.post("/login", response_model=LoginResponse)
@limiter.limit("15/minute")
async def login(request: Request, body: LoginRequest):
  """
  Unified login endpoint - automatically detects admin or student.
  Rate limited to 15 requests per minute per IP.
  """
  try:
    logger.info(f"[API] Login attempt: {body.username}")

    # Try admin authentication first
    admin_user = auth_service.authenticate_admin(body.username, body.password)
    if admin_user:
      token = auth_service.generate_token(
        user_id=admin_user['id'],
        role=admin_user['role'],
        username=admin_user['username']
      )
      logger.info(f"[API] ✅ {admin_user['role'].capitalize()} login successful: {body.username}")
      return LoginResponse(
        success=True,
        token=token,
        user={
          'id': admin_user['id'],
          'username': admin_user['username'],
          'role': admin_user['role'],
          'email': admin_user.get('email'),
          'name': admin_user.get('name'),
        },
        must_change_password=False
      )

    # Try student authentication (email-based)
    student_user = auth_service.authenticate_student(body.username, body.password)
    if student_user:
      token = auth_service.generate_token(
        user_id=student_user['id'],
        role='student',
        email=student_user['email']
      )
      logger.info(f"[API] ✅ Student login successful: {body.username}")
      must_change_password = student_user.get('must_change_password', False)
      return LoginResponse(
        success=True,
        token=token,
        user={
          'id': student_user['id'],
          'email': student_user['email'],
          'name': student_user.get('name'),
          'phone': student_user.get('phone'),
          'role': 'student',
          'username': student_user['email'],
        },
        must_change_password=must_change_password
      )

    # Authentication failed
    logger.warning(f"[API] Login failed: {body.username}")
    return LoginResponse(
      success=False,
      error="Invalid credentials"
    )

  except Exception as e:
    logger.error(f"[API] Login error: {str(e)}", exc_info=True)
    return LoginResponse(
      success=False,
      error=str(e)
    )


@router.post("/change-password")
async def change_password(request: ChangePasswordRequest):
  """
  Change password for any user (student, manager, admin).
  """
  success = auth_service.change_user_password(
    request.email,
    request.old_password,
    request.new_password
  )
  if not success:
    logger.warning(f"[API] Password change failed for {request.email}: Invalid email or old password")
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="Invalid email or current password"
    )
  logger.info(f"[API] ✅ Password changed successfully for {request.email}")
  return {"success": True, "message": "Password updated successfully"}


@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest):
  """
  Reset password for a student or manager (forgot password flow).
  In this implementation, we allow resetting by email for simplicity.
  In production, this would require a verification token or OTP.
  """
  try:
    # Check if user exists and is a student or manager
    user = auth_service.get_user_by_email(request.email)
    if not user or user.get('role') not in ['student', 'manager']:
      logger.warning(f"[API] Reset password failed: User {request.email} not found or invalid role")
      raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="User with this email not found"
      )

    ok = auth_service.reset_password(request.email, request.new_password)
    if not ok:
      raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to reset password"
      )

    logger.info(f"[API] ✅ Password reset successfully for {request.email} ({user.get('role')})")
    return {"success": True, "message": "Password reset successfully"}
  except HTTPException:
    raise
  except Exception as e:
    logger.error(f"[API] Reset password error: {str(e)}")
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail=str(e)
    )


@router.post("/student/register", response_model=LoginResponse)
async def student_register(request: StudentRegisterRequest):
  """
  Register a new student account.
  """
  try:
    logger.info(f"[API] Student registration attempt: {request.email}")

    # Validate password strength
    if len(request.password) < 12:
      raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Password must be at least 12 characters long"
      )

    # Register student
    try:
      student = auth_service.register_student(
        email=request.email,
        password=request.password,
        name=request.name,
        phone=request.phone,
        must_change_password=False  # Students registering themselves don't need to change password
      )
    except Exception as e:
      error_msg = str(e)
      # Check if student already exists
      if "already registered" in error_msg.lower() or "unique constraint" in error_msg.lower() or "already exists" in error_msg.lower():
        logger.warning(f"[API] Student registration failed: Email {request.email} is already registered")
        raise HTTPException(
          status_code=status.HTTP_400_BAD_REQUEST,
          detail=f"Email {request.email} is already registered"
        )
      raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Registration failed: {error_msg}"
      )

    # Generate token
    token = auth_service.generate_token(
      user_id=student['id'],
      role='student',
      email=student['email']
    )

    logger.info(f"[API] ✅ Student registered successfully: {request.email}")

    return LoginResponse(
      success=True,
      token=token,
      user={
        'id': student['id'],
        'email': student['email'],
        'name': student.get('name'),
        'phone': student.get('phone'),
        'role': 'student',
        'username': student['email'],
      },
      must_change_password=False
    )

  except HTTPException:
    raise
  except Exception as e:
    error_msg = f"Registration failed: {str(e)}"
    logger.error(f"[API] {error_msg}", exc_info=True)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail=error_msg
    )


@router.post("/admin/login", response_model=AdminLoginResponse)
@limiter.limit("15/minute")
async def admin_login(request: Request, body: AdminLoginRequest):
  """
  Admin authentication endpoint. Rate limited to 15/minute per IP.
  """
  try:
    admin_user = admin_service.authenticate(body.username, body.password)

    if admin_user:
      token = admin_service.generate_token()
      logger.info(f"[API] Admin login successful: {body.username}")
      return AdminLoginResponse(success=True, token=token)
    else:
      logger.warning(f"[API] Admin login failed: {body.username}")
      return AdminLoginResponse(success=False, error="Invalid credentials")
  except Exception as e:
    logger.error(f"[API] Admin login error: {str(e)}", exc_info=True)
    return AdminLoginResponse(success=False, error=str(e))


