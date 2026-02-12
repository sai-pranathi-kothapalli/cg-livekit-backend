"""
Users module router.

Currently includes the router from `app.api.users`. As endpoints are
gradually moved, they can live in either this module or the API router,
while keeping paths and response schemas identical.
"""

from fastapi import APIRouter

from app.api import users as api_users

router = APIRouter()
router.include_router(api_users.router)

__all__ = ["router"]

