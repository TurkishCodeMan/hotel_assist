#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import asyncio
import streamlit as st
from contextlib import AsyncExitStack, asynccontextmanager
import anyio
import functools
import time
import traceback

# UI
from ui import (
    clean_json_text,
    safe_parse_message,
    create_state_display,
    render_header,
    render_conversation,
    render_sidebar_state,
    render_message_form
)

# LangGraph
from agent_graph.graph import create_graph, compile_workflow
from states.state import state

# MCP
from mcp import StdioServerParameters, ClientSession
from mcp.client.stdio import stdio_client

server = "gemini"
model = "gemini-2.0-flash"
model_endpoint = None
iterations = 40

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MCPConnectionManager:
    """MCP bağlantı yönetimi için sınıf"""
    
    def __init__(self, command="python", args=None, connection_timeout=30, max_connection_attempts=3):
        self.command = command
        self.args = args or []
        self.connection_timeout = connection_timeout
        self.max_connection_attempts = max_connection_attempts
        self.connection_id = None
        self.connection_timestamp = 0
        self.connection_active = False
        self.connection_attempts = 0
        self.stack = None  # Stack nesnesini sakla
        self.close_future = None  # Kapanış için future
    
    async def _safe_close_resources(self, stack):
        """Kaynakları güvenli bir şekilde kapatır"""
        try:
            # Tüm kaynakları serbest bırak
            logger.info("Kaynaklar güvenli bir şekilde kapatılıyor...")
            
            # 5 saniye içinde kapanmasını dene
            try:
                # Shield kullanarak mevcut task iptallerinden koruyoruz
                # Bu işlem ayrı bir task olarak çalışacak
                await asyncio.wait_for(
                    asyncio.shield(stack.__aexit__(None, None, None)), 
                    timeout=5.0
                )
                logger.info("Kaynaklar başarıyla kapatıldı")
                return True
            except asyncio.TimeoutError:
                logger.warning("Kaynak kapatma zaman aşımına uğradı (5 saniye)")
                return False
            except Exception as e:
                logger.error(f"Kaynak kapatma hatası oluştu: {str(e)}")
                return False
        finally:
            # Her durumda bağlantı durumunu güncelle
            self.connection_active = False
    
    @asynccontextmanager
    async def create_connection(self):
        """MCP bağlantısı oluşturur ve yönetir"""
        self.connection_id = int(time.time() * 1000)  # Milisaniye cinsinden timestamp
        self.connection_timestamp = time.time()
        self.connection_attempts += 1
        
        logger.info(f"Google Sheets MCP bağlantısı başlatılıyor (ID: {self.connection_id})")
        logger.info(f"MCP komut: {self.command} {' '.join(self.args)}")
        
        # Yeni bir stack oluştur
        stack = AsyncExitStack()
        session = None
        tools = []
        
        try:
            server_params = StdioServerParameters(command=self.command, args=self.args)
            
            # Asenkron kaynak yönetimi için stack kullanımı
            await stack.__aenter__()
            
            # MCP istemci akışını oluştur
            client_stream = stdio_client(server_params)
            stdio, write = await stack.enter_async_context(client_stream)
            
            # ClientSession oluştur ve başlat
            session = ClientSession(stdio, write)
            await stack.enter_async_context(session)
            
            await session.initialize()
            logger.info(f"Google Sheets MCP oturumu başlatıldı (ID: {self.connection_id})")
            
            # Kullanılabilir araçları al
            tools_response = await session.list_tools()
            tools = tools_response.tools
            logger.info(f"MCP araçları yüklendi: {len(tools)} araç bulundu")
            
            # Bağlantı durumunu güncelle
            self.connection_active = True
            self.connection_attempts = 0  # Başarılı bağlantı olduğu için sıfırla
            
            # Graf ve iş akışını oluştur
            graph = create_graph(server=server, model=model, model_endpoint=model_endpoint, 
                                tools=tools, session=session)
            workflow = compile_workflow(graph)
            
            # Context manager değerlerini döndür
            yield tools, session, workflow
            
        except Exception as e:
            # Bağlantı başarısız olduğunda oturum durumunu güncelle
            logger.exception(f"Google Sheets MCP bağlantı hatası (ID: {self.connection_id}): {e}")
            self.connection_active = False
            yield [], None, None
            
        finally:
            # Context çıkışında kaynakları güvenli şekilde serbest bırak
            if self.connection_id is not None:  # Bağlantı ID'si varsa
                try:
                    logger.info(f"Google Sheets MCP bağlantısı kapatılıyor (ID: {self.connection_id})")
                    
                    # Kapatma işlemini arka planda çalıştır ve sonucu bekleme
                    # Bu sayede kapatma işlemi akışı bloke etmez
                    if hasattr(asyncio, 'create_task') and asyncio.get_event_loop().is_running():
                        # Event loop açıksa ve kapatmıyorsa, background task olarak çalıştır
                        asyncio.create_task(self._safe_close_resources(stack))
                    else:
                        # Event loop kapalıysa veya kapanıyorsa, synchronous olarak kapat
                        self.connection_active = False
                    
                    logger.info(f"Google Sheets MCP bağlantı kapatma süreci başlatıldı (ID: {self.connection_id})")
                    
                except Exception as e:
                    logger.error(f"Google Sheets MCP bağlantısını kapatırken hata (ID: {self.connection_id}): {e}")
                    self.connection_active = False
    
    def need_reset(self, current_time=None):
        """Bağlantının sıfırlanması gerekip gerekmediğini kontrol eder"""
        if current_time is None:
            current_time = time.time()
        
        # Bağlantı çok eskiyse veya aktif değilse sıfırla
        connection_age = current_time - self.connection_timestamp
        return (
            not self.connection_active or
            connection_age > self.connection_timeout or
            self.connection_attempts < self.max_connection_attempts
        )
    
    def reset_connection_state(self):
        """Bağlantı durumunu sıfırlar"""
        self.connection_active = False
        self.connection_timestamp = 0
        self.connection_id = None


