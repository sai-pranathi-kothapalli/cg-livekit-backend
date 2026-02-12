"""
Auth module service facade.

Thin wrapper around the core `AuthService` in `app.services.auth_service`
so feature code can import from `app.modules.auth.service` while
keeping the underlying implementation shared.
"""

from app.config import get_config
from app.services.auth_service import AuthService

config = get_config()
auth_service = AuthService(config)

__all__ = ["auth_service", "AuthService"]

