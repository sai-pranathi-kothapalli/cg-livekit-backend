"""
Users module service facade.

Thin wrapper around the core `UserService` in `app.services.user_service`.
"""

from app.config import get_config
from app.services.user_service import UserService

config = get_config()
user_service = UserService(config)

__all__ = ["user_service", "UserService"]