def initialize_session_state():
    """Streamlit oturum durumunu başlat veya sıfırla"""
    if "initialized" not in st.session_state:
        # İlk kez başlatılıyorsa, tüm durum değişkenlerini ayarla
        st.session_state.conversation = []
        st.session_state.form_submitted = False
        st.session_state.initialized = False
        st.session_state.session_state = state.copy()
        st.session_state.workflow = None
        st.session_state.session = None
        st.session_state.last_render_time = time.time()  # Render zamanı takibi
        st.session_state.render_complete = False  # Render tamamlandı mı?
        
        # Sadece Google Sheets MCP bağlantı yöneticisini oluştur
        st.session_state.connection_manager = MCPConnectionManager(
            command="npx",
            args=["gs-mcp"],
            connection_timeout=30,
            max_connection_attempts=3
        )
        st.session_state.last_reset_time = time.time()
        
        # Sidebar'a bilgi ekle
        st.sidebar.title("MCP Bilgileri")
        st.sidebar.info("Bu uygulama Google Sheets MCP kullanmaktadır.")
    else:
        # Konuşma geçmişini kontrol et, boş değilse ve render_complete false ise
        # render_complete'i true yap - bu sayede mesajlar gösterilir
        if not st.session_state.get("render_complete", False) and st.session_state.get("conversation", []):
            st.session_state.render_complete = True
            logger.info("render_complete = True olarak ayarlandı, mesajlar gösterilecek")

async def run_workflow(workflow, inputs):
    """LangGraph iş akışını çalıştırır ve son yanıtı işler"""
    try:
        last_event = None
        async for event in workflow.astream(inputs, {"recursion_limit": iterations}):
            last_event = event
            logger.info(f"Workflow event: {event}")

        if last_event and "end" in last_event:
            st.session_state.session_state = last_event["end"]
            # Basitleştirilmiş yanıt alma 
            return process_final_response(last_event["end"])
        else:
            logger.error("Workflow event 'end' bulunamadı")
            return "Yanıt alınamadı. Lütfen tekrar deneyiniz."
    except Exception as e:
        logger.exception(f"Workflow çalıştırma hatası: {e}")
        return f"Workflow hatası: {str(e)}"


