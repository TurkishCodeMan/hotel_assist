"""
Centralized logging utilities for the project.

This module provides standardized logging functions and configurations
to ensure consistent logging across the application.
"""

import logging
import os
import sys
from typing import Optional, Union, Dict, Any

# Default log format
DEFAULT_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DEFAULT_LEVEL = logging.INFO

class LoggerManager:
    """
    Manages logger instances across the application.
    
    Provides methods to create and retrieve loggers with consistent formatting.
    """
    
    _instance = None
    _loggers = {}
    
    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super(LoggerManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize logging configuration."""
        self._loggers = {}
        self._default_formatter = logging.Formatter(DEFAULT_FORMAT)
        
        # Create root handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(self._default_formatter)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(console_handler)
        
        # Set log level from environment or use default
        log_level = os.environ.get("LOG_LEVEL", DEFAULT_LEVEL)
        if isinstance(log_level, str):
            log_level = getattr(logging, log_level.upper(), DEFAULT_LEVEL)
        root_logger.setLevel(log_level)
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        Get or create a logger with the specified name.
        
        Args:
            name: The name for the logger
            
        Returns:
            Logger instance
        """
        if name not in self._loggers:
            logger = logging.getLogger(name)
            self._loggers[name] = logger
        return self._loggers[name]


# Global LoggerManager instance
_manager = LoggerManager()

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    
    Args:
        name: The name for the logger
        
    Returns:
        Logger instance
    """
    return _manager.get_logger(name)


