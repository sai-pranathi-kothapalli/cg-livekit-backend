"""
Configuration Management

Centralized configuration management using environment variables
with proper validation and type safety.
"""

import os
from typing import Optional
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


# Load environment variables from .env in backend directory (resolve to absolute path)
_backend_root = Path(__file__).resolve().parent.parent
_env_path = _backend_root / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=str(_env_path))
else:
    # Fallback to .env.local in parent directory (for backward compatibility)
    _env_path_fallback = _backend_root.parent / ".env.local"
    if _env_path_fallback.exists():
        load_dotenv(dotenv_path=str(_env_path_fallback))
    # Also load from current working directory so "python backend_server.py" from backend root picks up .env
    load_dotenv()

# Note: Google API key setup removed - using self-hosted OpenAI-compatible models only


@dataclass
class LiveKitConfig:
    """LiveKit agent configuration"""
    api_key: str
    api_secret: str
    url: str
    agent_name: str = "my-interviewer"


@dataclass
class OpenAIConfig:
    """OpenAI / Self-hosted configuration"""
    api_key: str
    llm_base_url: str
    tts_base_url: str
    stt_base_url: str
    llm_model: str = "qwen2-5-7b-instruct"
    tts_model: str = "kokoro"
    stt_model: str = "small.en"
    tts_voice: str = "af_bella"
    # Enable/disable flags for self-hosted services
    stt_enabled: bool = True
    llm_enabled: bool = True
    tts_enabled: bool = True


@dataclass
class GeminiConfig:
    """Google Gemini LLM configuration (primary LLM)"""
    api_key: str
    model: str = "gemini-1.5-flash"


@dataclass
class SileroVADConfig:
    """Silero VAD configuration"""
    min_speech_duration: float = 0.2  # Reduced for better sensitivity
    min_silence_duration: float = 5.0  # Seconds of silence before considering user done (wait before next question)
    activation_threshold: float = 0.5  # Standard sensitivity


@dataclass
class MongoConfig:
    """MongoDB configuration"""
    uri: str
    db_name: Optional[str] = None  # Database name; if unset, uses 'interview'


@dataclass
class SMTPConfig:
    """SMTP email configuration"""
    host: Optional[str] = None
    port: int = 587
    secure: bool = False
    user: Optional[str] = None
    password: Optional[str] = None
    from_name: str = "Sreedhar's CCE Team"
    from_email: Optional[str] = None


@dataclass
class ServerConfig:
    """HTTP server configuration"""
    host: str
    port: int
    frontend_url: str = ""
    # Public URL for links in emails (login, interview). Use e.g. https://interview.skillifire.com
    public_frontend_url: str = ""


