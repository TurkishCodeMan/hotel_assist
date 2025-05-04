# Models and Error Handling

## Overview

This documentation provides details about the refactored model architecture and error handling system. The new implementation follows Python PEP standards, prioritizes clean code, and ensures consistent behavior across different model integrations.

## Architecture

### Model Structure

The model system consists of:

1. **Base Interface** (`BaseLLM`): Abstract base class that defines the common interface for all model implementations
2. **Model Registry**: Central registry for model implementations to enable dynamic selection
3. **Model Implementations**: Concrete implementations for different LLM providers:
   - `GeminiJSONModel`: Google's Gemini API
   - `Groq`: Groq's LLM API

### Error Handling System

The error handling system includes:

1. **Centralized Logging**: Consistent logging across the application
2. **Standard Exception Classes**: Hierarchy of custom exceptions
3. **Safe Execution Utilities**: Helper functions for error handling

## Using Models

### Creating a Model

You can create a model using the factory function:

```python
from models import create_model

# Create a Gemini model
gemini_model = create_model(
    model_name="gemini",
    temperature=0.2,
    model="gemini-2.0-flash"
)

# Create a Groq model
groq_model = create_model(
    model_name="groq",
    temperature=0.7,
    model_name="llama-3.3-70b-versatile"
)
```

### Using a Model

All models implement the standard interface:

```python
async def generate_response():
    # Prepare messages
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me about Python."}
    ]
    
    # Generate response
    response = await model.invoke(messages)
    
    return response.content
```

### Working with Tools

Models support tool integrations:

```python
from mcp import ClientSession

# Initialize model with tools and session
model = create_model(
    model_name="gemini",
    tools=available_tools,
    session=mcp_session
)

# The model will handle tool calls automatically
response = await model.invoke(messages)
```

## Error Handling

### Using Exceptions

The application provides custom exceptions for different error types:

```python
from utils.exceptions import ModelError, APIError, ConfigError, DataError

# Raise a specific error
raise ModelError("Failed to generate content", {
    "model": "gemini",
    "additional_info": "API key missing"
})
```

### Safe Execution

The `safe_execute` utility handles errors consistently:

```python
from utils.exceptions import safe_execute, ModelError

def risky_function():
    # Function that might fail
    result = api.call()
    return result

# Execute safely
result = safe_execute(
    risky_function,
    error_message="API call failed",
    exception_type=ModelError,
    additional_detail="user_id: 123"
)
```

### Logging

Use the standardized logging utilities:

```python
from utils.logging_utils import get_logger, log_error, log_info

# Get a logger
logger = get_logger("my_module")

# Log messages
logger.info("Operation started")
logger.error("Operation failed", exc_info=True)

# Or use convenience functions
log_info("my_module", "Operation completed")
log_error("my_module", "Error occurred", exc_info=True)
```

## Implementation Details

### BaseLLM Interface

```python
class BaseLLM(ABC):
    @abstractmethod
    async def invoke(self, messages: List[Dict[str, str]]) -> Union[Any, HumanMessage]:
        """Generate content using the language model."""
        pass
    
    @abstractmethod
    async def handle_function_call(self, function_call: Any, query: str, tools: List) -> Any:
        """Execute a function call using available tools."""
        pass
```

### Model Registry

```python
class ModelRegistry:
    _models = {}
    
    @classmethod
    def register(cls, name: str, model_class: type):
        cls._models[name] = model_class
    
    @classmethod
    def get_model(cls, name: str, **kwargs) -> Optional[BaseLLM]:
        model_class = cls._models.get(name)
        if model_class:
            return model_class(**kwargs)
        return None
```

### Exception Hierarchy

```python
class BaseAppException(Exception):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details
        }

class ModelError(BaseAppException):
    """Exception raised for errors in LLM model operations."""
    pass
```

## Best Practices

1. **Always use the base interface**: Code against `BaseLLM` rather than specific implementations
2. **Handle exceptions consistently**: Use custom exception classes
3. **Use the logging utilities**: For consistent log formatting
4. **Prefer async/await**: All model operations are asynchronous
5. **Use the model factory**: Instead of direct instantiation 