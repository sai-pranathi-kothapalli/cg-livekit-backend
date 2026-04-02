"""
Authentication Dependencies

FastAPI dependencies for route protection and strict role-based access control.
All JWT verification happens in get_current_user; role enforcement is layered on top.
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.auth_service import AuthService
from app.config import Config, get_config
from app.utils.logger import get_logger

logger = get_logger(__name__)

security = HTTPBearer()


def get_auth_service() -> AuthService:
    """Get auth service instance."""
    config = get_config()
    return AuthService(config)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service: AuthService = Depends(get_auth_service)
) -> dict:
    """
    Base auth dependency. Validates JWT signature, expiry, and required claims.
    Returns the user dict from the database.

    Raises:
        401 — token missing, invalid signature, expired, or user not found
    """
    token = credentials.credentials
    payload = auth_service.verify_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("user_id")
    role = payload.get("role")

    if not user_id or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing required claims.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Only allow known roles — reject anything else immediately
    if role not in ("admin", "manager", "student"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: unrecognised role.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch the user record from DB to confirm they still exist and are active
    if role == "admin":
        user = auth_service.get_admin_by_id(user_id)
    elif role == "manager":
        user = auth_service.get_user_by_id(user_id)
    else:  # student
        user = auth_service.get_student_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or has been deleted.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.debug(f"[Auth] ✅ Authenticated user_id={user_id} role={role}")
    return user


# ─── Role-specific dependencies ───────────────────────────────────────────────

async def require_admin(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Strict admin-only access. Role MUST be 'admin'.
    Managers cannot access routes protected by this dependency.

    Raises:
        403 — if role is not exactly 'admin'
    """
    if current_user.get("role") != "admin":
        logger.warning(
            f"[Auth] 403 require_admin: user {current_user.get('id')} "
            f"has role='{current_user.get('role')}', admin required"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required. Your account does not have permission."
        )
    return current_user


async def require_manager_or_admin(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Manager-or-admin access. Role must be 'admin' or 'manager'.
    Students cannot access routes protected by this dependency.

    Raises:
        403 — if role is not 'admin' or 'manager'
    """
    if current_user.get("role") not in ("admin", "manager"):
        logger.warning(
            f"[Auth] 403 require_manager_or_admin: user {current_user.get('id')} "
            f"has role='{current_user.get('role')}', admin/manager required"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager or admin access required. Your account does not have permission."
        )
    return current_user


# Keep original name as alias for backward compatibility with existing imports
get_current_admin = require_manager_or_admin


async def require_student(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Student-only access. Role MUST be 'student'.
    Admins and managers cannot access routes protected by this dependency.

    Raises:
        403 — if role is not 'student'
    """
    if current_user.get("role") != "student":
        logger.warning(
            f"[Auth] 403 require_student: user {current_user.get('id')} "
            f"has role='{current_user.get('role')}', student required"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student access required."
        )
    return current_user


# Keep original name as alias for backward compatibility with existing imports
get_current_student = require_student


# ─── Optional auth (routes that work with or without a token) ─────────────────

def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    auth_service: AuthService = Depends(get_auth_service)
) -> Optional[dict]:
    """
    Returns the current user if a valid token is provided, otherwise None.
    Used for endpoints that behave differently when authenticated vs anonymous.
    """
    if not credentials:
        return None

    payload = auth_service.verify_token(credentials.credentials)
    if not payload:
        return None

    user_id = payload.get("user_id")
    role = payload.get("role")

    if not user_id or not role:
        return None

    if role == "admin":
        return auth_service.get_admin_by_id(user_id)
    elif role == "manager":
        return auth_service.get_user_by_id(user_id)
    elif role == "student":
        return auth_service.get_student_by_id(user_id)

    return None


async def get_optional_student(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    auth_service: AuthService = Depends(get_auth_service)
) -> Optional[dict]:
    """
    Returns the current student user if a valid student token is provided, otherwise None.
    Non-student tokens (admin, manager) are treated as unauthenticated here.
    """
    if not credentials:
        return None

    payload = auth_service.verify_token(credentials.credentials)
    if not payload:
        return None

    user_id = payload.get("user_id")
    role = payload.get("role")

    if not user_id or role != "student":
        return None

    return auth_service.get_student_by_id(user_id)
