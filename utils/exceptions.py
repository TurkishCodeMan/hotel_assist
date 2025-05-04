"""
Standardized exception handling for the project.

This module provides consistent exception classes and error handling utilities.
"""

from typing import Dict, Any, Optional, Callable, Type
import traceback
import sys

from utils.logging_utils import get_logger

logger = get_logger("exceptions")

class BaseAppException(Exception):
    """Base exception class for application-specific exceptions."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Initialize the exception.
        
        Args:
            message: Human-readable error message
            details: Additional error context and details
        """
        self.message = message
        self.details = details or {}
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert exception to a dictionary representation.
        
        Returns:
            Dictionary with error details
        """
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details
        }
    
    def log(self, include_traceback: bool = True):
        """
        Log this exception with appropriate level and details.
        
        Args:
            include_traceback: Whether to include the traceback in the log
        """
        exc_info = sys.exc_info() if include_traceback else None
        logger.error(
            f"{self.__class__.__name__}: {self.message}", 
            exc_info=exc_info,
            extra={"details": self.details}
        )


class ModelError(BaseAppException):
    """Exception raised for errors in LLM model operations."""
    pass


class APIError(BaseAppException):
    """Exception raised for API-related errors."""
    pass


class ConfigError(BaseAppException):
    """Exception raised for configuration errors."""
    pass


class DataError(BaseAppException):
    """Exception raised for data handling errors."""
    pass


def safe_execute(func: Callable, args=None, kwargs=None, 
                 error_message: str = None, 
                 error_cls: Type[BaseAppException] = BaseAppException, 
                 log_error: bool = True, 
                 reraise: bool = True, 
                 **extra_details) -> Any:
    """
    Execute a function safely, catching and handling exceptions.
    
    Args:
        func: Function to execute.
        args: Positional arguments for the function (optional).
        kwargs: Keyword arguments for the function (optional).
        error_message: Custom message for the raised exception (optional).
        error_cls: Specific exception class to raise (optional).
        log_error: Whether to log the captured exception (default: True).
        reraise: Whether to re-raise the captured exception (default: True).
        extra_details: Additional details to include in the exception context.
        
    Returns:
        Result of the function execution, or None if an exception occurred and reraise=False.
        
    Raises:
        error_cls: If the function raises an exception and reraise=True.
    """
    args = args or ()
    kwargs = kwargs or {}
    
    try:
        return func(*args, **kwargs)
    except Exception as e:
        msg = error_message or f"Error executing {getattr(func, '__name__', 'unknown function')}: {str(e)}"
        
        details = {
            "original_error": str(e),
            "original_type": e.__class__.__name__,
            "traceback": traceback.format_exc(),
            **extra_details
        }
        
        exception = error_cls(msg, details)
        
        if log_error:
            exception.log(include_traceback=False) # Traceback already in details
        
        if reraise:
            raise exception
        else:
            return None 