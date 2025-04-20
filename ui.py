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
    st.markdown("""
    <style>
        /* Mesaj Giriş Alanı Stilleri */
        .input-container {
            margin-top: 2rem;
            margin-bottom: 1rem;
            border-radius: 12px;
            background-color: rgba(242, 242, 242, 0.1);
            padding: 1.5rem;
            border: 1px solid rgba(30, 136, 229, 0.2);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        }
        
        .input-label {
            margin-bottom: 0.8rem;
            color: #333;
            font-weight: 500;
            font-size: 1.1rem;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        
        /* Buton Stilleri */
        .button-primary {
            background: linear-gradient(135deg, #2979FF, #1E88E5);
            color: white;
            font-weight: 500;
            border: none;
            border-radius: 8px;
            padding: 0.6rem 1.2rem;
            transition: all 0.3s;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        
        .button-primary:hover {
            background: linear-gradient(135deg, #1E88E5, #1565C0);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            transform: translateY(-1px);
        }
        
        .button-secondary {
            background: rgba(0, 0, 0, 0.05);
            color: #666;
            font-weight: 500;
            border: 1px solid rgba(0, 0, 0, 0.1);
            border-radius: 8px;
            padding: 0.6rem 1.2rem;
            transition: all 0.3s;
        }
        
        .button-secondary:hover {
            background: rgba(0, 0, 0, 0.1);
            color: #333;
        }
        
        /* Örnek Sorular Stilleri */
        .example-questions {
            margin-top: 1rem;
            padding: 1rem;
            background-color: rgba(30, 136, 229, 0.05);
            border-radius: 10px;
            border: 1px dashed rgba(30, 136, 229, 0.3);
        }
        
        .example-title {
            font-weight: 500;
            margin-bottom: 0.8rem;
            color: #333;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .example-chips {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }
        
        .example-chip {
            background-color: rgba(30, 136, 229, 0.1);
            padding: 0.4rem 0.8rem;
            border-radius: 20px;
            font-size: 0.9rem;
            border: 1px solid rgba(30, 136, 229, 0.2);
            color: #1976D2;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .example-chip:hover {
            background-color: rgba(30, 136, 229, 0.2);
            border-color: rgba(30, 136, 229, 0.3);
            transform: translateY(-2px);
        }
    </style>
    
    <div class="input-container">
        <div class="input-label">
            <span>💬</span> Asistana mesajınız:
        </div>
    """, unsafe_allow_html=True)
    
    with st.form(key="chat_form", clear_on_submit=True):
        user_message = st.text_input(
            label="",
            key="user_message",
            placeholder="Nasıl yardımcı olabilirim? Rezervasyon yapmak, bilgi almak için yazın..."
        )

        cols = st.columns([5, 3, 3])
        with cols[1]:
            submit_button = st.form_submit_button(
                "💬 Gönder",
                on_click=lambda: st.session_state.update({"form_submitted": True}),
                use_container_width=True
            )
            st.markdown("""
            <style>
                div[data-testid="stFormSubmitButton"] > button {
                    background: linear-gradient(135deg, #2979FF, #1E88E5) !important;
                    color: white !important;
                    font-weight: 500 !important;
                    border: none !important;
                    border-radius: 8px !important;
                    padding: 0.6rem 1.2rem !important;
                    transition: all 0.3s !important;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1) !important;
                }
                div[data-testid="stFormSubmitButton"] > button:hover {
                    background: linear-gradient(135deg, #1E88E5, #1565C0) !important;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.2) !important;
                    transform: translateY(-1px) !important;
                }
            </style>
            """, unsafe_allow_html=True)
            
        with cols[2]:
            clear_button = st.form_submit_button(
                "🔄 Yeni Sohbet",
                on_click=lambda: st.session_state.update({"conversation": []}),
                use_container_width=True
            )
            st.markdown("""
            <style>
                div[data-testid="stFormSubmitButton"]:nth-of-type(2) > button {
                    background: rgba(0, 0, 0, 0.05) !important;
                    color: #666 !important;
                    font-weight: 500 !important;
                    border: 1px solid rgba(0, 0, 0, 0.1) !important;
                    border-radius: 8px !important;
                    padding: 0.6rem 1.2rem !important;
                    transition: all 0.3s !important;
                }
                div[data-testid="stFormSubmitButton"]:nth-of-type(2) > button:hover {
                    background: rgba(0, 0, 0, 0.1) !important;
                    color: #333 !important;
                }
            </style>
            """, unsafe_allow_html=True)

        if not st.session_state.conversation:
            st.markdown("""
            <div class="example-questions">
                <div class="example-title">
                    <span>✨</span> Örnek Sorular:
                </div>
                <div class="example-chips">
                    <div class="example-chip" onclick="document.querySelector('input[aria-label=\\"\\"]').value = '10-15 Ağustos arası oda müsaitliği'; document.querySelector('button[kind=\\"formSubmit\\"]').click();">📅 10-15 Ağustos arası oda müsaitliği</div>
                    <div class="example-chip" onclick="document.querySelector('input[aria-label=\\"\\"]').value = '2 kişilik oda fiyatları nedir?'; document.querySelector('button[kind=\\"formSubmit\\"]').click();">💰 2 kişilik oda fiyatları nedir?</div>
                    <div class="example-chip" onclick="document.querySelector('input[aria-label=\\"\\"]').value = 'Rezervasyonumu iptal etmek istiyorum'; document.querySelector('button[kind=\\"formSubmit\\"]').click();">❌ Rezervasyonumu iptal etmek istiyorum</div>
                    <div class="example-chip" onclick="document.querySelector('input[aria-label=\\"\\"]').value = 'Otelin özellikleri nelerdir?'; document.querySelector('button[kind=\\"formSubmit\\"]').click();">🏨 Otelin özellikleri nelerdir?</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    return user_message

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
    <style>
        /* Header Stilleri */
        .hotel-header {
            background: linear-gradient(135deg, #1A237E, #283593, #3949AB);
            border-radius: 12px;
            padding: 2rem;
            color: white;
            text-align: center;
            margin-bottom: 2rem;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
            position: relative;
            overflow: hidden;
        }
        
        .hotel-header::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: url('https://images.unsplash.com/photo-1566073771259-6a8506099945?q=80&w=1740') center center;
            background-size: cover;
            opacity: 0.15;
            z-index: 0;
        }
        
        .header-content {
            position: relative;
            z-index: 1;
        }
        
        .hotel-logo {
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 1.2rem;
        }
        
        .hotel-name {
            font-size: 2.8rem;
            font-weight: 700;
            margin: 0;
            text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
            background: linear-gradient(90deg, #E3F2FD, #FFFFFF, #E3F2FD);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: shimmer 2s infinite;
        }
        
        .hotel-icon {
            font-size: 3.2rem;
            margin-right: 15px;
            filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3));
        }
        
        .hotel-subtitle {
            font-size: 1.6rem;
            font-weight: 500;
            margin-top: 0.6rem;
            margin-bottom: 1.5rem;
            color: rgba(255, 255, 255, 0.95);
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
        }
        
        .hotel-desc {
            font-size: 1.1rem;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            color: rgba(255, 255, 255, 0.9);
        }
        
        .feature-pills {
            display: flex;
            justify-content: center;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 1.5rem;
        }
        
        .feature-pill {
            background-color: rgba(255, 255, 255, 0.15);
            border-radius: 20px;
            padding: 6px 12px;
            font-size: 0.85rem;
            backdrop-filter: blur(5px);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        @keyframes shimmer {
            0% { background-position: -100% 0; }
            100% { background-position: 200% 0; }
        }
    </style>
    <div class="hotel-header">
        <div class="header-content">
            <div class="hotel-logo">
                <span class="hotel-icon">🏨</span>
                <h1 class="hotel-name">ALTIKULAÇ OTEL</h1>
            </div>
            <h2 class="hotel-subtitle">Rezervasyon Asistanı</h2>
            <p class="hotel-desc">
                Altıkulaç Otel'e hoş geldiniz! Oda rezervasyonu yapmak, mevcut rezervasyonunuzu yönetmek 
                veya otelimiz hakkında sorularınız için benimle sohbet edebilirsiniz.
            </p>
            <div class="feature-pills">
                <div class="feature-pill">✨ 5 Yıldızlı Konfor</div>
                <div class="feature-pill">🍽️ Şef Restoranı</div>
                <div class="feature-pill">🏊 Açık Havuz</div>
                <div class="feature-pill">🧖 Spa & Wellness</div>
                <div class="feature-pill">🚗 Ücretsiz Otopark</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_conversation(conversation):
    # CSS stillerini ekle - baloncuklar ve yazı stilleri
    st.markdown("""
    <style>
        /* Baloncuk Stilleri */
        .chat-bubble-user {
            background-color: #0D47A1;
            color: white;
            border-radius: 18px 18px 0 18px;
            padding: 15px;
            margin: 10px 0;
            max-width: 80%;
            float: right;
            clear: both;
            box-shadow: 0 3px 8px rgba(0,0,0,0.2);
            border: 1px solid rgba(255,255,255,0.1);
        }
        
        .chat-bubble-assistant {
            background-color: #212121;
            color: white;
            border-radius: 18px 18px 18px 0;
            padding: 15px;
            margin: 10px 0;
            max-width: 80%;
            float: left;
            clear: both;
            box-shadow: 0 3px 8px rgba(0,0,0,0.2);
            border: 1px solid rgba(255,255,255,0.1);
        }
        
        .chat-header {
            font-weight: 600;
            margin-bottom: 8px;
            font-size: 0.9rem;
        }
        
        .chat-message-container {
            overflow: auto;
            margin-bottom: 20px;
            width: 100%;
        }
        
        .message-text {
            color: white;
            white-space: pre-wrap;
            line-height: 1.5;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Eğer sohbet boşsa, hoş geldin mesajını göster
    if not conversation:
        st.markdown("""
        <div style="display: flex; margin: 2rem 0; justify-content: center;">
            <div style="background-color: rgba(30, 136, 229, 0.08); border-radius: 20px; padding: 1.8rem; text-align: center; max-width: 80%; border: 1px dashed #1E88E5; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
                <div style="font-size: 3rem; margin-bottom: 1rem; color: #1E88E5;">👋</div>
                <div style="font-weight: 600; font-size: 1.3rem; margin-bottom: 0.8rem; color: #1E88E5;">Merhaba, ALTIKULAÇ Otel'e Hoş Geldiniz!</div>
                <div style="color: #555; line-height: 1.6; font-size: 1.05rem;">
                    Rezervasyon yapmak, mevcut rezervasyonunuzu kontrol etmek veya bilgi almak için sorularınızı aşağıdaki mesaj kutusuna yazabilirsiniz.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        return
    
    # Mesajları içeren div oluştur
    st.markdown('<div class="chat-message-container">', unsafe_allow_html=True)
    
    # Her mesajı render et
    for role, message in conversation:
        if role == "user":
            st.markdown(f"""
                <div class="chat-bubble-user">
                    <div class="chat-header">👤 Siz</div>
                    <div class="message-text">{message}</div>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
                <div class="chat-bubble-assistant">
                    <div class="chat-header">🏨 Otel Asistanı</div>
                    <div class="message-text">{message}</div>
                </div>
            """, unsafe_allow_html=True)
    
    # Mesaj konteynerini kapat
    st.markdown('</div>', unsafe_allow_html=True)

def render_sidebar_state(state):
    if hasattr(state, "keys"):
        st.sidebar.markdown("### 🔍 State Bilgileri (Debug)")
        st.sidebar.write("State içeriği (session_state):", state)
        create_state_display(state)
