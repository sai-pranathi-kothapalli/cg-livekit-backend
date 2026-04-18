from fastapi import APIRouter, HTTPException, Request, status

from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    ChangePasswordRequest,
    PasswordResetRequestSchema,
    PasswordResetVerifySchema,
    StudentRegisterRequest,
    AdminLoginRequest,
    AdminLoginResponse,
)
from app.services.container import (
    auth_service,
    admin_service,
    otp_service,
    email_service,
)
from app.utils.logger import get_logger
from app.utils.limiter import limiter
from app.utils.exceptions import SupabaseUnavailableError

logger = get_logger(__name__)

# All authentication-related endpoints
router = APIRouter(tags=["Auth"])


@router.post("/login", response_model=LoginResponse)
@limiter.limit("15/minute")
def login(request: Request, body: LoginRequest):
  """
  Unified login endpoint - automatically detects admin or student.
  Rate limited to 15 requests per minute per IP.
  """
  try:
    identifier = body.get_login_identifier()
    if not identifier:
        raise HTTPException(status_code=400, detail="Email or username is required")
        
    logger.info(f"[API] Login attempt: {identifier}")

    # Unified authentication -> single database round trip
    user = auth_service.authenticate_unified(identifier, body.password)
    
    if user:
      role = user.get('role', 'student')
      if role in ['admin', 'manager']:
        token = auth_service.generate_token(
          user_id=user['id'],
          role=role,
          username=user.get('username') or user.get('email')
        )
        logger.info(f"[API] ✅ {role.capitalize()} login successful: {identifier}")
        return LoginResponse(
          success=True,
          token=token,
          user={
            'id': user['id'],
            'username': user.get('username') or user.get('email'),
            'role': role,
            'email': user.get('email'),
            'name': user.get('name'),
          },
          must_change_password=user.get('must_change_password', False)
        )
      else:
        # Student
        token = auth_service.generate_token(
          user_id=user['id'],
          role='student',
          email=user['email']
        )
        logger.info(f"[API] ✅ Student login successful: {identifier}")
        return LoginResponse(
          success=True,
          token=token,
          user={
            'id': user['id'],
            'email': user['email'],
            'name': user.get('name'),
            'phone': user.get('phone'),
            'role': 'student',
            'username': user['email'],
          },
          must_change_password=user.get('must_change_password', False)
        )

    # Authentication failed
    logger.warning(f"[API] Login failed: {identifier}")
    return LoginResponse(
      success=False,
      error="Invalid credentials"
    )

  except SupabaseUnavailableError as e:
    raise HTTPException(
      status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
      detail=e.message,
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


@router.post("/request-password-reset")
@limiter.limit("5/minute")
async def request_password_reset(request: Request, body: PasswordResetRequestSchema):
    """
    Step 1 of password reset: send a 6-digit OTP to the provided email.

    Always returns the same response whether the email exists or not,
    to prevent email enumeration attacks.
    Rate limited to 5 requests/minute per IP.
    """
    _SAFE_RESPONSE = {
        "message": "If an account with this email exists, a reset code has been sent.",
        "expires_in_minutes": otp_service.OTP_EXPIRY_MINUTES,
    }
    try:
        email = body.email.strip().lower()
        user = auth_service.get_user_by_email(email)

        # ── ON-DEMAND REGISTRATION ───────────────────────────────────────────
        # If user is not in 'users' table, check if they are in 'enrolled_users'.
        # If so, automatically create their student account so they can reset.
        if not user:
            enrolled_user = user_service.get_user_by_email(email)
            if enrolled_user:
                logger.info(f"[API] 🆕 Auto-registering enrolled student for password reset: {email}")
                try:
                    # Generate a random temp password (will be reset anyway)
                    temp_pass = auth_service.generate_temporary_password()
                    user = auth_service.register_student(
                        email=email,
                        password=temp_pass,
                        name=enrolled_user.get('name', 'Student'),
                        phone=enrolled_user.get('phone'),
                        must_change_password=True
                    )
                except Exception as reg_err:
                    logger.error(f"[API] Failed auto-registration for {email}: {reg_err}")

        if user:
            otp = otp_service.create_otp(email)
            # Fire-and-forget: don't block or leak errors to caller
            try:
                await email_service.send_otp_email(email, otp)
                logger.info(f"[API] OTP email sent to {email}")
            except Exception as email_err:
                logger.error(f"[API] OTP email failed for {email}: {email_err}")
        else:
            logger.info(f"[API] Password reset requested for unknown email: {email} (ignored)")

        return _SAFE_RESPONSE

    except Exception as e:
        logger.error(f"[API] request_password_reset error: {e}", exc_info=True)
        # Always return safe response — never leak internal errors
        return _SAFE_RESPONSE


@router.post("/reset-password")
async def reset_password(body: PasswordResetVerifySchema):
    """
    Step 2 of password reset: verify OTP and set a new password.

    Requires email + 6-digit OTP (from email) + new password.
    OTP is validated for expiry, correct value, and attempt count.
    """
    try:
        email = body.email.strip().lower()

        # Verify OTP — raises ValueError with user-friendly message on failure
        otp_service.verify_otp(email, body.otp)

        # OTP is valid — reset the password
        ok = auth_service.reset_password(email, body.new_password)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update password. Please try again."
            )

        logger.info(f"[API] ✅ Password reset successfully for {email}")
        return {"success": True, "message": "Password has been reset successfully."}

    except ValueError as e:
        # OTP verification failure — return the specific reason to the user
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] reset_password error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred. Please try again."
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


