"""
Custom Exception Classes

Enterprise-grade exception handling with proper error codes
and messages for different error scenarios.
"""

from typing import Optional


class ApplicationError(Exception):
    """Base exception for all application errors"""
    
    def __init__(self, message: str, error_code: str = "GENERIC_ERROR", status_code: int = 500):
        """
        Initialize application error.
        
        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            status_code: HTTP status code
        """
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(self.message)


class ConfigurationError(ApplicationError):
    """Configuration-related errors"""
    
    def __init__(self, message: str):
        super().__init__(message, "CONFIGURATION_ERROR", 500)


class ValidationError(ApplicationError):
    """Input validation errors"""
    
    def __init__(self, message: str, field: Optional[str] = None):
        """
        Initialize validation error.
        
        Args:
            message: Error message
            field: Optional field name that failed validation
        """
        self.field = field
        error_code = f"VALIDATION_ERROR_{field.upper()}" if field else "VALIDATION_ERROR"
        super().__init__(message, error_code, 400)


class ServiceError(ApplicationError):
    """Service layer errors"""
    
    def __init__(self, message: str, service_name: str = "UNKNOWN"):
        """
        Initialize service error.
        
        Args:
            message: Error message
            service_name: Name of the service that failed
        """
        self.service_name = service_name
        error_code = f"SERVICE_ERROR_{service_name.upper()}"
        super().__init__(message, error_code, 503)


class RepositoryError(ApplicationError):
    """Data repository errors"""
    
    def __init__(self, message: str):
        super().__init__(message, "REPOSITORY_ERROR", 500)


class AgentError(ApplicationError):
    """LiveKit agent errors"""
    
    def __init__(self, message: str, agent_name: str = "UNKNOWN"):
        """
        Initialize agent error.
        
        Args:
            message: Error message
            agent_name: Name of the agent that failed
        """
        self.agent_name = agent_name
        error_code = f"AGENT_ERROR_{agent_name.upper()}"
        super().__init__(message, error_code, 503)

