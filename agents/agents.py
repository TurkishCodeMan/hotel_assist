"""
Ajanlar
------
Sistemin farklı görevleri yerine getiren ajan tanımları.
LangGraph kullanarak modüler ve akış halinde tasarlanmıştır.
"""

from datetime import datetime
import json
import uuid
from typing import Dict, Any, List, Optional, Union

from models import create_model
from models.base import BaseLLM
from prompts.prompts import (
    MEMORY_ANALYSIS_PROMPT,
    RESERVATION_SYSTEM_PROMPT,
    SUPPORT_SYSTEM_PROMPT,
)
from states.state import AgentGraphState
from utils.utils import create_tool_description, check_for_content
from utils.logging_utils import get_logger
from utils.exceptions import ModelError, BaseAppException, safe_execute

# Logger ayarları
logger = get_logger("agents")

class AgentError(BaseAppException):
    """Ajan işlemleri sırasında oluşan hatalar için özel exception sınıfı."""
    pass

class VectorStoreError(BaseAppException):
    """Vector store işlemleriyle ilgili hatalar için özel exception sınıfı."""
    pass

# Temel Ajan Sınıfı
class Agent:
    def __init__(
        self, 
        state=AgentGraphState, 
        model=None, 
        server=None, 
        model_endpoint=None, 
        stop=None, 
        guided_json=None, 
        temperature=0.0, 
        session=None
    ):
        """
        Temel ajan sınıfı.

        Args:
            state: Ajan durumu
            model: Model adı
            server: Sunucu tipi ("gemini", "groq" gibi)
            model_endpoint: Model endpoint'i
            stop: Durdurma dizesi
            guided_json: JSON biçimlendirme rehberi
            temperature: Sıcaklık değeri
            session: Oturum nesnesi
        """
        self.state = state
        self.temperature = temperature
        self.model = model
        self.server = server
        self.model_endpoint = model_endpoint
        self.stop = stop
        self.guided_json = guided_json
        self.session = session

    def update_state(self, key: str, value: Any) -> None:
        """
        Durum nesnesini günceller.

        Args:
            key: Güncellenecek anahtarı
            value: Yeni değer
        """
        self.state = {**self.state, key: value}

    def get_llm(self, tools=None) -> BaseLLM:
        """
        LLM modelini oluşturur.
        
        Args:
            tools: LLM tarafından kullanılacak araçlar
            
        Returns:
            BaseLLM: LLM model nesnesi
            
        Raises:
            ModelError: Model oluşturma hatası durumunda
        """
        # Server belirtilmişse kullan, yoksa gemini varsayılan
        server_name = self.server if self.server else "gemini"
        logger.debug(f"Model sunucusu: {server_name}")
        
        try:
            # Model parametreleri oluştur
            model_params = self._prepare_model_params(server_name, tools)
            
            # Model oluştur ve döndür
            return create_model(server_name, **model_params)
            
        except Exception as e:
            # Hata durumunda Gemini'ye fallback yap
            logger.error(f"Model oluşturma hatası ({server_name}): {str(e)}")
            return self._create_fallback_model(tools)
    
    def _prepare_model_params(self, server_name: str, tools=None) -> Dict[str, Any]:
        """
        Model tipine göre uygun parametreleri hazırlar.
        
        Args:
            server_name: Model sunucu tipi
            tools: LLM araçları
            
        Returns:
            Hazırlanan parametre sözlüğü
        """
        # Temel parametreler
        params = {
            "temperature": self.temperature,
            "tools": tools,
            "session": self.session
        }
        
        # Model adı parametresini doğru anahtarla ekle
        if self.model:
            if server_name == "gemini":
                params["model"] = self.model
            else:
                params["model_name"] = self.model
        
        logger.debug(f"{server_name.capitalize()} parametreleri: {params}")
        return params
    
    def _create_fallback_model(self, tools=None) -> BaseLLM:
        """
        Hata durumunda kullanılacak fallback model oluşturur.
        
        Args:
            tools: LLM araçları
            
        Returns:
            BaseLLM: Oluşturulan fallback model
        """
        fallback_params = {
            "temperature": self.temperature,
            "tools": tools,
            "session": self.session
        }
        
        try:
            return create_model("gemini", **fallback_params)
        except Exception as e:
            # Son çare - temel hatayı ilet
            raise ModelError(f"Fallback model oluşturulamadı: {str(e)}")

