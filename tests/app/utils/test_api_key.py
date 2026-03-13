import pytest
import hashlib
import secrets
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from app.utils.api_key import hash_api_key, generate_api_key, get_api_key

def test_hash_api_key():
    key = "test-key"
    expected_hash = hashlib.sha256(key.encode()).hexdigest()
    assert hash_api_key(key) == expected_hash

def test_generate_api_key():
    key = generate_api_key()
    assert len(key) == 64  # 32 bytes hex
    assert isinstance(key, str)

@pytest.mark.asyncio
async def test_get_api_key_success():
    key = "valid-key"
    hashed = hash_api_key(key)
    
    with patch("app.utils.api_key.get_config") as mock_get_config:
        mock_config = MagicMock()
        mock_config.api_key.key_hash = hashed
        mock_get_config.return_value = mock_config
        
        result = await get_api_key(key)
        assert result == key

@pytest.mark.asyncio
async def test_get_api_key_missing():
    with pytest.raises(HTTPException) as excinfo:
        await get_api_key(None)
    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "Missing API Key"

@pytest.mark.asyncio
async def test_get_api_key_invalid():
    key = "invalid-key"
    hashed = hash_api_key("other-key")
    
    with patch("app.utils.api_key.get_config") as mock_get_config:
        mock_config = MagicMock()
        mock_config.api_key.key_hash = hashed
        mock_get_config.return_value = mock_config
        
        with pytest.raises(HTTPException) as excinfo:
            await get_api_key(key)
        assert excinfo.value.status_code == 403
        assert excinfo.value.detail == "Invalid API Key"

@pytest.mark.asyncio
async def test_get_api_key_misconfigured():
    with patch("app.utils.api_key.get_config") as mock_get_config:
        mock_config = MagicMock()
        mock_config.api_key.key_hash = None
        mock_get_config.return_value = mock_config
        
        with pytest.raises(HTTPException) as excinfo:
            await get_api_key("some-key")
        assert excinfo.value.status_code == 500
        assert "misconfiguration" in excinfo.value.detail
