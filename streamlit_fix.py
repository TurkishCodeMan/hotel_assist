#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# PyTorch-Streamlit uyumluluk düzeltmesini uygula
import streamlit_torch_patch

import os
import logging
import asyncio
import streamlit as st
from contextlib import AsyncExitStack, asynccontextmanager
import anyio
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

class MCPServerManager:
    """MCP sunucuları yönetmek için sınıf"""
    
    def __init__(self):
        self.servers = {}
        
    def register_server(self, server_id, server_path, description=None):
        """Yeni bir MCP sunucu kaydı ekler
        
        Args:
            server_id: Sunucu ID'si
            server_path: MCP sunucu betiğinin yolu
            description: İsteğe bağlı açıklama
        """
        self.servers[server_id] = {
            "path": server_path,
            "description": description or f"{server_id} MCP sunucusu"
        }
        logger.info(f"MCP sunucusu kaydedildi: {server_id} - {server_path}")
        return server_id
        
    def get_server(self, server_id):
        """ID'ye göre sunucu bilgilerini döndürür"""
        if server_id not in self.servers:
            logger.warning(f"MCP sunucusu bulunamadı: {server_id}")
            return None
        return self.servers[server_id]
        
    def get_all_servers(self):
        """Tüm kayıtlı sunucuları döndürür"""
        return self.servers
        
    def remove_server(self, server_id):
        """Bir sunucu kaydını kaldırır"""
        if server_id in self.servers:
            del self.servers[server_id]
            logger.info(f"MCP sunucusu kaldırıldı: {server_id}")
            return True
        return False

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
        
        # MCP sunucularını yönetmek için sınıfı başlat
        st.session_state.mcp_manager = MCPServerManager()
        
        # Varsayılan sunucuları kaydet
        sheets_path = "/Users/huseyin/Documents/deep-learning/wp_agent/mcp_servers/google-sheets-mcp/sheet.py"
        st.session_state.mcp_manager.register_server(
            "sheets", 
            sheets_path, 
            "Google Sheets Rezervasyon MCP"
        )
        
        # Agent-MCP eşleştirmelerini tut
        st.session_state.agent_mcp_mapping = {
            "reservation_agent": "sheets",
            # Gelecekte eklenecek farklı ajanlar için
            # "memory_agent": "memory_mcp",
            # "support_agent": "support_mcp"
        }
        
        # Bağlantı takibi için durum değişkenleri
        st.session_state.active_connections = {}  # MCP-ID -> connection_info
        st.session_state.connection_timeout = 30  # Saniye cinsinden
        st.session_state.max_connection_attempts = 3
        st.session_state.last_reset_time = time.time()