class MemoryExtractionAgent(Agent):
    async def invoke(
        self, 
        research_question: Union[str, List[str]], 
        conversation_state: Dict[str, Any], 
        tools=None, 
        vector_store=None, 
        prompt=MEMORY_ANALYSIS_PROMPT, 
        feedback=None
    ) -> Dict[str, Any]:
        """
        Hafıza çıkarım ajanını çalıştırır.
        
        Args:
            research_question: Kullanıcı sorusu
            conversation_state: Konuşma durumu
            tools: Kullanılacak araçlar
            vector_store: Vektör depolama nesnesi
            prompt: Kullanılacak prompt
            feedback: Geri bildirim
            
        Returns:
            Güncellenmiş durum
        """
        try:
            # Araçları logla (DEBUG seviyesinde)
            if tools and logger.isEnabledFor(10):
                logger.debug(f"Tools: {[tool.name for tool in tools]}")
    
            # Yeni konuşma için boş mesaj listesi oluştur
            if 'messages' not in self.state:
                logger.debug("MemoryExtractionAgent: Yeni konuşma başlatılıyor")
                self.state['messages'] = []
            
            # Kullanıcı mesajını al
            user_message = research_question[-1] if isinstance(research_question, list) and research_question else research_question
            
            # Prompt ve mesaj oluştur
            messages = self._prepare_messages(user_message, conversation_state, prompt, tools)
            
            # LLM'i çağır ve yanıt al
            response_data = await self._get_llm_response(messages, tools, user_message, vector_store)
            
            # Yanıtı state'e ekle ve güncelle
            return self._update_state_with_response(response_data)
            
        except Exception as e:
            # Genel hata durumu
            error_msg = f"Hafıza çıkarım işlemi hatası: {str(e)}"
            logger.error(error_msg)
            return self._handle_error(error_msg)
    
    def _prepare_messages(
        self, 
        user_message: str, 
        conversation_state: Dict[str, Any], 
        prompt_template: str, 
        tools=None
    ) -> List[Dict[str, str]]:
        """
        LLM için mesaj formatını hazırlar.
        
        Args:
            user_message: Kullanıcı mesajı
            conversation_state: Konuşma durumu
            prompt_template: Kullanılacak prompt şablonu
            tools: Kullanılacak araçlar
            
        Returns:
            Hazırlanan mesaj listesi
        """
        # Prompt formatla
        formatted_prompt = prompt_template.format(
            tools_description=create_tool_description(tools),
            chat_history=conversation_state.get('messages', []),
            message=user_message
        )
        
        # Mesaj listesi oluştur
        return [
            {"role": "system", "content": formatted_prompt},
            {"role": "user", "content": str(user_message)}
        ]
    
    async def _get_llm_response(
        self, 
        messages: List[Dict[str, str]], 
        tools=None, 
        user_message: str = "", 
        vector_store=None
    ) -> Dict[str, Any]:
        """
        LLM'i çağırıp yanıt alır ve işler.
        
        Args:
            messages: Gönderilecek mesaj listesi
            tools: Kullanılacak araçlar
            user_message: Kullanıcı mesajı
            vector_store: Vektör depolama nesnesi
            
        Returns:
            İşlenmiş yanıt
        """
        # LLM modelini al
        llm = self.get_llm(tools=tools)
        
        # Yanıt al
        ai_msg = await llm.invoke(messages)
        response_text = ai_msg.content if hasattr(ai_msg, 'content') else str(ai_msg)
        logger.debug(f"MemoryExtractionAgent yanıtı alındı: {response_text[:50]}...")
        
        try:
            # Yanıtı işle
            response = self._parse_response(response_text)
            
            # Hafıza kaydı gerekli mi kontrol et
            if self._should_store_memory(response) and vector_store:
                response = await self._process_memory_storage(response, user_message, vector_store)
                
            return response
                
        except json.JSONDecodeError:
            logger.debug("Yanıt JSON formatında değil, ham metin kullanılıyor")
            return {"is_important": False, "formatted_memory": None, "raw_text": response_text}
        except Exception as e:
            logger.error(f"Yanıt işleme hatası: {str(e)}")
            return {"is_important": False, "formatted_memory": None, "error": str(e), "raw_text": response_text}
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        Yanıt metnini JSON'a dönüştürür.
        
        Args:
            response_text: İşlenecek yanıt metni
            
        Returns:
            İşlenmiş yanıt
            
        Raises:
            json.JSONDecodeError: JSON ayrıştırma hatası olursa
        """
        if isinstance(response_text, str):
            return json.loads(response_text)
        return response_text
    
    def _should_store_memory(self, response: Dict[str, Any]) -> bool:
        """
        Yanıtın hafıza kaydı gerektirip gerektirmediğini kontrol eder.
        
        Args:
            response: Kontrol edilecek yanıt
            
        Returns:
            Hafıza kaydı gerekli ise True
        """
        return (
            isinstance(response, dict) and 
            "is_important" in response and 
            response.get("is_important") and 
            response.get("formatted_memory")
        )
    
    async def _process_memory_storage(
        self, 
        response: Dict[str, Any], 
        user_message: str, 
        vector_store
    ) -> Dict[str, Any]:
        """
        Hafıza kaydını işler ve vector store'a kaydeder.
        
        Args:
            response: İşlenecek yanıt
            user_message: Kullanıcı mesajı
            vector_store: Vektör depolama nesnesi
            
        Returns:
            Güncellenmiş yanıt
        """
        try:
            logger.info(f"Önemli hafıza bulundu: '{response.get('formatted_memory')}'")
            
            # Cihaz kimliğini al
            device_id = None  # None bırakarak VectorStore'un otomatik oluşturmasına izin ver
            
            # Benzer hafıza var mı kontrol et
            similar = safe_execute(
                vector_store.find_similar_memory,
                error_cls=VectorStoreError,
                args=(
                    response.get("formatted_memory"), 
                    None # device_id için None (otomatik oluşturulacak)
                ),
                kwargs={},
                reraise=False 
            )
            
            if similar:
                logger.debug(f"Benzer hafıza zaten var: '{response.get('formatted_memory')}'")
                # Cihaz kimliği kontrolü
                if hasattr(similar, 'device_id') and similar.device_id:
                    logger.debug(f"Cihaz: {similar.device_id[:8]}... ID: {similar.id}")
                else:
                    logger.debug(f"Cihaz kimliği bulunamadı, ID: {similar.id if hasattr(similar, 'id') else 'Bilinmiyor'}")
            else:
                # Yeni hafıza kaydet
                logger.debug(f"Yeni hafıza kaydediliyor: '{response.get('formatted_memory')}'")
                
                # Vector store'a kaydet
                safe_execute(
                    vector_store.store_memory,
                    error_cls=VectorStoreError,
                    args=(
                        response.get("formatted_memory"), 
                        {
                            "id": str(uuid.uuid4()),
                            "timestamp": datetime.now().isoformat(),
                            "source": "conversation",
                            "user_message": user_message,
                        }
                    ),
                    kwargs={
                        "device_id": None
                    },
                    reraise=False
                )
                
                # Cihaz bilgisini yanıta ekle
                if hasattr(vector_store, 'device_id') and vector_store.device_id:
                    response["device_info"] = f"Cihaz: {vector_store.device_id[:8]}..."
            
            return response
            
        except Exception as e:
            logger.error(f"Vector store işlemi hatası: {str(e)}")
            # Hataya rağmen orijinal yanıtı döndür
            return response
    
    def _update_state_with_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Yanıtı state'e ekler ve günceller.
        
        Args:
            response: Eklenecek yanıt
            
        Returns:
            Güncellenmiş state
        """
        # JSON nesnesini string formatına dönüştür
        if isinstance(response, dict):
            message_content = json.dumps(response, ensure_ascii=False)
        else:
            message_content = str(response)
            
        # Mesaj nesnesi oluştur
        message_object = {"role": "assistant", "content": message_content}
        
        # State'i güncelle ve döndür
        self.state = {
            **self.state,
            "memory_extraction_response": message_object,
            "messages": self.state.get("messages", []) + [message_object]
        }
        
        return self.state
    
    def _handle_error(self, error_message: str) -> Dict[str, Any]:
        """
        Hata durumunu işler ve uygun state güncellemesi yapar.
        
        Args:
            error_message: Hata mesajı
            
        Returns:
            Hata içeren güncellenmiş state
        """
        error_object = {"role": "assistant", "content": error_message}
        self.state = {
            **self.state,
            "memory_extraction_response": error_object,
            "messages": self.state.get("messages", []) + [error_object]
        }
        return self.state

