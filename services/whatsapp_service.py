"""
WhatsApp Business API Servisi
----------------------------
WhatsApp Cloud API ile iletişim kurmak için gerekli fonksiyonlar.
"""

import os
import json
import logging
import requests
from typing import Dict, Any, Optional, List

# Logger ayarları
logger = logging.getLogger(__name__)

def send_message(recipient_id: str, message_text: str) -> Dict[str, Any]:
    """
    WhatsApp API üzerinden metin mesajı gönderir
    
    Args:
        recipient_id: Alıcı WhatsApp ID'si
        message_text: Gönderilecek mesaj metni
        
    Returns:
        Dict[str, Any]: API yanıtı
    """
    # Çevre değişkenlerinden WhatsApp API bilgilerini al
    token = os.getenv("WHATSAPP_TOKEN")
    phone_id = os.getenv("WHATSAPP_PHONE_ID")
    
    if not token or not phone_id:
        error_msg = "WhatsApp API için gerekli çevre değişkenleri tanımlanmamış"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # API endpoint
    url = f"https://graph.facebook.com/v17.0/{phone_id}/messages"
    
    # Mesaj içeriği
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_id,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": message_text
        }
    }
    
    # HTTP başlıkları
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    try:
        # POST isteği gönder
        response = requests.post(url, headers=headers, json=payload)
        
        # Yanıt durumunu kontrol et
        if response.status_code == 200:
            logger.info(f"Mesaj başarıyla gönderildi: {recipient_id}")
            return response.json()
        else:
            logger.error(f"Mesaj gönderme hatası: {response.status_code} - {response.text}")
            return {
                "error": True,
                "status_code": response.status_code,
                "message": response.text
            }
    
    except Exception as e:
        logger.error(f"WhatsApp API isteği sırasında hata: {str(e)}")
        return {
            "error": True,
            "message": str(e)
        }

def send_template_message(
    recipient_id: str, 
    template_name: str,
    language_code: str = "tr",
    components: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    WhatsApp API üzerinden şablon mesajı gönderir
    
    Args:
        recipient_id: Alıcı WhatsApp ID'si
        template_name: Şablon adı
        language_code: Dil kodu (varsayılan: tr)
        components: Şablon bileşenleri
        
    Returns:
        Dict[str, Any]: API yanıtı
    """
    # Çevre değişkenlerinden WhatsApp API bilgilerini al
    token = os.getenv("WHATSAPP_TOKEN")
    phone_id = os.getenv("WHATSAPP_PHONE_ID")
    
    if not token or not phone_id:
        error_msg = "WhatsApp API için gerekli çevre değişkenleri tanımlanmamış"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # API endpoint
    url = f"https://graph.facebook.com/v17.0/{phone_id}/messages"
    
    # Mesaj içeriği
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_id,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {
                "code": language_code
            }
        }
    }
    
    # Bileşenler varsa ekle
    if components:
        payload["template"]["components"] = components
    
    # HTTP başlıkları
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    try:
        # POST isteği gönder
        response = requests.post(url, headers=headers, json=payload)
        
        # Yanıt durumunu kontrol et
        if response.status_code == 200:
            logger.info(f"Şablon mesajı başarıyla gönderildi: {recipient_id}")
            return response.json()
        else:
            logger.error(f"Şablon mesajı gönderme hatası: {response.status_code} - {response.text}")
            return {
                "error": True,
                "status_code": response.status_code,
                "message": response.text
            }
    
    except Exception as e:
        logger.error(f"WhatsApp API şablon isteği sırasında hata: {str(e)}")
        return {
            "error": True,
            "message": str(e)
        }

def get_whatsapp_templates() -> Dict[str, Any]:
    """
    WhatsApp hesabına ait şablonları getirir
    
    Returns:
        Dict[str, Any]: Şablonların listesi
    """
    # Çevre değişkenlerinden WhatsApp API bilgilerini al
    token = os.getenv("WHATSAPP_TOKEN")
    phone_id = os.getenv("WHATSAPP_PHONE_ID")
    
    if not token or not phone_id:
        error_msg = "WhatsApp API için gerekli çevre değişkenleri tanımlanmamış"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # API endpoint
    url = f"https://graph.facebook.com/v17.0/{phone_id}/message_templates"
    
    # HTTP başlıkları
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    try:
        # GET isteği gönder
        response = requests.get(url, headers=headers)
        
        # Yanıt durumunu kontrol et
        if response.status_code == 200:
            logger.info("Şablonlar başarıyla alındı")
            return response.json()
        else:
            logger.error(f"Şablonları alma hatası: {response.status_code} - {response.text}")
            return {
                "error": True,
                "status_code": response.status_code,
                "message": response.text
            }
    
    except Exception as e:
        logger.error(f"WhatsApp API şablon listesi alma sırasında hata: {str(e)}")
        return {
            "error": True,
            "message": str(e)
        } 