@asynccontextmanager
async def managed_mcp_connection(agent_name):
    """Agent adına göre uygun MCP bağlantısını yöneten asenkron context manager
    
    Args:
        agent_name: Hangi ajanın MCP'sine bağlanacağı
        
    Yields:
        (tools, session, workflow) üçlüsü
    """
    # Agent için tanımlı MCP sunucusunu bul
    mcp_id = st.session_state.agent_mcp_mapping.get(agent_name)
    if not mcp_id:
        logger.error(f"'{agent_name}' ajanı için tanımlı MCP sunucusu bulunamadı")
        yield [], None, None
        return
    
    server_info = st.session_state.mcp_manager.get_server(mcp_id)
    if not server_info:
        logger.error(f"'{mcp_id}' ID'li MCP sunucusu bulunamadı")
        yield [], None, None
        return
    
    mcp_path = server_info["path"]
    connection_id = f"{mcp_id}_{int(time.time() * 1000)}"  # Benzersiz bağlantı ID'si
    
    # Aktif bağlantı yoksa veya zaman aşımına uğradıysa
    current_time = time.time()
    connection_info = st.session_state.active_connections.get(mcp_id, {})
    connection_age = current_time - connection_info.get("timestamp", 0)
    
    if (not connection_info.get("active", False) or 
        connection_age > st.session_state.connection_timeout or
        connection_info.get("attempts", 0) >= st.session_state.max_connection_attempts):
        
        # Yeni bağlantı kurulacak, bilgileri güncelle
        connection_info = {
            "id": connection_id,
            "timestamp": current_time,
            "attempts": connection_info.get("attempts", 0) + 1,
            "active": False,
            "session": None,
            "workflow": None
        }
        st.session_state.active_connections[mcp_id] = connection_info
    
    logger.info(f"MCP bağlantısı başlatılıyor: {mcp_id} (ID: {connection_id})")
    
    stack = AsyncExitStack()
    session = None
    tools = []
    
    try:
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
        logger.info(f"MCP oturumu başlatıldı: {mcp_id} (ID: {connection_id})")
        
        # Kullanılabilir araçları al
        tools_response = await session.list_tools()
        tools = tools_response.tools
        logger.info(f"MCP araçları yüklendi: {len(tools)} araç bulundu - {mcp_id}")
        
        # Bağlantı durumunu güncelle
        connection_info["active"] = True
        connection_info["attempts"] = 0  # Başarılı bağlantı olduğu için sıfırla
        connection_info["session"] = session
        
        # Her bir ajan için özel yapılandırma oluştur
        agent_mcp_config = {}
        
        # İstenen ajanın konfigürasyonunu hazırla
        # Bu, birden fazla MCP sunucusuyla çalışırken önemli
        agent_mcp_config[agent_name] = {
            "server": server,
            "model": model,
            "model_endpoint": model_endpoint,
            "tools": tools,
            "session": session
        }
        
        # Graf ve iş akışını oluştur - Agent tipine özgü MCP yapılandırması ile
        graph = create_graph(
            server=server, 
            model=model, 
            model_endpoint=model_endpoint, 
            session=session,
            agent_mcp_config=agent_mcp_config
        )
        workflow = compile_workflow(graph)
        
        # Workflow'u kaydet
        connection_info["workflow"] = workflow
        st.session_state.active_connections[mcp_id] = connection_info
        
        # Context manager değerlerini döndür
        yield tools, session, workflow
        
    except Exception as e:
        # Bağlantı başarısız olduğunda oturum durumunu güncelle
        logger.exception(f"MCP bağlantı hatası ({mcp_id}, ID: {connection_id}): {e}")
        connection_info["active"] = False
        st.session_state.active_connections[mcp_id] = connection_info
        yield [], None, None
        
    finally:
        # Context çıkışında kaynakları temizle
        try:
            logger.info(f"MCP bağlantısı kapatılıyor: {mcp_id} (ID: {connection_id})")
            await stack.__aexit__(None, None, None)
            connection_info["active"] = False
            st.session_state.active_connections[mcp_id] = connection_info
            logger.info(f"MCP bağlantısı başarıyla kapatıldı: {mcp_id} (ID: {connection_id})")
        except Exception as e:
            logger.error(f"MCP bağlantısını kapatırken hata ({mcp_id}, ID: {connection_id}): {e}")
            # Bağlantı zaten kapalı olabilir, durumu güncelle
            connection_info["active"] = False
            st.session_state.active_connections[mcp_id] = connection_info

