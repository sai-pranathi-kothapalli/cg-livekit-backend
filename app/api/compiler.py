"""
Code Compiler API Endpoint

Proxies code execution requests to OneCompiler API.
"""

import os
import httpx
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.config import get_config
from app.utils.logger import get_logger

logger = get_logger(__name__)
config = get_config()

router = APIRouter(tags=["Compiler"])


class CodeExecutionRequest(BaseModel):
    language: str
    code: str
    stdin: Optional[str] = None


class CodeExecutionResponse(BaseModel):
    stdout: str
    stderr: str
    executionTime: Optional[int] = None
    memory: Optional[int] = None
    error: Optional[str] = None


@router.post("/execute", response_model=CodeExecutionResponse)
async def execute_code(request: CodeExecutionRequest):
    """
    Execute code using OneCompiler API.
    
    Supports: Python, Java, C, C++, SQL, and other languages supported by OneCompiler.
    """
    try:
        # Get compiler credentials from environment
        compiler_api_url = os.getenv("ONECOMPILER_API_URL", "https://onecompiler.com/api/v1/run")
        compiler_access_token = os.getenv("ONECOMPILER_ACCESS_TOKEN")
        
        if not compiler_access_token:
            logger.error("[Compiler] ONECOMPILER_ACCESS_TOKEN not configured")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Compiler service not configured"
            )
        
        # Map language codes to OneCompiler language identifiers
        language_map = {
            "python": "python",
            "java": "java",
            "c": "c",
            "cpp": "cpp",
            "c++": "cpp",
            "sql": "mysql",  # OneCompiler uses specific SQL dialects (mysql, postgresql, etc.)
        }
        
        # Normalize language input
        normalized_lang = request.language.lower().strip()
        compiler_language = language_map.get(normalized_lang, normalized_lang)
        
        compiler_language = language_map.get(request.language.lower(), request.language.lower())
        
        # Prepare request body for OneCompiler API
        # OneCompiler expects: language, files (array with name and content), stdin
        payload = {
            "language": compiler_language,
            "files": [
                {
                    "name": f"main.{_get_file_extension(compiler_language)}",
                    "content": request.code
                }
            ],
            "stdin": request.stdin or ""
        }
        
        logger.info(f"[Compiler] Executing {compiler_language} code ({len(request.code)} chars)")
        
        # Make request to OneCompiler API
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                compiler_api_url,
                json=payload,
                headers={
                    "X-API-Key": compiler_access_token,
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"[Compiler] OneCompiler API error: {response.status_code} - {error_text}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Compiler service error: {error_text[:200]}"
                )
            
            result = response.json()
            
            # Extract results from OneCompiler response
            stdout = result.get("stdout", "")
            stderr = result.get("stderr", "")
            execution_time = result.get("executionTime")
            memory = result.get("memory")
            
            logger.info(f"[Compiler] Execution completed: {len(stdout)} chars output, {execution_time}ms")
            
            return CodeExecutionResponse(
                stdout=stdout,
                stderr=stderr,
                executionTime=execution_time,
                memory=memory,
                error=stderr if stderr else None
            )
            
    except httpx.TimeoutException:
        logger.error("[Compiler] Request timeout")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Code execution timeout"
        )
    except httpx.RequestError as e:
        logger.error(f"[Compiler] Request error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to connect to compiler service: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Compiler] Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


def _get_file_extension(language: str) -> str:
    """Get file extension for a given language."""
    extensions = {
        "python": "py",
        "java": "java",
        "c": "c",
        "cpp": "cpp",
        "mysql": "sql",
        "sql": "sql",
    }
    return extensions.get(language.lower(), "txt")
