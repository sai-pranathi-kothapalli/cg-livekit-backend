"""
Resume/application upload related Pydantic schemas.
Moved from app.api.main without changing fields or validation.
"""

from typing import Optional

from pydantic import BaseModel


class UploadApplicationResponse(BaseModel):
    applicationUrl: str
    applicationText: Optional[str] = None
    extractionError: Optional[str] = None


__all__ = ["UploadApplicationResponse"]

