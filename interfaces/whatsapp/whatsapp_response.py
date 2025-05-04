import logging
import os
import traceback
from io import BytesIO
from typing import Dict
import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from dotenv import load_dotenv
import httpx
import json
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from langchain_core.messages import HumanMessage

# MCP entegrasyonu için gerekli modüller
from mcp import StdioServerParameters, ClientSession
from mcp.client.stdio import stdio_client

# Uygulama modülleri
from agent_graph.graph import create_graph, compile_workflow

load_dotenv()
logger = logging.getLogger(__name__)

# Router for WhatsApp response
whatsapp_router = APIRouter()

# WhatsApp API credentials
WHATSAPP_TOKEN ="EAAmYmKdWEsMBOxbnOZCZBNXRXpS4ZCLLdaZBIZAD2w7cCgKfo4kIYq3QEfIw5Hnl5FhSsq3f272wOI6mBVxj6oF1GeguM1jc27rKWjDf4RjDSAhZCdg1j8zw3LzmgfuhWedCj8B2HXgJ9zzOxQpxNnO4nWVxfyu5sNumSsbZArAJdIMJf6eGmbcs2N43QBW9ZC5JAZBtDZBVnIpW13qE7pvIW6RmVr9zPSvGLGbLkZD"
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
MCP_SHEET_PATH = os.getenv("MCP_SHEET_PATH", "/Users/huseyin/Documents/deep-learning/wp_agent/mcp_servers/google-sheets-mcp/sheet.py")

# MCP ayarları
SERVER = "gemini"
MODEL = "gemini-2.0-flash"
MODEL_ENDPOINT = None
ITERATIONS = 40

# Son işlenen mesajın ID'sini izlemek için
last_processed_message_id = None

# Test endpoint - Basit JSON yanıtı döner
@whatsapp_router.get("/foo")
async def test_endpoint():
    """Test amaçlı basit bir endpoint."""
    return JSONResponse(content={
        "status": "success",
        "message": "Test endpoint çalışıyor!",
        "data": {
            "server": SERVER,
            "model": MODEL,
            "whatsapp_enabled": bool(WHATSAPP_PHONE_NUMBER_ID),
            "timestamp": asyncio.get_event_loop().time()
        }
    })

# MCP oturumunu bağlam yöneticisi olarak kullan
@asynccontextmanager
async def managed_mcp_connection(mcp_path):
    """MCP bağlantı yöneticisi - Streamlit uygulamasındaki gibi"""
    connection_id = int(asyncio.get_event_loop().time() * 1000)
    logger.info(f"MCP bağlantısı başlatılıyor (ID: {connection_id})")
    
    stack = AsyncExitStack()
    session = None
    tools = []
    workflow = None
    
    try:
        # MCP path kontrolü
        if not os.path.exists(mcp_path):
            logger.error(f"MCP dosyası bulunamadı: {mcp_path}")
            yield None, [], None, stack
            return
            
        command = "python"
        server_params = StdioServerParameters(command=command, args=[mcp_path])
        
        # Asenkron kaynak yönetimi için stack kullanımı
        await stack.__aenter__()
        
        # MCP istemci akışını oluştur
        client_stream = stdio_client(server_params)
        stdio, write = await stack.enter_async_context(client_stream)
        
        # ClientSession oluştur ve başlat
        session = ClientSession(stdio, write)
        await stack.enter_async_context(session)
        
        await session.initialize()
        logger.info(f"MCP oturumu başlatıldı (ID: {connection_id})")
        
        # Kullanılabilir araçları al
        try:
            tools_response = await session.list_tools()
            tools = tools_response.tools
            logger.info(f"MCP araçları yüklendi: {len(tools)} araç bulundu")
        except Exception as e:
            logger.error(f"MCP araçlarını alırken hata: {e}")
            yield None, [], None, stack
            return
        
        # Graf ve iş akışını oluştur
        try:
            graph = create_graph(server=SERVER, model=MODEL, model_endpoint=MODEL_ENDPOINT, 
                           tools=tools, session=session)
            workflow = compile_workflow(graph)
            logger.info(f"İş akışı başarıyla oluşturuldu (ID: {connection_id})")
        except Exception as e:
            logger.error(f"Graph oluşturma hatası: {e}")
            yield None, [], None, stack
            return
        
        # Context manager değerlerini döndür
        yield session, tools, workflow, stack
        
    except Exception as e:
        # Bağlantı başarısız olduğunda loglama yap
        logger.exception(f"MCP bağlantı hatası (ID: {connection_id}): {e}")
        yield None, [], None, stack
        
    finally:
        # Context manager çıkışında kaynakları temizle
        try:
            logger.info(f"MCP oturumu kapatılıyor (ID: {connection_id})")
            await stack.__aexit__(None, None, None)
            logger.info(f"MCP oturumu başarıyla kapatıldı (ID: {connection_id})")
        except Exception as e:
            logger.error(f"MCP oturumunu kapatırken hata (ID: {connection_id}): {e}")

