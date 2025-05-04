"""
Groq API integration for text generation and tool usage.

This module provides a wrapper around Groq's generative AI models
with enhanced error handling and tool integration.
"""

from typing import Any, Dict, List, Union, Optional, Callable
from langchain_groq import ChatGroq
from dotenv import load_dotenv
import os
import json

from langchain_core.messages.human import HumanMessage
from langchain_core.tools import Tool as LangChainTool

from utils.logging_utils import get_logger
from utils.exceptions import ModelError, safe_execute
from models.base import BaseLLM, ModelRegistry

# Initialize environment variables
load_dotenv()

# Initialize logger
logger = get_logger("groq_model")

class Groq(BaseLLM):
    """
    Wrapper for Groq's generative AI models with tool integration.
    
    Handles model configuration, tool conversion, and response processing
    with structured error handling.
    """
    
    def __init__(
        self, 
        temperature: float = 0.7, 
        model_name: str = 'llama-3.3-70b-versatile', 
        tools: List = None, 
        session: Any = None
    ):
        """
        Initialize the Groq model wrapper.
        
        Args:
            temperature: Controls randomness in generation (0.0 to 1.0)
            model_name: Name of the Groq model to use
            tools: List of tool objects to make available to the model
            session: Session object for tool execution
        """
        self.model_name = model_name
        self.temperature = temperature
        self.tools = tools or []
        self.session = session
        
        # Validate API key
        if not os.environ.get('GROQ_API_KEY'):
            raise ModelError("GROQ_API_KEY environment variable not set")

    def _convert_mcp_tools_to_langchain(self) -> List[LangChainTool]:
        """
        Convert MCP tools to LangChain format for compatibility.
        
        Returns:
            List of LangChain tools
        """
        if not self.tools:
            return []

        langchain_tools = []
        
        for tool in self.tools:
            try:
                # Create tool function - generate a closure for each tool
                def make_tool_func(tool_name):
                    async def tool_func(**kwargs):
                        return await self._tool_executor(tool_name, kwargs)
                    return tool_func
                
                # Convert MCP tool to LangChain tool
                lc_tool = LangChainTool(
                    name=tool.name,
                    description=tool.description,
                    func=make_tool_func(tool.name),
                    args_schema=tool.inputSchema if hasattr(tool, 'inputSchema') else None
                )
                langchain_tools.append(lc_tool)
            except Exception as e:
                logger.warning(f"Failed to convert tool {tool.name}: {str(e)}")
        
        return langchain_tools

    async def _tool_executor(self, tool_name: str, kwargs: Dict) -> Any:
        """
        Execute MCP tool asynchronously.
        
        Args:
            tool_name: Name of the tool to execute
            kwargs: Arguments to pass to the tool
            
        Returns:
            Result from tool execution
            
        Raises:
            ValueError: If MCP session is not initialized
            ModelError: If tool execution fails
        """
        if not self.session:
            raise ValueError("MCP session not initialized")
        
        try:
            result = await self.session.call_tool(tool_name, arguments=kwargs)
            return result
        except Exception as e:
            raise ModelError(f"Failed to execute tool {tool_name}", {
                "original_error": str(e),
                "tool_name": tool_name,
                "arguments": kwargs
            })

    async def invoke(self, messages: List[Dict[str, str]]) -> Union[Any, HumanMessage]:
        """
        Generate content using the Groq model with potential tool usage.
        
        Args:
            messages: List of messages for the conversation context
            
        Returns:
            Generated response
            
        Raises:
            ModelError: If the model invocation fails
        """
        logger.info(f"Invoking Groq model, MCP session available: {bool(self.session)}")
        
        try:
            # Create Groq model
            groq_model = self._create_groq_model()
            
            # Handle MCP session and tools
            if self.session and self.tools:
                # Convert tools to LangChain format
                langchain_tools = self._convert_mcp_tools_to_langchain()
                
                # Bind converted tools to model
                if langchain_tools:
                    groq_with_tools = groq_model.bind_tools(tools=langchain_tools)
                    ai_msg = await groq_with_tools.ainvoke(messages)
                else:
                    # Tool conversion failed, continue without tools
                    ai_msg = await groq_model.ainvoke(messages)
                
                # Process tool calls if present
                if hasattr(ai_msg, 'tool_calls') and ai_msg.tool_calls:
                    await self._process_tool_calls(ai_msg.tool_calls)
                
                # Return response
                return HumanMessage(content=ai_msg.content)
                
            # Standard LangChain processing without MCP session
            else:
                if self.tools:
                    result = await groq_model.bind_tools(tools=self.tools).ainvoke(messages)
                else:
                    result = await groq_model.ainvoke(messages)
                return result
                
        except Exception as e:
            error_msg = "Failed to process Groq request"
            logger.error(f"{error_msg}: {str(e)}")
            return HumanMessage(content=f"İsteğinizi işlerken bir hata oluştu: {str(e)}")

    def _create_groq_model(self) -> ChatGroq:
        """
        Create a ChatGroq model instance with proper error handling.
        
        Returns:
            Initialized ChatGroq model
            
        Raises:
            ModelError: If model creation fails
        """
        try:
            return ChatGroq(
                api_key=os.environ.get('GROQ_API_KEY'),
                model_name=self.model_name,
                temperature=self.temperature
            )
        except Exception as e:
            raise ModelError(f"Failed to create Groq model {self.model_name}", {
                "original_error": str(e)
            })
            
    async def _process_tool_calls(self, tool_calls: List[Dict]) -> None:
        """
        Process tool calls from model response.
        
        Args:
            tool_calls: List of tool calls from the model
            
        Raises:
            ModelError: If tool execution fails
        """
        logger.info(f"Processing {len(tool_calls)} tool calls")
        
        for tool_call in tool_calls:
            try:
                name = tool_call.get('name')
                args = tool_call.get('args', {})
                
                if name and args:
                    logger.info(f"Executing MCP tool: {name}")
                    await self.session.call_tool(name, arguments=args)
            except Exception as e:
                logger.error(f"Failed to execute tool call {name}: {str(e)}")
                # Continue with other tool calls even if one fails

    async def handle_function_call(
        self, 
        function_call: Dict, 
        query: str, 
        tools: List
    ) -> Union[Dict, List, str, Any]:
        """
        Process a function call through MCP.
        
        Args:
            function_call: Function call details
            query: Original query string
            tools: Available tools list
            
        Returns:
            Result from tool execution
        """
        name = function_call.get('name', '')
        args = function_call.get('args', {})
        
        # Validate function call
        if not name:
            return {"error": "Function name not found"}

        available_tool_names = [tool.name for tool in tools]
        if name not in available_tool_names:
            return {"error": f"Invalid tool name: {name}"}

        if not args:
            return {"error": f"Tool name found ({name}) but parameters are missing"}

        logger.info(f"Executing tool: {name}, Parameters: {args}")

        try:
            result = await self.session.call_tool(name, arguments=args)
            return result
        except Exception as e:
            logger.error(f"Tool execution error ({name}): {str(e)}")
            return {"error": f"Tool execution error: {str(e)}"}


# Register the model with the registry
ModelRegistry.register("groq", Groq)