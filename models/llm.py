"""
Google Gemini API integration for text generation and tool usage.

This module provides a wrapper around Google's Generative AI models
with enhanced error handling and tool integration.
"""

import json
import os
from typing import List, Dict, Any, Union, Optional, Callable

from langchain_core.messages.human import HumanMessage
import google.generativeai as genai
from google.generativeai import types

from utils.logging_utils import get_logger
from utils.exceptions import ModelError, safe_execute
from models.base import BaseLLM, ModelRegistry

# Initialize logger
logger = get_logger("gemini_model")

class GeminiJSONModel(BaseLLM):
    """
    Wrapper for Google's Gemini model with JSON output and tool integration.
    
    Handles model configuration, prompt formatting, and response parsing
    with structured error handling.
    """
    
    def __init__(
        self, 
        temperature: float = 0,
        model: str = 'gemini-1.5-flash',
        tools: List = None,
        session: Any = None
    ):
        """
        Initialize the Gemini model wrapper.
        
        Args:
            temperature: Controls randomness in generation (0.0 to 1.0)
            model: Name of the Gemini model to use
            tools: List of tool objects to make available to the model
            session: Session object for tool execution
        """
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ModelError("GEMINI_API_KEY environment variable not set")
            
        genai.configure(api_key=self.api_key)

        self.generation_config = {
            "temperature": temperature,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 2048,
        }

        self.model = self._initialize_model(model)
        self.tools = tools or []
        self.temperature = temperature
        self.session = session
        
    def _initialize_model(self, model_name: str) -> Any:
        """
        Initialize the Gemini model with proper error handling.
        
        Args:
            model_name: Name of the model to initialize
            
        Returns:
            Initialized model object
        """
        try:
            return genai.GenerativeModel(
                model_name=model_name,
                generation_config=self.generation_config,
            )
        except Exception as e:
            raise ModelError(f"Failed to initialize Gemini model {model_name}", {
                "original_error": str(e)
            })

    def _clean_schema(self, schema: Dict) -> Dict:
        """
        Clean JSON schema to be compatible with Gemini's function calling format.
        
        Args:
            schema: JSON schema to clean
            
        Returns:
            Cleaned schema
        """
        if not schema:
            return {}

        allowed_keys = {"type", "properties", "required", "description", "enum", "items"}
        cleaned = {}
        
        for key, value in schema.items():
            if key not in allowed_keys:
                continue
                
            if key == "properties" and isinstance(value, dict):
                cleaned[key] = {k: self._clean_schema(v) for k, v in value.items()}
            else:
                cleaned[key] = value
                
        return cleaned
        
    def _prepare_function_declarations(self) -> List[Dict]:
        """
        Prepare function declarations for tools.
        
        Returns:
            List of function declarations
        """
        function_declarations = []
        
        for tool in self.tools:
            try:
                cleaned_schema = self._clean_schema(tool.inputSchema)
                function_declarations.append({
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": cleaned_schema
                })
            except Exception as e:
                logger.warning(f"Failed to prepare function declaration for tool {tool.name}: {e}")
                
        return function_declarations

    async def invoke(self, messages: List[Dict[str, str]]) -> HumanMessage:
        """
        Generate content using the Gemini model with potential tool usage.
        
        Args:
            messages: List of messages for the conversation context
            
        Returns:
            Generated response as a HumanMessage object
            
        Raises:
            ModelError: If the model invocation fails
        """
        try:
            system_msg = ""
            user_msg = ""

            # Extract system and user messages
            if messages and len(messages) > 0 and "content" in messages[0]:
                system_msg = messages[0]["content"]
            if messages and len(messages) > 1 and "content" in messages[1]:
                user_msg = messages[1]["content"]

            logger.info(f"Generating response for: \"{user_msg[:100]}...\"")

            # Create prompt with system instructions
            tools_prompt = system_msg
            tools_prompt += f"\n\nİsteğim: {user_msg}\n"

            # Prepare function declarations for tools
            function_declarations = self._prepare_function_declarations()
            
            # Generate content
            response = await self._generate_content(tools_prompt, function_declarations)
            
            # Process response
            return await self._process_response(response, user_msg)
                
        except Exception as e:
            error_msg = f"Failed to generate content"
            logger.error(f"{error_msg}: {str(e)}")
            return HumanMessage(content=f"İsteğinizi işlerken bir hata oluştu: {str(e)}")

    async def _generate_content(self, prompt: str, function_declarations: List[Dict]) -> Any:
        """
        Generate content using the model with proper error handling.
        
        Args:
            prompt: The text prompt
            function_declarations: Tool function declarations
            
        Returns:
            Response from the model
            
        Raises:
            ModelError: If content generation fails
        """
        try:
            if function_declarations:
                return await self.model.generate_content_async(
                    [{"role": "user", "parts": [prompt]}],
                    tools=[types.Tool(function_declarations=function_declarations)]
                )
            else:
                return await self.model.generate_content_async(
                    [{"role": "user", "parts": [prompt]}]
                )
        except Exception as e:
            raise ModelError("Failed to generate content", {
                "original_error": str(e)
            })

    async def _process_response(self, response: Any, user_msg: str) -> HumanMessage:
        """
        Process model response, handling both text content and function calls.
        
        Args:
            response: The model response object
            user_msg: The original user message
            
        Returns:
            Processed response as a HumanMessage
        """
        if not response or not hasattr(response, 'candidates') or not response.candidates:
            return HumanMessage(content="Yanıt alınamadı, lütfen tekrar deneyin.")
            
        candidate = response.candidates[0]
        if not hasattr(candidate, 'content') or not hasattr(candidate.content, 'parts'):
            return HumanMessage(content="Yanıt formatı beklendiği gibi değil.")

        parts = candidate.content.parts
        
        # Extract text content and function call
        text_content = ""
        function_call_part = None
        
        for part in parts:
            # Collect text content
            if hasattr(part, 'text') and part.text:
                text_content += part.text
                
            # Find function call
            if hasattr(part, 'function_call') and part.function_call:
                function_call_part = part.function_call
        
        # Process function call if present
        if function_call_part:
            logger.info(f"Function call detected: {getattr(function_call_part, 'name', 'Unnamed')}")
            return await self._handle_function_response(function_call_part, text_content, user_msg)
        
        # Return text content
        logger.info("Returning text response")
        return HumanMessage(content=text_content)
            
    async def _handle_function_response(
        self, 
        function_call: Any, 
        text_content: str, 
        user_msg: str
    ) -> HumanMessage:
        """
        Handle function call in the model response.
        
        Args:
            function_call: Function call details from model
            text_content: Text content from the response
            user_msg: Original user message
            
        Returns:
            Processed response with function results
        """
        try:
            # Execute function call
            tool_result = await self.handle_function_call(function_call, user_msg, self.tools)
            
            if not tool_result:
                return HumanMessage(content=f"{text_content}\n\nAraç sonucu boş döndü.")
            
            # Format tool result
            tool_result_str = self._format_tool_result(tool_result)
            
            # Generate a summary of the tool result
            return await self._summarize_tool_result(text_content, tool_result_str)
                
        except Exception as e:
            logger.error(f"Function handling error: {str(e)}")
            # Return text content with error message if available
            if text_content:
                return HumanMessage(content=f"{text_content}\n\n(İşlem sırasında bir hata oluştu: {str(e)})")
            return HumanMessage(content=f"İşleminiz sırasında bir hata oluştu: {str(e)}")
    
    def _format_tool_result(self, result: Any) -> str:
        """
        Format tool result as a string.
        
        Args:
            result: Tool execution result
            
        Returns:
            Formatted result as string
        """
        try:
            if hasattr(result, 'text'):
                return result.text
            elif isinstance(result, (dict, list)):
                return json.dumps(result, indent=2, ensure_ascii=False)
            else:
                return str(result)
        except Exception as e:
            logger.warning(f"Error formatting tool result: {e}")
            return str(result)
    
    async def _summarize_tool_result(self, text_content: str, tool_result_str: str) -> HumanMessage:
        """
        Generate a summary combining text content and tool results.
        
        Args:
            text_content: Text content from the model
            tool_result_str: Formatted tool result
            
        Returns:
            Summarized response
        """
        try:
            # Create prompt for summarization based on content
            if text_content:
                combined_prompt = f"""Merhaba, kullanıcıya şu bilgilendirme mesajı verildi:

                {text_content}

                Ardından, istediği işlem için şu sonuç alındı:

                {tool_result_str}

                Lütfen bu iki mesajı birleştirerek tek bir açıklayıcı yanıt oluştur. 
                Özellikle araç sonucunu kullanıcı dostu formatta özetle."""
            else:
                combined_prompt = f"""Aşağıdaki sonucu kolay anlaşılır şekilde, Türkçe olarak özetle.
                Eğer bir rezervasyon listesi ise, kaç rezervasyon olduğunu, müşteri isimlerini, tarihlerini ve oda tiplerini belirt.

                {tool_result_str}"""

            summary_response = await self.model.generate_content_async(combined_prompt)
            return HumanMessage(content=summary_response.text)
        except Exception as e:
            logger.error(f"Summarization error: {e}")
            # Return raw content in case of error
            if text_content:
                return HumanMessage(content=f"{text_content}\n\n{tool_result_str}")
            return HumanMessage(content=tool_result_str)

    async def handle_function_call(
        self, 
        function_call: Any, 
        query: str, 
        tools: List
    ) -> Union[Dict, List, str, Any]:
        """
        Execute a function call using the available tools.
        
        Args:
            function_call: Function call details from model
            query: Original query text
            tools: Available tools list
            
        Returns:
            Result from tool execution
        """
        name = getattr(function_call, 'name', '')
        args_dict = self._extract_args(function_call)
        
        # Validate function call
        if not name:
            return {"error": "Fonksiyon adı bulunamadı. Lütfen sorgunuzu daha net bir şekilde belirtin."}

        available_tool_names = [tool.name for tool in tools]
        if name not in available_tool_names:
            return {"error": f"Geçerli bir araç adı değil: {name}. Mevcut araçlar: {available_tool_names}"}

        if not args_dict:
            return {"error": f"Araç adı bulundu ({name}) fakat parametreler eksik."}

        logger.info(f"Executing tool: {name}, Parameters: {args_dict}")

        try:
            # Execute tool
            if not self.session:
                return {"error": "Session is not available for tool execution"}
                
            result = await self.session.call_tool(name, arguments=args_dict)
            return result
        except Exception as e:
            logger.error(f"Tool execution error ({name}): {str(e)}")
            return {"error": f"Araç çağrısı hatası: {str(e)}"}
    
    def _extract_args(self, function_call: Any) -> Dict[str, Any]:
        """
        Extract arguments from a function call.
        
        Args:
            function_call: Function call object
            
        Returns:
            Dictionary of arguments
        """
        args_dict = {}
        
        if not hasattr(function_call, 'args') or not function_call.args:
            return args_dict
            
        raw_args = function_call.args
        
        # Handle dict type
        if isinstance(raw_args, dict):
            return raw_args
            
        # Handle fields attribute
        if hasattr(raw_args, "fields"):
            for k, v in raw_args.fields.items():
                if hasattr(v, 'string_value'):
                    args_dict[k] = v.string_value
                elif hasattr(v, 'number_value'):
                    args_dict[k] = v.number_value
                elif hasattr(v, 'bool_value'):
                    args_dict[k] = v.bool_value
                else:
                    args_dict[k] = str(v)
            return args_dict
            
        # Handle MapComposite type
        if hasattr(raw_args, '__class__') and 'MapComposite' in str(raw_args.__class__):
            logger.debug("Processing MapComposite arguments")
            try:
                # Try to convert MapComposite to dict
                if hasattr(raw_args, 'items') and callable(raw_args.items):
                    return {k: v for k, v in raw_args.items()}
                elif hasattr(raw_args, '__dict__'):
                    return raw_args.__dict__
                    
                # Parse as string if other approaches fail
                str_rep = str(raw_args)
                for line in str_rep.split(','):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip().strip('"\'{}')
                        value = value.strip().strip('"\'{}')
                        args_dict[key] = value
                return args_dict
            except Exception as e:
                logger.warning(f"MapComposite processing error: {str(e)}")
                return {"error": "Failed to process MapComposite arguments"}
        
        # Last resort: try to parse as string
        try:
            str_args = str(raw_args)
            # Check if JSON-like string
            if str_args.strip().startswith('{') and str_args.strip().endswith('}'):
                return json.loads(str_args)
            else:
                return {"raw_input": str_args}
        except Exception as e:
            logger.warning(f"Failed to parse arguments: {e}")
            return {"raw_input": str(raw_args)}


# Register the model with the registry
ModelRegistry.register("gemini", GeminiJSONModel)