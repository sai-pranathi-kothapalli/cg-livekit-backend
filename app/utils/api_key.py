import hashlib
import secrets
from typing import Optional
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from app.config import get_config

# Define the security scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def hash_api_key(api_key: str) -> str:
    """
    Hash an API key using SHA-256.
    
    Args:
        api_key: The raw API key string
        
    Returns:
        SHA-256 hash of the key
    """
    return hashlib.sha256(api_key.encode()).hexdigest()

def generate_api_key() -> str:
    """
    Generate a secure random API key.
    
    Returns:
        A securely generated random string (32 bytes hex)
    """
    return secrets.token_hex(32)

async def get_api_key(
    api_key: Optional[str] = Security(api_key_header),
) -> str:
    """
    Validate the API Key from the X-API-Key header.
    
    Args:
        api_key: The API key from header
        
    Returns:
        The valid API key (if valid)
        
    Raises:
        HTTPException: If key is missing (401) or invalid (403)
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    config = get_config()
    stored_hash = config.api_key.key_hash
    
    if not stored_hash:
        # If no hash is configured, deny all access for safety
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfiguration: No API key hash set"
        )
        
    # Hash the incoming key and compare
    incoming_hash = hash_api_key(api_key)
    
    # Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(incoming_hash, stored_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key",
        )
        
    return api_key