class ReservationAgent(Agent):
    async def invoke(
        self, 
        research_question: str, 
        conversation_state: Dict[str, Any], 
        tools=None, 
        prompt=RESERVATION_SYSTEM_PROMPT, 
        feedback=None
    ) -> Dict[str, Any]:
        """
        Rezervasyon ajanını çalıştırır.
        
        Args:
            research_question: Kullanıcı sorusu
            conversation_state: Konuşma durumu
            tools: Kullanılacak araçlar
            prompt: Kullanılacak prompt
            feedback: Geri bildirim
            
        Returns:
            Güncellenmiş durum
        """
        logger.debug("ReservationAgent soru alındı")
        
        try:
            # Araçları logla (debug seviyesinde)
            if tools and logger.isEnabledFor(10):
                logger.debug(f"Tools: {[tool.name for tool in tools]}")
            
            # Geri bildirim değerini hazırla    
            feedback_value = feedback() if callable(feedback) else feedback
            feedback_value = check_for_content(feedback_value)
            
            # Prompt formatla
            formatted_prompt = self._prepare_reservation_prompt(conversation_state, tools, prompt)
            
            # Mesajları hazırla
            messages = [
                {"role": "system", "content": formatted_prompt},
                {"role": "user", "content": research_question}
            ]
            
            # LLM yanıtını al
            response = await self._get_reservation_response(messages, tools)
            
            # Yanıt tipini belirle ve uygun şekilde işle
            return self._process_reservation_response(response)
            
        except Exception as e:
            # Genel hata durumu
            error_msg = f"Rezervasyon işlemi hatası: {str(e)}"
            logger.error(error_msg)
            return self._handle_reservation_error(error_msg)
    
    def _prepare_reservation_prompt(
        self, 
        conversation_state: Dict[str, Any], 
        tools=None, 
        prompt_template: str = RESERVATION_SYSTEM_PROMPT
    ) -> str:
        """
        Rezervasyon promptunu hazırlar.
        
        Args:
            conversation_state: Konuşma durumu
            tools: Kullanılacak araçlar
            prompt_template: Prompt şablonu
            
        Returns:
            Formatlanmış prompt
        """
        return prompt_template.format(
            reservations_result=conversation_state.get('reservations_result', []),
            add_reservation_result=conversation_state.get('add_reservation_result', []),
            update_reservation_result=conversation_state.get('update_reservation_result', []),
            delete_reservation_result=conversation_state.get('delete_reservation_result', []),
            chat_history=conversation_state.get('messages'),
            tools_description=create_tool_description(tools)
        )
    
    async def _get_reservation_response(
        self, 
        messages: List[Dict[str, str]], 
        tools=None
    ) -> str:
        """
        LLM yanıtını alır.
        
        Args:
            messages: Gönderilecek mesajlar
            tools: Kullanılacak araçlar
            
        Returns:
            LLM yanıtı
        """
        llm = self.get_llm(tools=tools)
        ai_msg = await llm.invoke(messages)
        return ai_msg.content if hasattr(ai_msg, 'content') else str(ai_msg)
    
    def _process_reservation_response(self, response: str) -> Dict[str, Any]:
        """
        Rezervasyon yanıtını işler.
        
        Args:
            response: İşlenecek yanıt
            
        Returns:
            İşlenmiş yanıt içeren state
        """
        # Normal metin yanıtı mı kontrol et
        if self._is_regular_text_response(response):
            logger.debug("Sıradan metin yanıtı tespit edildi")
            message_object = {"role": "assistant", "content": response}
        else:
            # Araç yanıtı, JSON formatlamayı dene
            formatted_response = self._format_tool_response(response)
            message_object = {"role": "assistant", "content": formatted_response}
            
        # State'i güncelle ve döndür
        self.state = {
            **self.state,
            "reservation_response": message_object,
            "messages": self.state.get("messages", []) + [message_object]
        }
        return self.state
    
    def _is_regular_text_response(self, response: str) -> bool:
        """
        Yanıtın normal metin mi yoksa araç yanıtı mı olduğunu kontrol eder.
        
        Args:
            response: Kontrol edilecek yanıt
            
        Returns:
            Normal metin yanıtı ise True
        """
        tool_markers = [
            "REZERVASYON KAYITLARI", 
            "REZERVASYON EKLEME SONUÇLARI", 
            "REZERVASYON GÜNCELLEME SONUÇLARI", 
            "REZERVASYON SİLME SONUÇLARI"
        ]
        
        return not any(marker in response for marker in tool_markers)
    
    def _format_tool_response(self, response: str) -> str:
        """
        Araç yanıtını JSON olarak formatlar.
        
        Args:
            response: Formatlanacak yanıt
            
        Returns:
            Formatlanmış yanıt
        """
        try:
            # JSON olarak parse etmeyi dene
            json_obj = json.loads(response)
            
            # Başarılıysa ve bir dict ise, doğrudan kullan
            if isinstance(json_obj, dict):
                return response  # Zaten JSON string
            
            # Liste gibi başka bir JSON tipiyse, response field'a çevir
            return json.dumps({"response": json_obj}, ensure_ascii=False)
            
        except json.JSONDecodeError:
            # JSON parse edilemiyorsa, bir dict içine koy
            return json.dumps({"response": response}, ensure_ascii=False)
        except Exception as e:
            logger.debug(f"JSON formatlarken hata: {str(e)}")
            # Herhangi bir hata durumunda, düz string kullan
            return response
    
    def _handle_reservation_error(self, error_message: str) -> Dict[str, Any]:
        """
        Rezervasyon hatası durumunu işler.
        
        Args:
            error_message: Hata mesajı
            
        Returns:
            Hata içeren güncellenmiş state
        """
        error_object = {"role": "assistant", "content": error_message}
        self.state = {
            **self.state,
            "reservation_response": error_object,
            "messages": self.state.get("messages", []) + [error_object]
        }
        return self.state