@whatsapp_router.api_route("/whatsapp_response", methods=["GET", "POST"])
async def whatsapp_handler(request: Request) -> Response:
    """Handles incoming messages and status updates from the WhatsApp Cloud API."""
    global last_processed_message_id

    if request.method == "GET":
        params = request.query_params
        if params.get("hub.verify_token") == os.getenv("WHATSAPP_VERIFY_TOKEN"):
            return Response(content=params.get("hub.challenge"), status_code=200)
        return Response(content="Verification token mismatch", status_code=403)
    
    try:
        # İstek gövdesini incele
        body = await request.body()
        if not body or len(body) <= 2:  # Boş istek veya {} gibi
            logger.warning("Boş webhook isteği alındı, atlama yapılıyor")
            return Response(content="Empty request", status_code=200)
            
        data = await request.json()
        
        # Meta API'nin statüleri izleme isteği gibi bazı istekleri filtrele
        if "object" in data and data["object"] == "whatsapp_business_account" and "entry" in data:
            if not data["entry"] or len(data["entry"]) == 0 or "changes" not in data["entry"][0]:
                logger.info("Boş entry veya changes içermeyen istek, atlama yapılıyor")
                return Response(content="No changes", status_code=200)
        else:
            logger.warning("Beklenmeyen istek formatı")
            return Response(content="Unexpected request format", status_code=200)
                
        change_value = data["entry"][0]["changes"][0]["value"]
        
        if "messages" in change_value:
            message = change_value["messages"][0]
            
            # Aynı mesajı tekrar işlemeyi önlemek için mesaj ID'sini kontrol et
            message_id = message.get("id")
            if message_id == last_processed_message_id:
                logger.info(f"Mesaj zaten işlendi, atlama yapılıyor: {message_id}")
                return Response(content="Message already processed", status_code=200)
            
            # Yeni mesaj ID'sini kaydet
            last_processed_message_id = message_id
            
            from_number = message["from"]
            session_id = from_number

            logger.info(f"Mesaj alındı: Kimden={from_number}, ID={message_id}")
            
            # Mesaj türünü kontrol et
            if message.get("type") != "text":
                logger.warning(f"Desteklenmeyen mesaj türü: {message.get('type', 'bilinmiyor')}")
                await send_response(from_number, "Sadece metin mesajları destekleniyor", "text")
                return Response(content="Unsupported message type", status_code=200)
            
            # Metin mesajını al
            try:
                content = message["text"]["body"]
                logger.info(f"Alınan mesaj içeriği: {content}")
            except KeyError as e:
                logger.error(f"Mesaj içeriği alınamıyor: {e}")
                return Response(content="Message content not found", status_code=400)

            # MCP oturumunu başlat ve iş akışını oluştur
            async with managed_mcp_connection(MCP_SHEET_PATH) as (session, tools, workflow, resource_stack):
                if not session or not workflow:
                    logger.error("MCP oturumu başlatılamadı")
                    return Response(content="Failed to start MCP session", status_code=500)
                
                # İş akışını çalıştırmak için giriş verilerini hazırla
                dict_inputs = {
                    "research_question": [content],
                    "session_id": session_id,
                    "from_number": from_number,
                    "platform": "whatsapp"
                }
                
                try:
                    # İş akışını çalıştır
                    logger.info("İş akışı çalıştırılıyor")
                    last_event = None
                    try:
                        async for event in workflow.astream(dict_inputs, {"recursion_limit": ITERATIONS}):
                            last_event = event
                    except Exception as e:
                        logger.error(f"İş akışı akışı sırasında hata: {e}")
                        return Response(content=f"Workflow stream error: {str(e)}", status_code=500)
                    
                    if last_event and "end" in last_event:
                        end_state = last_event["end"]
                        
                        # Sadece reservation_response'u al ve yanıt olarak gönder
                        response_message = ""
                        if "reservation_response" in end_state:
                            logger.info("reservation_response alınıyor")
                            res = end_state["reservation_response"]
                            if isinstance(res, list) and res:
                                res = res[-1]  # Son yanıtı al
                                
                            # Yanıt formatını kontrol et ve çıkart
                            if hasattr(res, "content"):
                                response_message = res.content
                            elif isinstance(res, dict) and "content" in res:
                                response_message = res["content"]
                            else:
                                response_message = str(res)
                        else:
                            logger.warning("Son durumda reservation_response bulunamadı")
                            response_message = "Üzgünüm, isteğinizi şu anda işleyemiyorum."
                        
                        # Yanıtı gönder
                        logger.info(f"Yanıt gönderiliyor: {from_number}")
                        success = await send_response(from_number, response_message, "text")
                        
                        if not success:
                            logger.error("Yanıt gönderme başarısız oldu")
                            return Response(content="Failed to send message", status_code=500)
                        
                        logger.info("İşlem başarıyla tamamlandı")
                        return Response(content="Message processed", status_code=200)
                    else:
                        logger.error("İş akışı tamamlanamadı veya son durum bulunamadı")
                        return Response(content="Workflow did not complete successfully", status_code=500)
                        
                except Exception as e:
                    logger.error(f"İş akışı çalıştırma hatası: {e}")
                    return Response(content=f"Workflow execution error: {str(e)}", status_code=500)

        elif "statuses" in change_value:
            logger.info("Durum güncellemesi alındı")
            return Response(content="Status update received", status_code=200)

        else:
            logger.warning(f"Bilinmeyen olay türü: {change_value.keys()}")
            return Response(content="Unknown event type", status_code=400)

    except Exception as e:
        logger.error(f"Mesaj işleme hatası: {e}")
        return Response(content=f"Internal server error: {str(e)}", status_code=500)

async def send_response(
    from_number: str,
    response_text: str,
    message_type: str = "text",
    media_content: bytes = None,
) -> bool:
    """Send response to user via WhatsApp API."""
    try:
        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json",
        }

        if message_type == "text":
            json_data = {
                "messaging_product": "whatsapp",
                "to": from_number,
                "type": "text",
                "text": {"body": response_text},
            }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"https://graph.facebook.com/v21.0/{WHATSAPP_PHONE_NUMBER_ID}/messages",
                headers=headers,
                json=json_data,
            )
            
        response_data = response.json()

        return response.status_code == 200
    except Exception as e:
        logger.error(f"WhatsApp yanıtı gönderme hatası: {e}")
        return False