def process_final_response(end_state):
    """Son durumdan yanıtı işler ve formatlar - GÜNCELLENDİ"""
    try:
        logger.info(f"Son durum: {end_state}")
        
        # reservation_response anahtarını kontrol et
        if "reservation_response" in end_state and end_state["reservation_response"]:
            res_list = end_state["reservation_response"]
            
            # Liste ise ve boş değilse SON öğeyi al
            if isinstance(res_list, list) and res_list:
                # En son mesajı alalım
                res = res_list[-1]
                logger.info(f"Liste tespit edildi, SON öğe alındı: {res}")
                
                # Yanıt içeriğini çıkar
                if hasattr(res, "content"):
                    return res.content
                elif isinstance(res, dict) and "content" in res:
                    return res["content"]
                else:
                    # Liste olmayan veya beklenmedik format durumunda string'e çevir
                    return str(res)
            else:
                # Liste değilse veya boşsa, olduğu gibi işlemeye çalış
                res = res_list  # Liste olmayan değeri ata
                if hasattr(res, "content"):
                    return res.content
                elif isinstance(res, dict) and "content" in res:
                    return res["content"]
                else:
                    return str(res)
        else:
            # Alternatif olarak messages anahtarındaki son mesajı al
            if "messages" in end_state and end_state["messages"]:
                messages = end_state["messages"]
                if isinstance(messages, list) and messages:
                    last_message = messages[-1]
                    if hasattr(last_message, "content"):
                        return last_message.content
                    elif isinstance(last_message, dict):
                        # İçerik yoksa tüm sözlüğü string yap
                        return last_message.get("content", str(last_message))
                    else:
                        return str(last_message)
                else:
                    # Mesaj listesi değilse veya boşsa, olduğu gibi string yap
                    return str(messages)
            
            # Hiçbir yanıt bulunamadıysa default mesaj
            logger.warning("End state'den yanıt alınamadı, varsayılan mesaj döndürülüyor.")
            return "Yanıt işlenirken bir sorun oluştu. Lütfen tekrar deneyin."
            
    except Exception as e:
        logger.exception(f"Yanıt işleme hatası: {e}")
        return f"Yanıt işlenemedi: {str(e)}"


async def display_main_ui(state):
    """Ana UI'ı göster ve kullanıcı etkileşimlerini işle"""
    render_header()
    
    # Google Sheets MCP bilgisi için sidebar'a bilgi ekle
    st.sidebar.title("MCP Bilgileri")
    st.sidebar.info("Bu uygulama Google Sheets MCP kullanmaktadır.")
    
    # Konuşma geçmişini logla ve render et
    logger.info(f"Konuşma geçmişi (display başlangıcı): {st.session_state.conversation}")
    render_conversation(st.session_state.conversation)
    
    # Yan paneli render et
    render_sidebar_state(state)
    
    # Kullanıcı giriş formunu göster
    user_input = render_message_form()

    if st.session_state.form_submitted and user_input:
        logger.info(f"Kullanıcı girişi işleniyor - form_submitted=True, Input: {user_input}")
        # Girdiyi işlenmeden önce bir değişkende sakla
        current_input = user_input
        # Formun tekrar gönderilmesini engelle
        st.session_state.form_submitted = False 
        
        # Kullanıcı mesajını ekle - spinner dışında gerçekleştirilsin
        st.session_state.conversation.append(("user", current_input))
        
        # İşlem tamamlandı flag'i
        process_completed = False
        
        # Spinner kullanarak SADECE yanıt alma işlemini gerçekleştirelim
        with st.spinner("Yanıt hazırlanıyor..."):
            try:
                # Kullanıcı mesajını zaten ekledik, şimdi sadece yanıt alma işlemini gerçekleştir
                dict_inputs = state.copy()
                dict_inputs["research_question"] = [msg for role, msg in st.session_state.conversation if role == "user"]
                
                # MCP ile etkileşim ve yanıt alma
                async with st.session_state.connection_manager.create_connection() as (tools, session, workflow):
                    if not session or not workflow:
                        error_msg = "Google Sheets MCP sunucusuna bağlanılamadı. Lütfen sayfayı yenileyip tekrar deneyin."
                        st.error(error_msg)
                        st.session_state.conversation.append(("assistant", error_msg))
                    else:
                        # İş akışını çalıştır
                        final_response = await run_workflow(workflow, dict_inputs)
                        
                        # Yanıtın bir string olduğundan emin ol
                        if not isinstance(final_response, str):
                            logger.warning(f"Yanıt string değil, dönüştürülüyor: {type(final_response)}")
                            final_response = str(final_response)
                        
                        # Yanıt ekle
                        logger.info(f"Alınan yanıt: {final_response}")
                        st.session_state.conversation.append(("assistant", final_response))
                        logger.info("Yanıt konuşmaya eklendi, arayüzde gösterilecek")
                
                # İşlem tamamlandı
                process_completed = True
            
            except Exception as e:
                logger.exception(f"Yanıt alma sırasında hata: {e}")
                error_msg = f"İşlem sırasında bir hata oluştu: {str(e)}"
                st.session_state.conversation.append(("assistant", error_msg))
                process_completed = True
        
        # Spinner tamamlandıktan sonra ve işlem başarılı olduysa sayfayı yenile
        if process_completed:
            logger.info("İşlem tamamlandı, sayfa yenileniyor...")
            st.session_state["last_render_time"] = time.time()
            
            # Çok kısa bir bekleme ekle (thread'in tamamlanması için)
            try:
                await asyncio.sleep(0.1)
            except:
                time.sleep(0.1)
            
            try:
                # rerun() çağrısını koruma altına al
                # Bu noktada yapılacak hata göz ardı edilebilir çünkü sayfa yenilenecek
                st.rerun()
            except Exception as e:
                logger.warning(f"Sayfa yenileme hatası (göz ardı edilebilir): {e}")


