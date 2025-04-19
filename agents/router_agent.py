"""
Router Ajanı
-----------
Rezervasyon istek tipini belirler ve ilgili düğüme yönlendirme yapar.
Sadece yönlendirme sorumluluğu vardır, veri hazırlama işlemi yapmaz.
"""

import json
import logging
from typing import Dict, Any, Optional
import re

from agents.agents import Agent
from langchain_core.messages import HumanMessage, AIMessage
from utils.utils import get_current_utc_datetime, check_for_content

# Logger ayarları
logger = logging.getLogger(__name__)

class RouterAgent(Agent):
    """
    Router Ajanı.
    Kullanıcının isteğini analiz eder ve uygun düğüme yönlendirir.
    """
    async def invoke(self, research_question, conversation_state=None, reservation_response=None):
        """
        Router ajanını çağırır
        
        Args:
            research_question: Kullanıcı sorusu/isteği
            conversation_state: Konuşma durumu
            reservation_response: Rezervasyon ajanının yanıtı
            
        Returns:
            Güncellenmiş durum
        """
        logger.info(f"RouterAgent invoked with question: {research_question}")
        print(f"DEBUG: RouterAgent çağrıldı. Soru: {research_question}")
        
        # Varsayılan hedef düğüm
        target_node = "end"
        
        # Rezervasyon yanıtını al
        response_list = reservation_response() if callable(reservation_response) else reservation_response
        if not response_list:
            logger.info("Rezervasyon yanıtı boş, 'end' düğümüne gidiliyor.")
            print("DEBUG: Rezervasyon yanıtı boş, 'end' düğümüne gidiliyor.")
            self.state["router_output"] = target_node
            return self.state
            
        # Son yanıtı al
        latest_response = response_list[-1]
        
        # Yanıt içeriğini al
        if hasattr(latest_response, 'content'):
            content = latest_response.content
        else:
            content = str(latest_response)
            
        print(f"DEBUG: Rezervasyon yanıtı içeriği: {content}")
        
        try:
            # JSON olarak ayrıştır
            data = json.loads(content)
            print(f"DEBUG: JSON ayrıştırma başarılı: {data}")
            
            # action_type ve tool_action parametrelerini al
            action_type = data.get("action_type", "")
            tool_action = data.get("tool_action", None)
            
            # Eğer action_type null veya boş ise, doğrudan end'e yönlendir (teşekkür, sohbet vb. yanıtlar için)
            if action_type is None or action_type == "null" or action_type == "":
                logger.info("action_type null veya boş, end düğümüne yönlendiriliyor (teşekkür/genel sohbet yanıtı)")
                print("DEBUG: action_type null veya boş, end düğümüne yönlendiriliyor (teşekkür/genel sohbet yanıtı)")
                target_node = "end"
                self.state["router_output"] = target_node
                return self.state
            
            print(f"DEBUG: Tespit edilen action_type: {action_type}")
            print(f"DEBUG: Tespit edilen tool_action: {tool_action}")
            
            if action_type == "list_reservations":
                print("DEBUG: list_reservations işlemi tespit edildi.")
                
                # Eğer tool_action belirtilmişse, doğrudan o düğüme yönlendir
                if tool_action is not None and tool_action != "null":
                    print(f"DEBUG: Doğrudan tool_action yönlendirmesi: {tool_action}")
                    
                    # Eğer "fetch_reservations_tool" ise doğrudan yönlendir
                    if "fetch_reservations" in tool_action or "list_reservations" in tool_action:
                        target_node = "fetch_reservations_tool"
                        print(f"DEBUG: fetch_reservations_tool'a yönlendiriliyor")
                        
                        # reservation_query değerini hazırla - JSON olarak hazırla
                        customer_name = data.get("customer_name", "")
                        query_data = {"customer_name": customer_name}
                        self.state["reservation_query"] = json.dumps(query_data)
                        print(f"DEBUG: reservation_query değeri ayarlandı: {json.dumps(query_data)}")
                else:
                    print("DEBUG: Tool action belirtilmemiş, kullanıcı bilgi sorgusu yapıyor.")
                    
                    # Kullanıcı bilgilerini al ve rezervasyon_query'yi ayarla
                    customer_name = data.get("customer_name", "")
                    
                    if customer_name:
                        print(f"DEBUG: Müşteri adı bulundu: {customer_name}")
                        query_data = {"customer_name": customer_name}
                        self.state["reservation_query"] = json.dumps(query_data)
                        target_node = "fetch_reservations_tool"
                        print(f"DEBUG: Müşteri adı var, fetch_reservations_tool'a yönlendiriliyor.")
                    else:
                        print("DEBUG: Müşteri adı yok, end düğümüne yönlendiriliyor.")
                        target_node = "end"
            
            elif action_type == "create_reservation":
                print("DEBUG: create_reservation işlemi tespit edildi.")
                
                # Eğer tool_action belirtilmişse, doğrudan o düğüme yönlendir
                if tool_action is not None and tool_action != "null":
                    print(f"DEBUG: Doğrudan tool_action yönlendirmesi: {tool_action}")
                    
                    if "add_reservation_advanced_tool" in tool_action:
                        target_node = "add_reservation_tool"
                        print(f"DEBUG: add_reservation_tool'a yönlendiriliyor")
                        
                        # Rezervasyon verilerini hazırla
                        reservation_data = {
                            "customer_name": data.get("customer_name", ""),
                            "check_in_date": data.get("check_in_date", ""),
                            "check_out_date": data.get("check_out_date", ""),
                            "room_type": data.get("room_type", ""),
                            "adults": data.get("adults", 2),
                            "children": data.get("children", 0)
                        }
                        self.state["new_reservation"] = json.dumps(reservation_data)
                        print(f"DEBUG: new_reservation değeri ayarlandı: {json.dumps(reservation_data)}")
                else:
                    print("DEBUG: Tool action belirtilmemiş, end düğümüne yönlendiriliyor.")
                    target_node = "end"
            
            else:
                if tool_action is not None and tool_action != "null":
                    logger.info(f"Tespit edilen tool_action: {tool_action}")
                    print(f"DEBUG: Tespit edilen tool_action: {tool_action}")
                    
                    # Araç çağrısına göre yönlendir (sadece yönlendirme yapıyor)
                    if "fetch_reservations" in tool_action or "list_reservations" in tool_action:
                        logger.info("fetch_reservations_tool'a yönlendiriliyor")
                        print("DEBUG: fetch_reservations_tool'a yönlendiriliyor")
                        target_node = "fetch_reservations_tool"
                        
                    elif "add_reservation_advanced_tool" in tool_action:
                        logger.info("add_reservation_tool'a yönlendiriliyor")
                        print("DEBUG: add_reservation_tool'a yönlendiriliyor")
                        target_node = "add_reservation_tool"
                    
                    elif "update_reservation" in tool_action or "modify_reservation" in tool_action:
                        logger.info("update_reservation_tool'a yönlendiriliyor")
                        print("DEBUG: update_reservation_tool'a yönlendiriliyor")
                        target_node = "update_reservation_tool"
                        
                    elif "delete_reservation" in tool_action or "cancel_reservation" in tool_action:
                        logger.info("delete_reservation_tool'a yönlendiriliyor")
                        print("DEBUG: delete_reservation_tool'a yönlendiriliyor")
                        target_node = "delete_reservation_tool"
                        
                    elif "check_availability" in tool_action or "availability" in tool_action:
                        logger.info("check_availability_tool'a yönlendiriliyor")
                        print("DEBUG: check_availability_tool'a yönlendiriliyor")
                        target_node = "check_availability_tool"
                        
                    else:
                        logger.info(f"Bilinmeyen tool_action: {tool_action}, 'end' düğümüne gidiliyor")
                        print(f"DEBUG: Bilinmeyen tool_action: {tool_action}, 'end' düğümüne gidiliyor")
                        target_node = "end"
                    
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse hatası: {str(e)}, varsayılan olarak 'end' kullanılıyor.")
            print(f"DEBUG: JSON parse hatası: {str(e)}, varsayılan olarak 'end' kullanılıyor.")
            target_node = "end"
                
        self.state["router_output"] = target_node
        logger.info(f"RouterAgent yönlendirme kararı: {target_node}")
        print(f"DEBUG: RouterAgent yönlendirme kararı: {target_node}")
        
        return self.state

