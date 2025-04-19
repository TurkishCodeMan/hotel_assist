"""
Ajanlar
------
Sistemin farklı görevleri yerine getiren ajan tanımları.
LangGraph kullanarak modüler ve akış halinde tasarlanmıştır.
"""

import json
import logging
import aiohttp
import os
from typing import Dict, Any, List, Optional

from mcp import StdioServerParameters, stdio_client
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from models.llm import GeminiJSONModel
from prompts.prompts import (
    UNDERSTANDING_SYSTEM_PROMPT,
    RESERVATION_SYSTEM_PROMPT,
    SUPPORT_SYSTEM_PROMPT,

)
from states.state import AgentGraphState
from utils.utils import create_tool_description, get_current_utc_datetime, check_for_content

# Logger ayarları
logger = logging.getLogger(__name__)

# Temel Ajan Sınıfı
class Agent:
    def __init__(self, state=AgentGraphState, model=None, server=None, model_endpoint=None, stop=None, guided_json=None, temperature=0.0, session=None):
        self.state = state
        self.temperature = temperature
        self.model = model
        self.server = server
        self.model_endpoint = model_endpoint
        self.stop = stop
        self.guided_json = guided_json
        self.session = session

    def update_state(self, key, value):
        self.state = {**self.state, key: value}

    def get_llm(self, json_model=True, tools=None):
        if self.server == 'gemini':
            return GeminiJSONModel(
                model=self.model,
                temperature=self.temperature,
                tools=tools,
                session=self.session
            )
        elif self.server is None:
            model = self.model if self.model else "gemini-2.0-flash"
            logger.warning(f"Server belirtilmemiş, varsayılan 'gemini' kullanılıyor. Model: {model}")
            return GeminiJSONModel(
                model=model,
                temperature=self.temperature,
                tools=tools
            )
        else:
            logger.error(f"Desteklenmeyen LLM sunucusu: {self.server}")
            return GeminiJSONModel(
                model="gemini-2.0-flash",
                temperature=self.temperature,
                tools=tools
            )

class UnderstandingAgent(Agent):
    async def invoke(self, research_question, conversation_state, prompt=UNDERSTANDING_SYSTEM_PROMPT, feedback=None):
        logger.info(f"UnderstandingAgent invoked with question: {research_question}...")
        feedback_value = feedback() if callable(feedback) else feedback
        feedback_value = check_for_content(feedback_value)
        prompt = UNDERSTANDING_SYSTEM_PROMPT.format(chat_history=feedback_value)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": research_question}
        ]
        llm = self.get_llm()
        ai_msg = await llm.invoke(messages)
        self.update_state("understanding_response", ai_msg.content)
        return self.state
    




class ReservationAgent(Agent):
    async def invoke(self, research_question, conversation_state, tools=None, prompt=RESERVATION_SYSTEM_PROMPT, feedback=None):
        logger.info(f"ReservationAgent invoked with question: {research_question}...")
        if tools:
            logger.debug(f"Tools: {[tool.name for tool in tools]}")
            
        feedback_value = feedback() if callable(feedback) else feedback
        feedback_value = check_for_content(feedback_value)
        
        prompt = RESERVATION_SYSTEM_PROMPT.format(
            reservations_result=conversation_state.get('reservations_result', []),
            add_reservation_result=conversation_state.get('add_reservation_result', []),
            update_reservation_result=conversation_state.get('update_reservation_result', []),
            delete_reservation_result=conversation_state.get('delete_reservation_result', []),
            chat_history=feedback_value,
            tools_description=create_tool_description(tools)
        )
        
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": research_question}
        ]
        try:
            llm = self.get_llm(tools=tools)
            ai_msg = await llm.invoke(messages)
            response = ai_msg.content if hasattr(ai_msg, 'content') else str(ai_msg)
            
            # Normal metin yanıtı tespiti yap
            is_regular_text_response = True
            for tool_result_marker in [
                "REZERVASYON KAYITLARI", 
                "REZERVASYON EKLEME SONUÇLARI", 
                "REZERVASYON GÜNCELLEME SONUÇLARI", 
                "REZERVASYON SİLME SONUÇLARI"
            ]:
                if tool_result_marker in response:
                    is_regular_text_response = False
                    break
                    
            # Normal metin yanıtlarını JSON formatında değil, doğrudan döndür
            if is_regular_text_response:
                logger.info("Sıradan metin yanıtı tespit edildi")
                # Normal metni doğrudan mesaj nesnesine koy, JSON formatlamadan
                message_object = {"role": "assistant", "content": response}
                self.state = {
                    **self.state,
                    "reservation_response": message_object,
                    "messages": self.state.get("messages", []) + [message_object]
                }
                return self.state
                
            # Araç yanıtları için JSON formatlamayı dene
            try:
                # Yanıt zaten JSON formatında mı kontrol et
                try:
                    # JSON olarak parse etmeyi dene
                    json_obj = json.loads(response)
                    # Başarılıysa ve bir dict ise, doğrudan kullan
                    if isinstance(json_obj, dict):
                        formatted_response = response  # Zaten JSON string
                    else:
                        # Liste gibi başka bir JSON tipiyse, response field'a çevir
                        formatted_response = json.dumps({"response": json_obj}, ensure_ascii=False)
                except json.JSONDecodeError:
                    # JSON parse edilemiyorsa, bir dict içine koy
                    formatted_response = json.dumps({"response": response}, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"JSON formatlarken hata: {str(e)}")
                # Herhangi bir hata durumunda, düz string kullan
                formatted_response = response
                
            # Sonuçları döndür
            message_object = {"role": "assistant", "content": formatted_response}
            self.state = {
                **self.state,
                "reservation_response": message_object,
                "messages": self.state.get("messages", []) + [message_object]
            }
            return self.state
        except Exception as e:
            error_msg = f"Rezervasyon işlemi hatası: {str(e)}"
            logger.error(error_msg)
            error_message = {"role": "assistant", "content": error_msg}  # JSON formatı yok
            self.state = {
                **self.state,
                "reservation_response": error_message,
                "messages": self.state.get("messages", []) + [error_message]
            }
            return self.state

class SupportAgent(Agent):
    async def invoke(self, research_question, conversation_state, prompt=SUPPORT_SYSTEM_PROMPT, feedback=None):
        logger.info(f"SupportAgent invoked with question: {research_question}...")
        feedback_value = feedback() if callable(feedback) else feedback
        feedback_value = check_for_content(feedback_value)
        prompt = SUPPORT_SYSTEM_PROMPT.format(chat_history=feedback_value)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": research_question}
        ]
        llm = self.get_llm()
        ai_msg = await llm.invoke(messages)
        message_object = {"role": "assistant", "content": ai_msg.content}
        self.update_state("support_response", message_object)
        if "messages" not in self.state:
            self.state["messages"] = []
        self.state["messages"].append(message_object)
        return self.state