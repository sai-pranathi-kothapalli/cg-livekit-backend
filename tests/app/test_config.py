import pytest
import os
from unittest.mock import patch
from app.config import Config, get_config

def test_config_missing_vars():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError) as excinfo:
            Config.from_env()
        assert "LIVEKIT_API_KEY" in str(excinfo.value)

def test_config_success():
    mock_env = {
        "LIVEKIT_API_KEY": "lk_key",
        "LIVEKIT_API_SECRET": "lk_secret",
        "LIVEKIT_URL": "http://lk.com",
        "OPENAI_API_KEY": "oa_key",
        "OPENAI_BASE_URL": "http://oa.com/v1",
        "TTS_BASE_URL": "http://tts.com",
        "STT_BASE_URL": "http://stt.com",
        "GEMINI_API_KEY": "gem_key",
        "SUPABASE_URL": "http://sb.com",
        "SUPABASE_SERVICE_KEY": "sb_key"
    }
    with patch.dict(os.environ, mock_env, clear=True):
        config = Config.from_env()
        assert config.livekit.api_key == "lk_key"
        assert config.openai.api_key == "oa_key"
        assert config.gemini_llm.api_key == "gem_key"
        assert config.supabase.url == "http://sb.com"

def test_get_config():
    with patch('app.config.Config.from_env') as mock_from_env:
        get_config()
        mock_from_env.assert_called_once()