async def display_main_ui(state):
    """Ana UI'ı göster ve kullanıcı etkileşimlerini işle"""
    render_header()
    render_conversation(st.session_state.conversation)
    render_sidebar_state(state)
    
    # MCP yönetici bölümünü UI'a ekle
    with st.sidebar.expander("MCP Sunucu Yönetimi", expanded=False):
        st.subheader("Kayıtlı MCP Sunucuları")
        for server_id, server_info in st.session_state.mcp_manager.get_all_servers().items():
            with st.container():
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.code(f"{server_id}: {server_info['description']}")
                    st.text(f"Yol: {server_info['path']}")
                    
                    # MCP-Agent eşleştirmeleri
                    agent_list = [agent for agent, mcp in st.session_state.agent_mcp_mapping.items() if mcp == server_id]
                    if agent_list:
                        st.text(f"Bağlı ajanlar: {', '.join(agent_list)}")
                
                with col2:
                    # Silme butonu
                    if st.button("Sil", key=f"delete_{server_id}"):
                        # Önce bu sunucuyu kullanan ajanları kontrol et
                        if agent_list:
                            st.warning(f"Bu sunucu şu ajanlar tarafından kullanılıyor: {', '.join(agent_list)}")
                        else:
                            # Bağlantı aktifse kapat
                            if server_id in st.session_state.active_connections:
                                conn_info = st.session_state.active_connections[server_id]
                                if conn_info.get("active", False):
                                    st.warning("Aktif bağlantı kapatılıyor...")
                                    # Aktif bağlantıları kapatma işlemi burada yapılabilir
                                    # Ancak asenkron bir işlev gerektirir
                                conn_info["active"] = False
                            
                            # Sunucuyu kaldır
                            if st.session_state.mcp_manager.remove_server(server_id):
                                st.success(f"{server_id} sunucusu kaldırıldı")
                                st.rerun()
                st.divider()
        
        # Yeni MCP sunucusu ekleme formu
        st.subheader("Yeni MCP Sunucusu Ekle")
        with st.form(key="add_mcp_form"):
            new_server_id = st.text_input("Sunucu ID", key="new_server_id")
            new_server_path = st.text_input("Sunucu Betik Yolu", key="new_server_path")
            new_server_desc = st.text_input("Açıklama", key="new_server_desc", value="MCP Sunucusu")
            
            # Ajanlarla eşleştirme
            st.subheader("Ajanlarla Eşleştir")
            agents_to_connect = []
            # Mevcut ajanları listele
            agent_names = ["reservation_agent", "memory_extraction_agent"]
            for agent in agent_names:
                if st.checkbox(f"{agent}", key=f"connect_{agent}"):
                    agents_to_connect.append(agent)
            
            submit_button = st.form_submit_button(label="Ekle")
            
            if submit_button:
                if not new_server_id or not new_server_path:
                    st.error("Sunucu ID ve yol gereklidir.")
                else:
                    # Yol geçerli mi kontrol et
                    if os.path.exists(new_server_path):
                        # Sunucuyu kaydet
                        st.session_state.mcp_manager.register_server(
                            new_server_id, 
                            new_server_path, 
                            new_server_desc
                        )
                        
                        # Seçilen ajanları bu MCP ile eşleştir
                        for agent in agents_to_connect:
                            st.session_state.agent_mcp_mapping[agent] = new_server_id
                        
                        st.success(f"{new_server_id} sunucusu başarıyla eklendi")
                        # Ajanlar için gereken araçları alabilmek için bağlantıyı test et
                        st.info("Bağlantı test ediliyor...")
                        # Not: Gerçek bağlantı testi asenkron olacağından burada yapılamaz
                        # Sadece kaydedilir ve ilk kullanımda test edilir
                        st.rerun()
                    else:
                        st.error(f"Belirtilen yol bulunamadı: {new_server_path}")
    
    # Ajan-MCP Eşleştirme Bölümü
    with st.sidebar.expander("Ajan-MCP Eşleştirmeleri", expanded=False):
        st.subheader("Ajan MCP Eşleştirmeleri")
        
        # Mevcut eşleştirmeleri göster ve düzenleme imkanı sun
        servers = list(st.session_state.mcp_manager.get_all_servers().keys())
        if servers:
            for agent in st.session_state.agent_mcp_mapping.keys():
                current_mcp = st.session_state.agent_mcp_mapping.get(agent)
                new_mcp = st.selectbox(
                    f"{agent} için MCP", 
                    options=servers,
                    index=servers.index(current_mcp) if current_mcp in servers else 0,
                    key=f"select_{agent}_mcp"
                )
                
                if new_mcp != current_mcp:
                    st.session_state.agent_mcp_mapping[agent] = new_mcp
                    st.success(f"{agent} artık {new_mcp} MCP'sine bağlı")
        else:
            st.info("Henüz kayıtlı MCP sunucusu bulunmuyor")
    
    user_input = render_message_form()

    # Form gönderildiyse VE kullanıcı bir mesaj girdiyse (boş değilse)
    if st.session_state.form_submitted and user_input and user_input.strip():
        logger.debug(f"Kullanıcı mesajı alındı: {user_input}")
        st.session_state.conversation.append(("user", user_input))
        st.session_state.form_submitted = False # Flag'ı burada temizleyelim

        # Graph'a gönderilecek state'i hazırla
        from langchain_core.messages import HumanMessage
        # Önceki state'i al (varsa)
        previous_state = st.session_state.get("session_state", state.copy()) 
        
        # Yeni input dict'ini oluştur
        dict_inputs = {
            # research_question sadece son dolu kullanıcı mesajını içerir
            "research_question": [HumanMessage(content=user_input)],
            # messages, önceki mesajları ve yeni kullanıcı mesajını içerir
            "messages": previous_state.get("messages", []) + [HumanMessage(content=user_input)]
        }
        # Önceki state'teki diğer alanları yeni input'a ekle (messages ve research_question hariç)
        for key, value in previous_state.items():
            if key not in ["research_question", "messages"]:
                dict_inputs[key] = value
        
        logger.debug(f"Graph'a gönderilen input: {dict_inputs}")

        with st.spinner("Yanıt hazırlanıyor..."):
            # Hangi ajan için MCP bağlantısı açılacak?
            agent_name = "reservation_agent"  # Varsayılan olarak rezervasyon ajanı
            
            # Bağlantı yönetimi yaklaşımı kullanılıyor - agent adına göre
            async with managed_mcp_connection(agent_name) as (mcp_tools, mcp_session, workflow):
                if not mcp_session or not workflow:
                    st.error(f"{agent_name} için MCP sunucusuna bağlanılamadı. Lütfen sayfayı yenileyip tekrar deneyin.")
                    st.session_state.conversation.append(("assistant", "Bağlantı hatası. Lütfen sayfayı yenileyip tekrar deneyin."))
                    st.rerun()
                
                try:
                    # İş akışını çalıştır
                    last_event = None
                    async for event in workflow.astream(dict_inputs, {"recursion_limit": iterations}):
                        last_event = event

                    if last_event and "end" in last_event:
                        # Graph'tan dönen son state'i kaydet
                        st.session_state.session_state = last_event["end"]
                        logger.debug(f"Graph'tan dönen son state: {st.session_state.session_state}")
                        
                        final_response = ""

                        # 'messages' içindeki son AI mesajını bulmaya çalış
                        if "messages" in st.session_state.session_state:
                            all_messages = st.session_state.session_state["messages"]
                            if isinstance(all_messages, list) and all_messages:
                                # Son mesajı al
                                last_msg_from_state = all_messages[-1]
                                
                                # Son mesajın AI mesajı olup olmadığını ve içeriğini kontrol et
                                role = getattr(last_msg_from_state, 'type', None) # Veya .role
                                if role == 'ai' or isinstance(last_msg_from_state, dict) and last_msg_from_state.get('role') == 'assistant':
                                    content = getattr(last_msg_from_state, 'content', None) or last_msg_from_state.get('content')
                                    if content:
                                         # Yanıtı işle ve temizle
                                        parsed = safe_parse_message(content)
                                        final_response = clean_json_text(parsed.get("response", str(content)))
                                    else:
                                        logger.warning("Son AI mesajında içerik bulunamadı.")
                                else:
                                     logger.warning(f"State'deki son mesaj bir AI mesajı değil: {last_msg_from_state}")
                            else:
                                logger.warning("'messages' listesi boş veya liste değil.")
                        else:
                             logger.warning("Son state içinde 'messages' anahtarı bulunamadı.")

                        st.session_state.conversation.append(("assistant", final_response or "Yanıt işlenemedi."))
                        st.rerun()
                        
                except anyio.ClosedResourceError:
                    logger.error(f"ClosedResourceError: Bağlantı kaynak hatası")
                    mcp_id = st.session_state.agent_mcp_mapping.get(agent_name)
                    if mcp_id in st.session_state.active_connections:
                        st.session_state.active_connections[mcp_id]["active"] = False
                    st.session_state.conversation.append(("assistant", "Bağlantı hatası oluştu. Lütfen sorunuzu tekrar sorun."))
                    st.rerun()
                except Exception as e:
                    logger.exception(f"İşlem sırasında hata: {e}")
                    st.session_state.conversation.append(("assistant", f"Üzgünüm, bir hata oluştu: {str(e)}"))
                    st.rerun()
                    
    # Kullanıcı boş mesaj gönderdiyse veya form gönderilmediyse
    elif st.session_state.form_submitted:
        st.warning("Lütfen bir mesaj girin.")
        st.session_state.form_submitted = False # Flag'ı temizle

async def main():
    """Ana uygulama akışı"""
    # Sayfayı ayarla
    st.set_page_config(page_title="Altıkulaç Otel Asistanı", page_icon="🏨", layout="wide")
    
    # Oturum durumunu başlat
    initialize_session_state()
    
    # Ana UI'ı göster ve etkileşimleri işle
    await display_main_ui(state=st.session_state.session_state)
    
    # Uygulama ilk defa başlatılıyorsa, başlatıldı olarak işaretle
    if not st.session_state.initialized:
        st.session_state.initialized = True

if __name__ == "__main__":
    try:
        # Ana uygulamayı çalıştır
        asyncio.run(main())
    except Exception as e:
        logger.exception(f"Ana döngüde hata: {e}")
