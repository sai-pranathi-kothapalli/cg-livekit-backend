import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import httpx

@pytest.mark.asyncio
async def test_execute_code_success(client):
    # Mock httpx.AsyncClient.post
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "stdout": "Hello World\n",
        "stderr": "",
        "executionTime": 10,
        "memory": 100
    }
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post, \
         patch("app.api.compiler.os.getenv") as mock_getenv:
        
        mock_getenv.side_effect = lambda k, d=None: "test-token" if k == "ONECOMPILER_ACCESS_TOKEN" else d
        mock_post.return_value = mock_response
        
        response = client.post("/api/compiler/execute", json={
            "language": "python",
            "code": "print('Hello World')",
            "stdin": ""
        })
        
        assert response.status_code == 200
        assert response.json()["stdout"] == "Hello World\n"
        assert response.json()["executionTime"] == 10

@pytest.mark.asyncio
async def test_execute_code_no_token(client):
    with patch("app.api.compiler.os.getenv") as mock_getenv:
        mock_getenv.return_value = None
        
        response = client.post("/api/compiler/execute", json={
            "language": "python",
            "code": "print('Hello World')"
        })
        
        assert response.status_code == 500
        assert "not configured" in response.json()["detail"]

@pytest.mark.asyncio
async def test_execute_code_api_error(client):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal error"
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post, \
         patch("app.api.compiler.os.getenv") as mock_getenv:
        
        mock_getenv.side_effect = lambda k, d=None: "test-token" if k == "ONECOMPILER_ACCESS_TOKEN" else d
        mock_post.return_value = mock_response
        
        response = client.post("/api/compiler/execute", json={
            "language": "python",
            "code": "print('Hello World')"
        })
        
        assert response.status_code == 502
        assert "Compiler service error" in response.json()["detail"]
