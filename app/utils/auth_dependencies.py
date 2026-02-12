"""
Authentication Dependencies

FastAPI dependencies for route protection and authentication.
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
    """Get auth service instance"""
    config = get_config()
    return AuthService(config)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service: AuthService = Depends(get_auth_service)
) -> dict:
    """
    Get current authenticated user from JWT token.
    
    Raises:
        HTTPException: If token is invalid or missing
    """
    token = credentials.credentials
    payload = auth_service.verify_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get('user_id')
    role = payload.get('role')
    
    if not user_id or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Fetch user from database based on role
    if role == 'admin':
        user = auth_service.get_admin_by_id(user_id)
    elif role == 'manager':
        user = auth_service.get_user_by_id(user_id)
    elif role == 'student':
        user = auth_service.get_student_by_id(user_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user role",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.debug(f"[Auth] Authenticated user {user_id} with role {role}")
    return user


async def get_current_admin(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Get current admin user. Requires admin role.
    
    Raises:
        HTTPException: If user is not an admin
    """
    if current_user.get('role') not in ('admin', 'manager'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Manager access required"
        )
    return current_user


async def get_current_student(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Get current student user. Requires student role.
    
    Raises:
        HTTPException: If user is not a student
    """
    if current_user.get('role') != 'student':
        logger.warning(f"[Auth] 403 Forbidden: User {current_user.get('id')} has role {current_user.get('role')}, student required")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student access required"
        )
    return current_user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    auth_service: AuthService = Depends(get_auth_service)
) -> Optional[dict]:
    """
    Get current user if token is provided, otherwise return None.
    Used for endpoints that work both with and without authentication.
    """
    if not credentials:
        return None
    
    token = credentials.credentials
    payload = auth_service.verify_token(token)
    
    if not payload:
        return None
    
    user_id = payload.get('user_id')
    role = payload.get('role')
    
    if not user_id or not role:
        return None
    
    if role == 'admin':
        return auth_service.get_admin_by_id(user_id)
    elif role == 'manager':
        return auth_service.get_user_by_id(user_id)
    elif role == 'student':
        return auth_service.get_student_by_id(user_id)
    
    return None


async def get_optional_student(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    auth_service: AuthService = Depends(get_auth_service)
) -> Optional[dict]:
    """
    Get current student user if token is provided, otherwise return None.
    Used for endpoints that require student authentication when accessing interviews.
    """
    if not credentials:
        return None
    
    token = credentials.credentials
    payload = auth_service.verify_token(token)
    
    if not payload:
        return None
    
    user_id = payload.get('user_id')
    role = payload.get('role')
    
    if not user_id or not role:
        return None
    
    # Only return if role is student
    if role != 'student':
        return None
    
    return auth_service.get_student_by_id(user_id)
