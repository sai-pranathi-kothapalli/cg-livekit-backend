import hashlib
import logging
from datetime import datetime
from fastapi import Header, HTTPException, status

logger = logging.getLogger(__name__)


class IntegrationAuth:
    """
    Validates X-API-Key headers for service-to-service integration calls.
    Completely separate from JWT user auth.
    """

    def __init__(self, supabase_client):
        self.client = supabase_client

    def hash_key(self, plain_key: str) -> str:
        """Hash an API key using SHA-256 (same method used during key generation)."""
        return hashlib.sha256(plain_key.encode()).hexdigest()

    async def verify_key(self, x_api_key: str = Header(..., alias="X-API-Key")) -> dict:
        """
        FastAPI dependency that validates the X-API-Key header.
        
        Usage in routes:
            @router.post("/api/integration/something")
            async def something(api_key_info: dict = Depends(integration_auth.verify_key)):
                # api_key_info contains: id, name, permissions
                ...
        """
        if not x_api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing X-API-Key header"
            )

        # Hash the provided key and look it up
        hashed = self.hash_key(x_api_key)

        try:
            result = self.client.table('api_keys').select(
                'id, name, permissions, status'
            ).eq(
                'hashed_key', hashed
            ).limit(1).execute()

            if not result.data:
                logger.warning(f"Invalid API key attempt (hash prefix: {hashed[:8]}...)")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid API key"
                )

            key_data = result.data[0]

            # Check if key is active
            if key_data.get('status') != 'active':
                logger.warning(f"Revoked API key used: {key_data.get('name')}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key has been revoked"
                )

            # Update last_used_at timestamp (fire and forget — don't block the request)
            try:
                self.client.table('api_keys').update({
                    'last_used_at': datetime.utcnow().isoformat()
                }).eq('id', key_data['id']).execute()
            except Exception:
                pass  # Non-critical — don't fail the request

            logger.info(f"Integration API call authenticated: {key_data.get('name')}")

            return {
                'key_id': key_data['id'],
                'key_name': key_data.get('name'),
                'permissions': key_data.get('permissions', []),
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"API key verification error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service error"
            )