async def main():
    """Ana uygulama akışı"""
    try:
        # Sayfayı ayarla
        st.set_page_config(page_title="Altıkulaç Otel Asistanı", page_icon="🏨", layout="wide")
        
        # Oturum durumunu başlat
        initialize_session_state()
        
        # Ana UI'ı göster ve etkileşimleri işle
        await display_main_ui(state=st.session_state.session_state)
        
        # Uygulama ilk defa başlatılıyorsa, başlatıldı olarak işaretle
        if not st.session_state.initialized:
            st.session_state.initialized = True
            
        # Render tamamlandı mı, konuşma var mı kontrol et
        if not st.session_state.get("render_complete", False) and len(st.session_state.get("conversation", [])) > 0:
            # Render tamamlandığını işaretle
            st.session_state.render_complete = True
            logger.info("main: render_complete = True olarak ayarlandı")
            
            # Konuşma görüntülenirken bir sorun varsa, gecikmeli rerun deneyelim
            latest_message_time = time.time() - st.session_state.get("last_render_time", 0)
            if latest_message_time > 2.0:  # Son render'dan bu yana 2 saniyeden fazla geçtiyse
                logger.info("Ana işlemde eski render tespit edildi, sayfa yenileniyor...")
                time.sleep(0.3)  # Kısa bekleme
                st.rerun()
                
    except Exception as e:
        logger.exception(f"Ana döngüde hata: {e}")
        st.error(f"Uygulama çalıştırılırken bir hata oluştu: {str(e)}")

def run_app():
    """
    Streamlit uygulamasını asenkron olarak çalıştırır.
    Bu fonksiyon, asyncio tarafından oluşturulan hataları önlemek için
    event loop'un güvenli bir şekilde başlatılmasını ve kapatılmasını sağlar.
    """
    try:
        # Mevcut event loop var mı diye kontrol et
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                # Kapalıysa yeni bir loop oluştur
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            # Loop yoksa yeni bir tane oluştur
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Event loop'un düzgün kapanması için kaynakları temizle
        loop.set_exception_handler(lambda loop, context: None)
        
        # Uygulamayı çalıştır
        loop.run_until_complete(main())
        
        # Açık tüm görevleri temizle
        pending = asyncio.all_tasks(loop)
        if pending:
            logger.info(f"{len(pending)} bekleyen görev kapatılıyor...")
            for task in pending:
                task.cancel()
            
            # Görevlerin iptal edilmesini bekle
            try:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except:
                pass
            
    except Exception as e:
        logger.exception(f"Uygulama çalıştırma hatası: {e}")
        st.error(f"Uygulama başlatılırken bir hata oluştu: {str(e)}")
    finally:
        # Loop'u kapat
        try:
            loop.close()
        except:
            pass

if __name__ == "__main__":
    # Ana uygulamayı çalıştır
    run_app()

