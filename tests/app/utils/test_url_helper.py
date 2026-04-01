import pytest
from unittest.mock import MagicMock, patch
from app.utils.url_helper import get_frontend_url

def test_get_frontend_url_from_origin():
    request = MagicMock()
    request.headers = {"Origin": "https://frontend.com"}
    
    url = get_frontend_url(request)
    assert url == "https://frontend.com"

def test_get_frontend_url_from_referer():
    request = MagicMock()
    request.headers = {"Referer": "https://frontend.com/page"}
    
    url = get_frontend_url(request)
    assert url == "https://frontend.com"

def test_get_frontend_url_fallback_config():
    with patch("app.utils.url_helper.config") as mock_config:
        mock_config.server.frontend_url = "https://config.com"
        url = get_frontend_url(None)
        assert url == "https://config.com"

def test_get_frontend_url_no_request_no_config():
    with patch("app.utils.url_helper.config") as mock_config:
        mock_config.server.frontend_url = None
        url = get_frontend_url(None)
        assert url == ""