@dataclass
class Config:
    """Main application configuration"""
    
    # LiveKit configuration
    livekit: LiveKitConfig
    
    # AI Services - Self-hosted (STT, TTS, and LLM fallback Qwen)
    openai: OpenAIConfig
    silero_vad: SileroVADConfig
    
    # AI Services - LLM primary (Google Gemini)
    gemini_llm: GeminiConfig
    
    # MongoDB configuration
    mongo: MongoConfig
    
    # SMTP configuration
    smtp: SMTPConfig
    
    # Server configuration
    server: ServerConfig
    
    # Application processing
    MAX_APPLICATION_LENGTH: int = 3000  # Characters
    
    # Conversation History Management
    # Maximum tokens for conversation messages (excluding system instructions).
    # Use .env (e.g. 25000) for long interviews; default 12000 avoids aggressive truncation that can make the model "forget" not to conclude.
    MAX_CONVERSATION_TOKENS: int = int(os.getenv("MAX_CONVERSATION_TOKENS", "12000"))
    # Maximum number of messages to keep in history. Default 50 so "do not conclude" context is not dropped early.
    MAX_CONVERSATION_MESSAGES: int = int(os.getenv("MAX_CONVERSATION_MESSAGES", "50"))
    # Minimum messages to always keep (even if over token limit)
    MIN_CONVERSATION_MESSAGES: int = int(os.getenv("MIN_CONVERSATION_MESSAGES", "6"))
    
    # Turn Detection
    # Enable ML-based multilingual turn detection (requires model download from HuggingFace).
    # If False or unavailable, falls back to VAD-based detection (recommended for production).
    # Default: False (VAD-first approach for reliability and determinism).
    ENABLE_ML_TURN_DETECTION: bool = False
    
    # Interview link access
    # If True: only logged-in students can open interview link (token must match their booking).
    # If False: anyone with the link (token) can open and attend the interview without logging in.
    REQUIRE_LOGIN_FOR_INTERVIEW: bool = True
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv(
        "LOG_FORMAT",
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    @classmethod
    def from_env(cls) -> "Config":
        """
        Create configuration from environment variables.
        
        Returns:
            Configured Config instance
            
        Raises:
            ValueError: If required environment variables are missing
        """
        # Validate required LiveKit variables
        livekit_api_key = os.getenv("LIVEKIT_API_KEY")
        livekit_api_secret = os.getenv("LIVEKIT_API_SECRET")
        livekit_url = os.getenv("LIVEKIT_URL")
        
        if not livekit_api_key:
            raise ValueError("LIVEKIT_API_KEY environment variable is required")
        if not livekit_api_secret:
            raise ValueError("LIVEKIT_API_SECRET environment variable is required")
        if not livekit_url:
            raise ValueError("LIVEKIT_URL environment variable is required")
        
        # Validate required OpenAI/Self-hosted API variables
        openai_api_key = os.getenv("OPENAI_API_KEY")
        openai_base_url = os.getenv("OPENAI_BASE_URL")
        tts_base_url = os.getenv("TTS_BASE_URL")
        stt_base_url = os.getenv("STT_BASE_URL")
        
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        if not openai_base_url:
            raise ValueError("OPENAI_BASE_URL environment variable is required")
        # OpenAI client sends to {base_url}/chat/completions; most proxies expect .../v1/chat/completions
        openai_base_url = openai_base_url.rstrip("/")
        if not openai_base_url.endswith("/v1"):
            openai_base_url = f"{openai_base_url}/v1"
        if not tts_base_url:
            raise ValueError("TTS_BASE_URL environment variable is required")
        if not stt_base_url:
            raise ValueError("STT_BASE_URL environment variable is required")
        
        # Validate Gemini (primary LLM)
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required (primary LLM)")
        
        # Validate MongoDB URI
        mongodb_uri = os.getenv("MONGODB_URI")
        if not mongodb_uri:
            raise ValueError("MONGODB_URI environment variable is required")
        
        # SMTP configuration (optional)
        smtp_port = os.getenv("SMTP_PORT", "587")
        smtp_secure = os.getenv("SMTP_SECURE", "false").lower() == "true" or smtp_port == "465"
        
        return cls(
            livekit=LiveKitConfig(
                api_key=livekit_api_key,
                api_secret=livekit_api_secret,
                url=livekit_url,
                agent_name=os.getenv("LIVEKIT_AGENT_NAME", "my-interviewer"),
            ),
            openai=OpenAIConfig(
                api_key=openai_api_key,
                llm_base_url=openai_base_url,
                tts_base_url=tts_base_url,
                stt_base_url=stt_base_url,
                llm_model=os.getenv("OPENAI_LLM_MODEL", "qwen2-5-7b-instruct"),
                tts_model=os.getenv("OPENAI_TTS_MODEL", "kokoro"),
                stt_model=os.getenv("OPENAI_STT_MODEL", "small.en"),
                tts_voice=os.getenv("OPENAI_TTS_VOICE", "af_bella"),
                # Enable/disable flags for self-hosted services
                stt_enabled=os.getenv("SELF_HOSTED_STT_ENABLED", "true").lower() == "true",
                llm_enabled=os.getenv("SELF_HOSTED_LLM_ENABLED", "true").lower() == "true",
                tts_enabled=os.getenv("SELF_HOSTED_TTS_ENABLED", "true").lower() == "true",
            ),
            silero_vad=SileroVADConfig(
                min_speech_duration=float(os.getenv("SILERO_MIN_SPEECH_DURATION", "0.3")),
                min_silence_duration=float(os.getenv("SILERO_MIN_SILENCE_DURATION", "4.0")),
                activation_threshold=float(os.getenv("SILERO_ACTIVATION_THRESHOLD", "0.6")),
            ),
            gemini_llm=GeminiConfig(
                api_key=gemini_api_key,
                model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            ),
            mongo=MongoConfig(
                uri=mongodb_uri,
                db_name=os.getenv("MONGODB_DB_NAME") or None,
            ),
            smtp=SMTPConfig(
                host=os.getenv("SMTP_HOST"),
                port=int(smtp_port),
                secure=smtp_secure,
                user=os.getenv("SMTP_USER"),
                password=os.getenv("SMTP_PASSWORD"),
                from_name=os.getenv("SMTP_FROM_NAME", "Sreedhar's CCE Team"),
                from_email=os.getenv("SMTP_FROM_EMAIL") or os.getenv("SMTP_USER"),
            ),
            server=ServerConfig(
                host=os.getenv("SERVER_HOST", "0.0.0.0"),
                port=int(os.getenv("SERVER_PORT", "8000")),
                frontend_url=os.getenv("NEXT_PUBLIC_APP_URL") or os.getenv("FRONTEND_URL", ""),
                public_frontend_url=(os.getenv("PUBLIC_FRONTEND_URL") or os.getenv("FRONTEND_PUBLIC_URL") or "").strip(),
            ),
            MAX_APPLICATION_LENGTH=int(os.getenv("MAX_APPLICATION_LENGTH", "3000")),
            ENABLE_ML_TURN_DETECTION=os.getenv("ENABLE_ML_TURN_DETECTION", "false").lower() == "true",
            REQUIRE_LOGIN_FOR_INTERVIEW=os.getenv("REQUIRE_LOGIN_FOR_INTERVIEW", "true").lower() == "true",
        )




def get_config() -> Config:
    """
    Get configuration from environment variables.
    
    Returns:
        Configuration instance
    """
    return Config.from_env()

