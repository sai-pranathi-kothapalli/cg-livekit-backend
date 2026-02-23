"""
Application entrypoint.

Uses the FastAPI app from app.api.main (all routers registered there with
/api/auth, /api/admin, etc.). Duplicate registration removed so only
/api/auth/login and /api/auth/admin/login exist (no /login, /admin/login).
"""

from app.api.main import app  # type: ignore  # noqa: F401
from app.utils.logger import get_logger, setup_logging
from app.config import get_config

config = get_config()
setup_logging(config)
logger = get_logger(__name__)

