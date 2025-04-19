import streamlit as st
import re
import json
import logging
import traceback

logger = logging.getLogger(__name__)

def clean_json_text(text):
    """JSON string içindeki unicode ve kaçış karakterlerini düzeltir."""
    if not text:
        return ""

    text = text.replace("\\u00fc", "ü").replace("\\u00f6", "ö").replace("\\u00e7", "ç")
    text = text.replace("\\u011f", "ğ").replace("\\u0131", "ı").replace("\\u015f", "ş")
    text = text.replace("\\u00c7", "Ç").replace("\\u011e", "Ğ").replace("\\u0130", "İ")
    text = text.replace("\\u00d6", "Ö").replace("\\u015e", "Ş").replace("\\u00dc", "Ü")
    text = text.replace("\\n", "\n").replace("\\\"", "\"").replace("\\'", "'")
    return text

def safe_parse_message(message_content):
    """Gelen string mesajı güvenli şekilde parse etmeye çalışır."""
    if not message_content:
        return {}

    try:
        # Düz metin yanıtını kontrol et (JSON olmayan yanıtlar için)
        if isinstance(message_content, str):
            # Yanıt zaten JSON değilse, doğrudan yanıt olarak döndür
            if not (message_content.strip().startswith('{') or message_content.strip().startswith('[')):
                logger.info("JSON olmayan metin yanıtı tespit edildi, JSON çözümleme atlanıyor")
                return {"response": message_content}
            
            # JSON benzeri içerik ancak muhtemelen basit metin yanıtı
            # Rezervasyon ile ilgili anahtar kelimeler içermiyor ve json formatında değilse,
            # muhtemelen basit bir yanıttır.
            reservation_keywords = [
                'rezervasyon', 'kayıt', 'ekleme', 'güncelleme', 'silme', 'listeleme',
                'reservation', 'check-in', 'checkout', 'oda', 'hotel', 'tarih'
            ]
            
            # Mesaj içeriğinde bu anahtar kelimelerin varlığını kontrol et
            content_lower = message_content.lower()
            if (not any(keyword in content_lower for keyword in reservation_keywords) and
                not (message_content.strip().startswith('{') and message_content.strip().endswith('}'))):
                logger.info("Rezervasyon içermeyen düz metin yanıtı tespit edildi")
                return {"response": message_content}
            
            # Emoji ve gereksiz karakterleri temizle
            emojis = ["📅", "👤", "🏨", "👪", "💰", "✅", "📋", "🔄"]
            for e in emojis:
                message_content = message_content.replace(e, "")
            message_content = message_content.replace("'", '"').replace("null", "None")
            message_content = message_content.replace("\n", "\\n")
            message_content = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', message_content)

        try:
            # JSON çözümlemeyi dene
            return json.loads(message_content.replace("None", "null"))
        except json.JSONDecodeError:
            logger.warning("JSON decode error, regex ile denenecek...")
            # İç içe JSON durumunu kontrol et - mevcut sorunumuz bu
            if message_content.startswith('{"response":') and '"}"' in message_content:
                # İç içe geçmiş JSON formatı - içteki JSON'u düzgün çıkar
                try:
                    # Dıştaki JSON parantezlerini kaldır
                    inner_content = re.search(r'"response":"(.*)"', message_content)
                    if inner_content:
                        inner_json = inner_content.group(1)
                        inner_json = inner_json.replace('\\"', '"')
                        return {"response": inner_json}
                except Exception as e:
                    logger.warning(f"İç içe JSON parsing hatası: {e}")
            
            # Normal regex ile yanıt alanını çıkarmayı dene
            match = re.search(r'"response":"([^"]+)"', message_content)
            if match:
                return {"response": match.group(1)}
            
            # JSON'a benzeyen alan var mı?
            json_like_pattern = re.search(r'\{[^\}]+\}', message_content)
            if json_like_pattern:
                try:
                    json_content = json.loads(json_like_pattern.group(0))
                    return json_content
                except:
                    pass

        # Alternatif: dict-like string varsa değerlendir
        try:
            result = eval(message_content)
            if isinstance(result, dict):
                return result
        except Exception:
            pass

    except Exception as e:
        logger.error(f"safe_parse_message hatası: {e}")
        logger.error(traceback.format_exc())
        
    # Hiçbir şekilde JSON yapamadıysak, ham içeriği response olarak döndür
    if isinstance(message_content, str):
        return {"response": message_content}
    return {}

