"""
Base model interface for language model implementations.

This module defines the base interface that all language model implementations
should follow to ensure consistent behavior across the application.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Union, Optional

from langchain_core.messages.human import HumanMessage


class BaseLLM(ABC):
    """
    Abstract base class for language model implementations.
    
    Defines the standard interface that all model implementations must follow.
    """
    
    @abstractmethod
    async def invoke(self, messages: List[Dict[str, str]]) -> Union[Any, HumanMessage]:
        """
        Generate content using the language model.
        
        Args:
            messages: List of messages for the conversation context
            
        Returns:
            Generated response
        """
        pass
    
    @abstractmethod
    async def handle_function_call(self, function_call: Any, query: str, tools: List) -> Any:
        """
        Execute a function call using available tools.
        
        Args:
            function_call: Function call details from model
            query: Original query string
            tools: Available tools list
            
        Returns:
            Result from tool execution
        """
        pass


class ModelRegistry:
    """
    Registry for available language model implementations.
    
    Provides a central registry of model implementations that can be used
    by the application.
    """
    
    _models = {}
    
    @classmethod
    def register(cls, name: str, model_class: type):
        """
        Register a model implementation.
        
        Args:
            name: Name to register the model under
            model_class: The model class to register
        """
        cls._models[name] = model_class
    
    @classmethod
    def get_model(cls, name: str, **kwargs) -> Optional[BaseLLM]:
        """
        Get a model implementation by name.
        
        Args:
            name: Name of the model implementation
            **kwargs: Configuration parameters for the model
            
        Returns:
            Instance of the requested model or None if not found
        """
        model_class = cls._models.get(name)
        if model_class:
            return model_class(**kwargs)
        return None
    
    @classmethod
    def list_models(cls) -> List[str]:
        """
        List all registered model implementations.
        
        Returns:
            List of model names
        """
        return list(cls._models.keys()) 