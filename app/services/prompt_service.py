"""
Prompt Service

Manages retrieval and caching of system prompts from Supabase.
"""

from typing import Optional, Dict
from datetime import datetime, timedelta
import asyncio

from app.utils.logger import get_logger
from app.config import Config
from supabase import create_client, Client
from app.utils.datetime_utils import get_now_ist

logger = get_logger(__name__)


class PromptService:
    """Service for managing system prompts with caching"""
    
    _instance = None
    _cache: Dict[str, Dict] = {}
    _cache_ttl = timedelta(minutes=15)  # Cache duration
    
    def __new__(cls, config: Optional[Config] = None):
        if cls._instance is None:
            cls._instance = super(PromptService, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance
    
    def __init__(self, config: Optional[Config] = None):
        if self.initialized:
            return
            
        if not config:
            from app.config import get_config
            config = get_config()
            
        self.config = config
        self.supabase: Client = create_client(
            config.supabase.url, 
            config.supabase.service_role_key
        )
        self.initialized = True
        logger.info("[PromptService] Initialized")
    
    async def get_prompt(self, key: str, default_content: Optional[str] = None) -> str:
        """
        Get prompt content by key.
        Checks cache first, then fetches from DB.
        Returns default_content if not found (and logs warning).
        """
        # Check cache
        cached = self._cache.get(key)
        if cached:
            if get_now_ist() < cached['expiry']:
                return cached['content']
            else:
                del self._cache[key]
        
        # Fetch from DB
        try:
            # Run in thread pool since supabase-py is synchronous
            response = await asyncio.to_thread(
                lambda: self.supabase.table('system_prompts')
                .select('content')
                .eq('key', key)
                .execute()
            )
            
            if response.data and len(response.data) > 0:
                content = response.data[0]['content']
                
                # Update cache
                self._cache[key] = {
                    'content': content,
                    'expiry': get_now_ist() + self._cache_ttl
                }
                
                return content
            else:
                logger.warning(f"[PromptService] Prompt key '{key}' not found in DB")
                
        except Exception as e:
            logger.error(f"[PromptService] Error fetching prompt '{key}': {str(e)}")
            
        # Return default if provided, otherwise empty string
        if default_content:
            logger.info(f"[PromptService] Using default content for '{key}'")
            return default_content
            
        return ""

    async def refresh_cache(self, key: str) -> None:
        """Force refresh a specific prompt in cache"""
        if key in self._cache:
            del self._cache[key]
        await self.get_prompt(key)

# Global singleton accessor
_prompt_service: Optional[PromptService] = None

def get_prompt_service(config: Optional[Config] = None) -> PromptService:
    global _prompt_service
    if not _prompt_service:
        _prompt_service = PromptService(config)
    return _prompt_service
