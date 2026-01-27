"""
Run FastAPI HTTP Server

Starts the FastAPI server for handling resume upload and interview scheduling.
"""

import os
import uvicorn
from app.config import get_config

if __name__ == "__main__":
    config = get_config()
    
    # Railway provides PORT environment variable, use it if available
    # Otherwise fall back to config
    port = int(os.environ.get("PORT", config.server.port))
    host = os.environ.get("HOST", config.server.host)
    
    uvicorn.run(
        "app.api.main:app",
        host=host,
        port=port,
        reload=False,  # Disable reload for production
        log_level="info",
    )

