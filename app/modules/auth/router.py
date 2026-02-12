"""
Auth module router.

For now this simply reuses the router from `app.api.auth`.
During refactoring, concrete auth endpoints can be defined here
or moved into `app.api.auth` and included.
"""

from fastapi import APIRouter

from app.api import auth as api_auth

router = APIRouter()
router.include_router(api_auth.router)

__all__ = ["router"]

