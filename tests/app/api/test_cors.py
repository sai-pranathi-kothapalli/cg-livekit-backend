import pytest
from app.api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_cors_allowed_origin():
    """Test that a request from an allowed origin receives the correct header."""
    origin = "http://localhost:3000"
    response = client.get("/health", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin

def test_cors_production_origin():
    """Test that the production origin from .env is allowed."""
    origin = "https://interviewfrontenddev.codegnan.ai"
    response = client.get("/health", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin

def test_cors_disallowed_origin():
    """Test that a request from a disallowed origin does not receive the header."""
    origin = "http://malicious-site.com"
    response = client.get("/health", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") is None

def test_cors_regex_allowed_origin():
    """Test that cloudflare tunnel origins are allowed via regex."""
    origin = "https://my-tunnel.trycloudflare.com"
    response = client.get("/health", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