class DataExtractorAgent(Agent):
    """
    Veri Çıkarıcı Ajan.
    Rezervasyon ajanının yanıtından gerekli verileri çıkarır ve state'e ekler.
    Ayrıca sohbet bağlamını koruyarak önceki niyetlerin kaybolmamasını sağlar.
    """
    async def invoke(self, research_question, conversation_state=None, reservation_response=None):
        """
        Veri çıkarıcı ajanını çağırır
        
        Args:
            research_question: Kullanıcı sorusu/isteği
            conversation_state: Konuşma durumu
            reservation_response: Rezervasyon ajanının yanıtı
            
        Returns:
            Güncellenmiş durum
        """
        logger.info(f"DataExtractorAgent invoked with question: {research_question}")
        
        # Rezervasyon yanıtını al
        response_list = reservation_response() if callable(reservation_response) else reservation_response
        if not response_list:
            logger.info("Rezervasyon yanıtı boş, veri çıkarılamadı.")
            return self.state
            
        # Son yanıtı al
        latest_response = response_list[-1]
        
        # Yanıtı çıkar
        if hasattr(latest_response, 'content'):
            content = latest_response.content
        else:
            content = str(latest_response)

        # State'deki önceki verileri koru
        existing_reservation_query = self._get_existing_state_data("reservation_query")
        existing_customer_name = self._extract_customer_name_from_state()
        
        # JSON güvenli ayrıştırma
        try:
            try:
                # Önce doğrudan JSON olarak ayrıştırmayı dene
                data = json.loads(content)
            except json.JSONDecodeError:
                # JSON olarak çözülemezse, tırnak işaretlerini düzelterek dene
                try:
                    content_fixed = content.replace("'", '"').replace("\\", "")
                    data = json.loads(content_fixed)
                except json.JSONDecodeError:
                    # Son çare olarak eval kullan
                    try:
                        data = eval(content)
                        if not isinstance(data, dict):
                            logger.error(f"Ayrıştırılan veri dict değil: {type(data)}")
                            return self.state
                    except (SyntaxError, NameError, ValueError) as e:
                        logger.error(f"Yanıt içeriği ayrıştırılamadı: {str(e)}")
                        return self.state
            
            # Gerekli verileri çıkar ve state'e ekle
            action_type = data.get("action_type")
            logger.info(f"Tespit edilen action_type: {action_type}")
            
            # Eğer action_type null veya boş ise hiçbir işlem yapma
            if action_type is None or action_type == "null" or action_type == "":
                logger.info("action_type null veya boş, hiçbir veri oluşturulmayacak (teşekkür/genel sohbet yanıtı)")
                return self.state
            
            if action_type == "list_reservations":
                customer_name = data.get("customer_name") or existing_customer_name
                
                if customer_name:
                    query_data = {
                        "customer_name": customer_name
                    }
                    
                    # Eğer önceki sorguda tarih veya başka bilgiler varsa koru
                    if existing_reservation_query:
                        for key, value in existing_reservation_query.items():
                            if key != "customer_name" and value:
                                query_data[key] = value
                    
                    self.state["reservation_query"] = json.dumps(query_data)
                    logger.info(f"Rezervasyon sorgusu oluşturuldu: {json.dumps(query_data)}")
                    
            elif action_type == "create_reservation":
                # Yeni değerleri al veya mevcut değerleri koru
                customer_name = data.get("customer_name") or existing_customer_name
                check_in_date = data.get("check_in_date")
                check_out_date = data.get("check_out_date")
                room_type = data.get("room_type")
                adults = data.get("adults", 2)
                children = data.get("children", 0)
                
                # Eğer yeni bir rezervasyon için müşteri adı varsa
                if customer_name:
                    reservation_data = {
                        "customer_name": customer_name,
                        "check_in_date": check_in_date,
                        "check_out_date": check_out_date,
                        "room_type": room_type,
                        "adults": adults,
                        "children": children
                    }
                    
                    # Eksik verileri önceki state'ten doldur
                    if existing_reservation_query:
                        for key, value in existing_reservation_query.items():
                            if key in reservation_data and not reservation_data[key] and value:
                                reservation_data[key] = value
                    
                    self.state["new_reservation"] = json.dumps(reservation_data)
                    logger.info(f"Yeni rezervasyon verisi oluşturuldu: {json.dumps(reservation_data)}")
                
                # Eğer müşteri sadece rezervasyonlarını görmek istiyorsa
                if customer_name and not (check_in_date and check_out_date and room_type):
                    # Önceki sorgudan bir müşteri adı elde edildiyse, listelemek için kullan
                    query_data = {"customer_name": customer_name}
                    
                    # State'e yaz ve list_reservations yapmak için hazırla
                    self.state["reservation_query"] = json.dumps(query_data)
                    logger.info(f"Müşteri adına göre rezervasyon sorgusu: {json.dumps(query_data)}")
            
            elif action_type == "update_reservation":
                # İlgili güncelleme işlemleri...
                # (Buradaki kodu koruyorum, değişiklik yapmıyorum)
                reservation_id = data.get("reservation_id")
                if reservation_id:
                    update_data = {
                        "reservation_id": reservation_id
                    }
                    
                    # Müşteri adı
                    customer_name = data.get("customer_name") or existing_customer_name
                    if customer_name:
                        update_data["customer_name"] = customer_name
                        
                    # Diğer güncellenebilir alanlar
                    for field in ["check_in_date", "check_out_date", "room_type", "adults", "children"]:
                        if data.get(field) is not None:
                            update_data[field] = data.get(field)
                            
                    self.state["update_reservation"] = json.dumps(update_data)
            
            elif action_type == "delete_reservation":
                # İlgili silme işlemleri...
                customer_name = data.get("customer_name") or existing_customer_name
                room_type = data.get("room_type")
                
                # Daha detaylı log
                logger.info(f"Silme işlemi için veri hazırlanıyor, İsim:{customer_name}, Oda:{room_type}")
                
                # Silme verisi için yeni bir sözlük oluştur
                delete_data = {}
                
                # Öncelikle reservation_id varsa ekle (ID ile silme öncelikli)
                reservation_id = data.get("reservation_id")
                if reservation_id:
                    delete_data["reservation_id"] = reservation_id
                
                # Opsiyonel alanları ekle - bazı API'ler için gerekli olabilir
                if customer_name:
                    delete_data["customer_name"] = customer_name
                
                if room_type:
                    delete_data["room_type"] = room_type
                
                # Eğer en az bir veri eklendiyse (ya ID ya da isim)
                if delete_data:
                    # Hazırlanan veriyi JSON olarak state'e ekle
                    json_data = json.dumps(delete_data)
                    self.state["delete_reservation"] = json_data  # JSON string olarak kaydet
                    logger.info(f"Silme verisi oluşturuldu (JSON string): {json_data}")
                else:
                    logger.warning("Silme işlemi için hiçbir tanımlayıcı bilgi bulunamadı (ne ID ne de isim)!")
                    # Genel bir hata mesajı ekle
                    error_data = {"error": "Silme için yeterli bilgi yok"}
                    self.state["delete_reservation"] = json.dumps(error_data)
                    logger.info(f"Hata verisi oluşturuldu: {json.dumps(error_data)}")
            
            # Önceki action_type değeri varsa ve yeni değer yoksa, önceki değeri koru
            elif not action_type and existing_reservation_query and "customer_name" in existing_reservation_query:
                customer_name = data.get("customer_name") or existing_customer_name
                if customer_name:
                    # Önceki müşteri adından farklı bir ad söylendiyse güncelle
                    query_data = dict(existing_reservation_query)
                    query_data["customer_name"] = customer_name
                    self.state["reservation_query"] = json.dumps(query_data)
                    logger.info(f"Önceki sorgu güncellendi: {json.dumps(query_data)}")
            
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse hatası: {str(e)}, veri çıkarılamadı.")
        
        return self.state
    
    def _get_existing_state_data(self, key):
        """State'den veri alıp JSON olarak decode eder"""
        if key in self.state and self.state[key]:
            try:
                return json.loads(self.state[key])
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}
        
    def _extract_customer_name_from_state(self):
        """State içindeki farklı alanlardaki müşteri adını bulur"""
        customer_name = None
        
        # reservation_query içinde müşteri adı kontrolü
        query_data = self._get_existing_state_data("reservation_query")
        if query_data and "customer_name" in query_data:
            customer_name = query_data["customer_name"]
            
        # new_reservation içinde müşteri adı kontrolü
        if not customer_name:
            new_res_data = self._get_existing_state_data("new_reservation")
            if new_res_data and "customer_name" in new_res_data:
                customer_name = new_res_data["customer_name"]
        
        # update_reservation içinde müşteri adı kontrolü  
        if not customer_name:
            update_data = self._get_existing_state_data("update_reservation")
            if update_data and "customer_name" in update_data:
                customer_name = update_data["customer_name"]
                
        return customer_name 