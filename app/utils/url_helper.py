from typing import Optional
from fastapi import Request
from urllib.parse import urlparse
from app.config import get_config
from app.utils.logger import get_logger

logger = get_logger(__name__)
config = get_config()

def get_frontend_url(request: Optional[Request] = None) -> str:
    """
    Get frontend URL from request origin/referer, fallback to config.
    
    Args:
        request: FastAPI Request object (optional)
        
    Returns:
        Frontend base URL (without trailing slash)
    """
    if request:
        # Try Origin header first (more reliable for CORS requests)
        origin = request.headers.get('Origin')
        if origin:
            parsed = urlparse(origin)
            base_url = f"{parsed.scheme}://{parsed.netloc}".rstrip('/')
            if base_url:
                logger.debug(f"[API] Using frontend URL from Origin header: {base_url}")
                return base_url
        
        # Fallback to Referer header
        referer = request.headers.get('Referer')
        if referer:
            parsed = urlparse(referer)
            base_url = f"{parsed.scheme}://{parsed.netloc}".rstrip('/')
            if base_url:
                logger.debug(f"[API] Using frontend URL from Referer header: {base_url}")
                return base_url
    
    # Final fallback to config
    fallback_url = config.server.frontend_url.rstrip('/') if config.server.frontend_url else ''
    if fallback_url:
        logger.debug(f"[API] Using frontend URL from config: {fallback_url}")
    return fallback_url
