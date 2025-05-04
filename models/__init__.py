"""
LLM models package for text generation and tool integration.

This package provides standardized interfaces and implementations
for working with various language models.
"""

from typing import Optional, Dict, Any
import logging

from models.base import BaseLLM, ModelRegistry
from models.llm import GeminiJSONModel
from models.groq import Groq

# Logger
logger = logging.getLogger("models")

# Re-export for convenience
__all__ = [
    'BaseLLM', 
    'ModelRegistry',
    'GeminiJSONModel',
    'Groq'
]

# Create a factory function for easy model creation
def create_model(model_type: str, **kwargs) -> Optional[BaseLLM]:
    """
    Create a model instance by type.
    
    Args:
        model_type: Type of model to create (e.g., "gemini", "groq")
        **kwargs: Configuration parameters for the model
        
    Returns:
        Instantiated model
        
    Raises:
        ValueError: If the model type is not registered
    """
    # Sorun yaratabilecek parametreleri temizle
    sanitized_kwargs = sanitize_model_params(model_type, kwargs)
    
    # ModelRegistry'den modeli al
    try:
        model = ModelRegistry.get_model(model_type, **sanitized_kwargs)
        if not model:
            available_models = ModelRegistry.list_models()
            raise ValueError(f"Model '{model_type}' not found. Available models: {available_models}")
        return model
    except TypeError as e:
        logger.error(f"Model oluşturma parametre hatası: {e}")
        # Parametre hatası varsa daha temiz bir şekilde dene
        if "got multiple values for argument" in str(e):
            logger.warning(f"Parametre çakışması, temizleme deneniyor")
            # Daha agresif temizleme
            minimal_kwargs = {
                "temperature": kwargs.get("temperature", 0.0),
                "tools": kwargs.get("tools", None),
                "session": kwargs.get("session", None)
            }
            return ModelRegistry.get_model(model_type, **minimal_kwargs)
        raise
    except Exception as e:
        logger.error(f"Model oluşturma hatası: {e}")
        raise

def sanitize_model_params(model_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Model tipine göre parametreleri temizle ve düzenle.
    
    Args:
        model_type: Model tipi (gemini, groq, vs.)
        params: Model parametreleri
    
    Returns:
        Temizlenmiş parametre sözlüğü
    """
    # Kopyalayarak orijinal sözlüğü değiştirmeden işlem yap
    clean_params = params.copy()
    
    # model_name parametresi çakışmaları önle
    if 'model_name' in clean_params and model_type != 'groq':
        logger.warning(f"model_name parametresi '{model_type}' ile çakışabilir, kaldırılıyor")
        clean_params.pop('model_name')
    
    # Gemini modelinde özel düzenlemeler
    if model_type == 'gemini':
        # model_name parametresi varsa kaldır
        if 'model_name' in clean_params:
            clean_params.pop('model_name')
        
        # model parametresi yoksa ve model_name varsa, model_name'i model'e aktar
        if 'model' not in clean_params and 'model_name' in params:
            clean_params['model'] = params['model_name']
    
    # Groq modelinde özel düzenlemeler
    elif model_type == 'groq':
        # model parametresi varsa ve model_name yoksa, model_name'e aktar
        if 'model' in clean_params and 'model_name' not in clean_params:
            clean_params['model_name'] = clean_params.pop('model')
    
    logger.debug(f"Temizlenmiş parametreler ({model_type}): {clean_params}")
    return clean_params