def render_message_form():
    with st.form(key="chat_form", clear_on_submit=True):
        st.markdown("""
        <div style="margin-top: 1.5rem; margin-bottom: 0.5rem; color: #E0E0E0; font-weight: 500; font-size: 1rem;">
            Asistana mesajınız:
        </div>
        """, unsafe_allow_html=True)

        user_message = st.text_input(
            label="",
            key="user_message",
            placeholder="Nasıl yardımcı olabilirim? Rezervasyon yapmak, bilgi almak için yazın..."
        )

        cols = st.columns([3, 2, 2])
        with cols[1]:
            st.form_submit_button(
                "💬 Gönder",
                on_click=lambda: st.session_state.update({"form_submitted": True}),
                use_container_width=True
            )
        with cols[2]:
            st.form_submit_button(
                "🔄 Yeni Sohbet",
                on_click=lambda: st.session_state.update({"conversation": []}),
                use_container_width=True
            )

        if not st.session_state.conversation:
            st.markdown("""
            <div style="margin-top: 1rem; padding: 1rem; background-color: #333333; border-radius: 10px; border: 1px dashed #424242;">
                <div style="font-weight: 500; margin-bottom: 0.5rem; color: #E0E0E0;">✨ Örnek Sorular:</div>
                <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                    <div style="background-color: #424242; padding: 0.4rem 0.8rem; border-radius: 20px; font-size: 0.9rem; border: 1px solid #616161; color: #E0E0E0;">10-15 Ağustos arası oda müsaitliği</div>
                    <div style="background-color: #424242; padding: 0.4rem 0.8rem; border-radius: 20px; font-size: 0.9rem; border: 1px solid #616161; color: #E0E0E0;">2 kişilik oda fiyatları nedir?</div>
                    <div style="background-color: #424242; padding: 0.4rem 0.8rem; border-radius: 20px; font-size: 0.9rem; border: 1px solid #616161; color: #E0E0E0;">Rezervasyonumu iptal etmek istiyorum</div>
                    <div style="background-color: #424242; padding: 0.4rem 0.8rem; border-radius: 20px; font-size: 0.9rem; border: 1px solid #616161; color: #E0E0E0;">Otelin özellikleri nelerdir?</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        return user_message  # Girdi mesajı döndürülüyor

def create_state_display(session_state):
    """Oturum state'ini gösteren sidebar paneli oluşturur."""
    st.sidebar.markdown("### 🧠 State Görünümü")

    if "reservation_response" in session_state:
        if session_state["reservation_response"]:
            res_data = session_state["reservation_response"][-1]
            if hasattr(res_data, "content"):
                data = safe_parse_message(res_data.content)
                st.sidebar.markdown("**📋 Son Rezervasyon Yanıtı**")
                st.sidebar.json(data)

    if "new_reservation" in session_state:
        try:
            st.sidebar.markdown("**🆕 Yeni Rezervasyon**")
            st.sidebar.json(safe_parse_message(session_state["new_reservation"]))
        except:
            st.sidebar.write(session_state["new_reservation"])

    if "reservations_result" in session_state and session_state["reservations_result"]:
        st.sidebar.markdown("**📄 Rezervasyon Sonuçları**")
        res = session_state["reservations_result"][-1]
        if hasattr(res, "content"):
            data = safe_parse_message(res.content)
            st.sidebar.json(data)

    # Diğer tüm state verileri
    other_data = {k: v for k, v in session_state.items()
                  if not isinstance(v, list) and not k.endswith("_result")}
    if other_data:
        st.sidebar.markdown("**⚙️ Diğer State Değerleri**")
        st.sidebar.json(other_data)


def render_header():
    st.markdown("""
    <div class="custom-card" style="text-align: center; padding: 2rem; background: linear-gradient(135deg, #3498db, #1E88E5); color: white; border: none; margin-bottom: 2rem;">
        <div style="display: flex; justify-content: center; align-items: center; margin-bottom: 1rem;">
            <span style="font-size: 3rem; margin-right: 15px;">🏨</span>
            <h1 style="margin: 0; color: white; font-size: 2.5rem; font-weight: 700;">Altıkulaç Otel</h1>
        </div>
        <h2 style="margin-top: 0; color: white; font-weight: 500; margin-bottom: 1.5rem;">Rezervasyon Asistanı</h2>
        <p style="font-size: 1.1rem; color: rgba(255, 255, 255, 0.9); max-width: 800px; margin: 0 auto; line-height: 1.6;">
            Altıkulaç Otel'e hoş geldiniz! Oda rezervasyonu yapmak, mevcut rezervasyonunuzu yönetmek veya otel hakkında sorularınız için benimle sohbet edebilirsiniz.
        </p>
    </div>
    """, unsafe_allow_html=True)

def render_conversation(conversation):
    if not conversation:
        st.markdown("""
        <div style="display: flex; margin-bottom: 1rem; justify-content: center;">
            <div style="background-color: rgba(30, 136, 229, 0.05); border-radius: 15px; padding: 1.5rem; text-align: center; max-width: 80%; border: 1px dashed var(--primary-color);">
                <div style="font-size: 2rem; margin-bottom: 1rem; color: var(--primary-color);">👋</div>
                <div style="font-weight: 600; font-size: 1.1rem; margin-bottom: 0.5rem; color: var(--primary-color);">Merhaba, ALTIKULAÇ Otel'e Hoş Geldiniz!</div>
                <div style="color: var(--text-secondary); line-height: 1.6;">
                    Rezervasyon yapmak, mevcut rezervasyonunuzu kontrol etmek veya bilgi almak için sorularınızı yazabilirsiniz.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    for role, message in conversation:
        if role == "user":
            st.markdown(f"""
                <div class="chat-message-user">
                    <div class="chat-bubble-user">
                        <div class="chat-header">👤 Siz</div>
                        <div>{message}</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
                <div class="chat-message-assistant">
                    <div class="chat-bubble-assistant">
                        <div class="chat-header">🤖 Asistan</div>
                        <div style="white-space: pre-wrap;">{message}</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

def render_sidebar_state(state):
    if hasattr(state, "keys"):
        st.sidebar.markdown("### 🔍 State Bilgileri (Debug)")
        st.sidebar.write("State içeriği (session_state):", state)
        create_state_display(state)
