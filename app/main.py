"""
Application entrypoint.

For now this re-exports the existing FastAPI `app` instance from
`app.api.main` and registers modular routers so that current
imports keep working while we incrementally refactor.
"""

from app.api.main import app  # type: ignore  # noqa: F401
from app.api import auth as auth_api
from app.api import admin as admin_api
from app.api import bookings as bookings_api
from app.utils.logger import get_logger, setup_logging
from app.config import get_config

config = get_config()
setup_logging(config)
logger = get_logger(__name__)

from app.api import auth as auth_api
from app.api import admin as admin_api
from app.api import bookings as bookings_api
from app.api import interviews as interviews_api
from app.api import resume as resume_api
from app.api import slots as slots_api
from app.api import users as users_api

# Register routers without changing paths or behavior.
app.include_router(auth_api.router)
app.include_router(admin_api.router)
app.include_router(bookings_api.router)
app.include_router(interviews_api.router)
app.include_router(resume_api.router)
app.include_router(slots_api.router)
app.include_router(users_api.router)


