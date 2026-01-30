"""
Prompt Service

Manages retrieval and caching of system prompts from MongoDB.
"""

from typing import Optional, Dict
from datetime import timedelta
import asyncio

from app.config import Config
from app.db.mongo import get_database
from app.utils.logger import get_logger
from app.utils.datetime_utils import get_now_ist

logger = get_logger(__name__)


class PromptService:
    """Service for managing system prompts with caching"""

    _instance = None
    _cache: Dict[str, Dict] = {}
    _cache_ttl = timedelta(minutes=15)

    def __new__(cls, config: Optional[Config] = None):
        if cls._instance is None:
            cls._instance = super(PromptService, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self, config: Optional[Config] = None):
        if getattr(self, "initialized", False):
            return
        if not config:
            from app.config import get_config
            config = get_config()
        self.config = config
        self.db = get_database(config)
        self.col = self.db["system_prompts"]
        self.initialized = True
        logger.info("[PromptService] Initialized")

    async def get_prompt(self, key: str, default_content: Optional[str] = None) -> str:
        cached = self._cache.get(key)
        if cached and get_now_ist() < cached["expiry"]:
            return cached["content"]
        if cached:
            del self._cache[key]
        try:
            def fetch():
                doc = self.col.find_one({"key": key})
                return doc.get("content") if doc else None
            content = await asyncio.to_thread(fetch)
            if content:
                self._cache[key] = {"content": content, "expiry": get_now_ist() + self._cache_ttl}
                return content
        except Exception as e:
            logger.error(f"[PromptService] Error fetching prompt '{key}': {str(e)}")
        if default_content:
            logger.info(f"[PromptService] Using default content for '{key}'")
            return default_content
        return ""

    async def refresh_cache(self, key: str) -> None:
        if key in self._cache:
            del self._cache[key]
        await self.get_prompt(key)


_prompt_service: Optional[PromptService] = None


def get_prompt_service(config: Optional[Config] = None) -> PromptService:
    global _prompt_service
    if not _prompt_service:
        _prompt_service = PromptService(config)
    return _prompt_service
