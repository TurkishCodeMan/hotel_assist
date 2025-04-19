import json
import os
import logging
import traceback
from typing import List, Dict, Any, Union
from langchain_core.messages.human import HumanMessage
import google.generativeai as genai
from google.generativeai import types
from pydantic import BaseModel
import re
import asyncio

# Logger tanımlama
logger = logging.getLogger(__name__)

class ResponseFormat(BaseModel):
    response: str
    action_type: str
    tool_action: str
    customer_name: str
    check_in_date: str
    check_out_date: str
    room_type: str
    adult: str
    children: str
    reservation_id: str

class GeminiJSONModel:
    def __init__(self, temperature=0, model='gemini-1.5-flash', tools=None, session=None):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        genai.configure(api_key=self.api_key)

        generation_config = {
            "temperature": 0.1,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 2048,
        }

        self.model = genai.GenerativeModel(
            model_name=model,
            generation_config=generation_config,
        )

        self.tools = tools or []
        self.temperature = temperature
        self.session = session

    def _clean_schema(self, schema: Dict) -> Dict:
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

    async def invoke(self, messages: List[Dict[str, str]]) -> HumanMessage:
        try:
            system_msg = ""
            user_msg = ""

            if messages and len(messages) > 0 and "content" in messages[0]:
                system_msg = messages[0]["content"]
            if messages and len(messages) > 1 and "content" in messages[1]:
                user_msg = messages[1]["content"]

            logger.info(f"Sorgu: \"{user_msg}\"")

            # Sistem mesajını doğrudan kullan
            tools_prompt = system_msg
            tools_prompt += f"\n\nİsteğim: {user_msg}\n"

            function_declarations = []
            for tool in self.tools:
                cleaned_schema = self._clean_schema(tool.inputSchema)
                function_declarations.append({
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": cleaned_schema
                })

            response = await self.model.generate_content_async(
                [{"role": "user", "parts": [tools_prompt]}],
                tools=[types.Tool(function_declarations=function_declarations)]
            )
            logger.debug(f"Model yanıtı alındı")

            # Metin ve fonksiyon çağrısı içerebilecek içeriği incele
            if response and hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    parts = candidate.content.parts
                    
                    # İki olası içerik tipi: metin ve fonksiyon çağrısı
                    text_content = ""
                    function_call_part = None
                    
                    # Önce tüm parçaları incele
                    for part in parts:
                        # Metin içeriği topla
                        if hasattr(part, 'text') and part.text:
                            text_content += part.text
                            
                        # Fonksiyon çağrısını bul
                        if hasattr(part, 'function_call') and part.function_call:
                            function_call_part = part.function_call
                    
                    # Eğer bir fonksiyon çağrısı bulunduysa, öncelikli olarak işle
                    if function_call_part:
                        logger.info(f"Fonksiyon çağrısı bulundu: {getattr(function_call_part, 'name', 'İsimsiz')}")
                        
                        try:
                            tool_result = await self.handle_function_call(function_call_part, user_msg, self.tools)
                            
                            if not tool_result:
                                return HumanMessage(content=f"{text_content}\n\nAraç sonucu boş döndü.")
                            
                            # Araç sonucunu işle
                            try:
                                if hasattr(tool_result, 'text'):
                                    tool_result_str = tool_result.text
                                elif isinstance(tool_result, (dict, list)):
                                    tool_result_str = json.dumps(tool_result, indent=2, ensure_ascii=False)
                                else:
                                    tool_result_str = str(tool_result)
                                
                                # Bilgilendirme mesajı + araç sonucu kombinasyonu
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
                                logger.error(f"Özetleme sırasında hata oluştu: {str(e)}\n{traceback.format_exc()}")
                                # Hata durumunda ham içeriği döndür
                                if text_content:
                                    return HumanMessage(content=f"{text_content}\n\n{tool_result_str}")
                                return HumanMessage(content=tool_result_str)
                        
                        except Exception as e:
                            logger.error(f"Fonksiyon çağrısı işleme hatası: {str(e)}\n{traceback.format_exc()}")
                            # Fonksiyon çağrısı hatalı ancak metin içeriği varsa, onu kullan
                            if text_content:
                                return HumanMessage(content=f"{text_content}\n\n(İşlem sırasında bir hata oluştu: {str(e)})")
                            return HumanMessage(content=f"İşleminiz sırasında bir hata oluştu: {str(e)}")
                    
                    # Sadece metin içeriği varsa
                    if text_content:
                        logger.info("Sadece metin içeriği bulundu, normal yanıt döndürülüyor")
                        return HumanMessage(content=text_content)
                
                # Content yapısını çözümleyemedik, ham text içeriğini dene
                if hasattr(response, 'text'):
                    logger.info("Response.text üzerinden metin döndürülüyor")
                    return HumanMessage(content=response.text)
            
            # Yanıtı hiçbir şekilde çözümleyemedik
            logger.warning("Yanıt yapısı beklendiği gibi değil, boş yanıt döndürülüyor")
            return HumanMessage(content="Yanıtınızı alamadım, lütfen tekrar dener misiniz?")

        except Exception as e:
            error_msg = f"Sorgu işleme hatası: {str(e)}"
            logger.error(f"{error_msg}\n{traceback.format_exc()}")
            return HumanMessage(content=f"İsteğinizi işlerken bir hata oluştu: {str(e)}")

    async def handle_function_call(self, function_call, query: str, tools: List) -> Union[Dict, List, str, Any]:
        name = getattr(function_call, 'name', '')
        args_dict = {}

        if hasattr(function_call, 'args') and function_call.args:
            raw_args = function_call.args
            if isinstance(raw_args, dict):
                args_dict = raw_args
            elif hasattr(raw_args, "fields"):
                for k, v in raw_args.fields.items():
                    if hasattr(v, 'string_value'):
                        args_dict[k] = v.string_value
                    elif hasattr(v, 'number_value'):
                        args_dict[k] = v.number_value
                    elif hasattr(v, 'bool_value'):
                        args_dict[k] = v.bool_value
                    else:
                        args_dict[k] = str(v)
            # MapComposite tipini işle
            elif hasattr(raw_args, '__class__') and 'MapComposite' in str(raw_args.__class__):
                logger.info("MapComposite argümanları işleniyor")
                try:
                    # MapComposite nesnesini dict'e dönüştürmeyi dene
                    if hasattr(raw_args, 'items') and callable(raw_args.items):
                        args_dict = {k: v for k, v in raw_args.items()}
                    elif hasattr(raw_args, '__dict__'):
                        args_dict = raw_args.__dict__
                    else:
                        # Eğer bu yaklaşımlar başarısız olursa, stringi parse et
                        str_rep = str(raw_args)
                        # Basit anahtar-değer analizi
                        for line in str_rep.split(','):
                            if ':' in line:
                                key, value = line.split(':', 1)
                                key = key.strip().strip('"\'{}')
                                value = value.strip().strip('"\'{}')
                                args_dict[key] = value
                except Exception as e:
                    logger.warning(f"MapComposite işleme hatası: {str(e)}")
                    args_dict = {"error": "MapComposite argümanları işlenemedi"}
            else:
                try:
                    # Son çare olarak string olarak parse etmeyi dene
                    str_args = str(raw_args)
                    logger.debug(f"String argümanlar: {str_args}")
                    # JSON-benzeri string mi kontrol et
                    if str_args.strip().startswith('{') and str_args.strip().endswith('}'):
                        args_dict = json.loads(str_args)
                    else:
                        args_dict = {"raw_input": str_args}
                except Exception as e:
                    logger.warning(f"Args JSON parse edilemedi: {e}")
                    args_dict = {"raw_input": str(raw_args)}

        # Eğer fonksiyon adı veya parametreler bulunamazsa, hata mesajı döndür
        if not name:
            return json.dumps({
                "error": "Fonksiyon adı bulunamadı. Lütfen sorgunuzu daha net bir şekilde belirtin."
            })

        available_tool_names = [tool.name for tool in tools]
        if name not in available_tool_names:
            return json.dumps({
                "error": f"Geçerli bir araç adı değil: {name}. Mevcut araçlar: {available_tool_names}"
            })

        if not args_dict:
            return json.dumps({
                "error": f"Araç adı bulundu ({name}) fakat parametreler eksik."
            })

        logger.info(f"🚀 Araç çağrılıyor: {name}, Parametreler: {args_dict}")

        try:
            result = await self.session.call_tool(name, arguments=args_dict)
            # TextContent veya başka nesne türleri için doğrudan nesneyi döndür
            # İşleme fonksiyonun çağrıldığı yerde yapılacak
            return result
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"🔴 MCP araç çağrısı hatası ({name}): {str(e)}\nTraceback:\n{tb}")
            return json.dumps({"error": f"Araç çağrısı hatası: {str(e)}", "traceback": tb})