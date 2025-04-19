"""
Tool Ajanları
------------
Rezervasyon sistemi için özel araç ajanları.
Her araç kendi state'ini yönetir ve güncelleyebilir.
"""

import json
import logging
from typing import Dict, Any, Optional

from agents.agents import Agent
from services.sheets_service import (

    get_all_reservations,
    add_reservation,
    update_reservation,
    delete_reservation,
    check_availability,
    get_reservations_by_name
)
from states.state import AgentGraphState
from langchain_core.messages import HumanMessage

# Logger ayarları
logger = logging.getLogger(__name__)

# Varsayılan spreadsheet ve worksheet değerleri
DEFAULT_SPREADSHEET = "REZERVASYON"
DEFAULT_WORKSHEET = "Rezervasyonlar"

class FetchReservationsAgent(Agent):
    """
    Rezervasyonları getiren ajan.
    Müşteri adına göre rezervasyonları Google Sheets'ten getirir.
    """
    def invoke(self, research_question, conversation_state=None, customer_data=None):
        """
        Rezervasyonları getirir ve filtreler.
        
        Args:
            research_question: Araştırma sorusu
            conversation_state: Konuşma durumu
            customer_data: Müşteri bilgileri (JSON string)
        
        Returns:
            Güncellenmiş durum
        """
        logger.info(f"FetchReservationsAgent invoked with data: {customer_data()}")
        
        try:
            # Parametre bilgilerini al
            params_data = customer_data() if callable(customer_data) else customer_data
            
            # JSON parametrelerini ayrıştır
            customer_name = None
            spreadsheet_name = DEFAULT_SPREADSHEET
            worksheet_name = DEFAULT_WORKSHEET
            room_type = None
            limit = 10  # Varsayılan olarak en fazla 10 kayıt getir
            exact_match = True  # Varsayılan olarak tam eşleşme arar
            sort_by_date = False  # Tarihe göre sıralama
            if params_data:
                try:
                    params_json = json.loads(params_data[0].content)
                    customer_name = params_json.get("customer_name")
                    spreadsheet_name = params_json.get("spreadsheet_name", DEFAULT_SPREADSHEET)
                    worksheet_name = params_json.get("worksheet_name", DEFAULT_WORKSHEET)
                    room_type = params_json.get("room_type")
                    
                    # Yeni parametreler
                    limit = int(params_json.get("limit", 10))  # Sayısal değere dönüştür
                    exact_match = params_json.get("exact_match", True)  # Tam eşleşme veya içerme
                    sort_by_date = params_json.get("sort_by_date", False)  # Tarihe göre sıralama
                    
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"JSON ayrıştırma hatası: {str(e)}")
            
            # Rezervasyonları getir
            reservations = []
            print(customer_name,'-------------')
            if customer_name:
                logger.info(f"Müşteri adına göre filtreleniyor: {customer_name}, Tam Eşleşme: {exact_match}")
                # Yeni get_reservations_by_name fonksiyonunu kullan - parametreleriyle
                reservations = get_reservations_by_name(
                    spreadsheet_name, 
                    customer_name, 
                    exact_match=exact_match,  # Tam eşleşme veya içerme kontrolü
                    worksheet_name=worksheet_name,
                    room_type=room_type
                )
                logger.info(f"İsme göre filtrelendi: {len(reservations)} sonuç")
            else:
                # Müşteri adı belirtilmemişse, tüm kayıtları getir ve sonra sınırla
                logger.info(f"Tüm rezervasyonlar getiriliyor (en fazla {limit} kayıt)")
                all_reservations = get_all_reservations(spreadsheet_name, worksheet_name)
                
                # Room type filtresi aktifse uygula
                if room_type:
                    logger.info(f"Oda tipine göre filtreleniyor: {room_type}")
                    all_reservations = [r for r in all_reservations if r.get('room_type', '').lower() == room_type.lower()]
                
                # Belirtilen limite göre sınırla
                reservations = all_reservations[:limit]
                logger.info(f"Toplam {len(all_reservations)} kayıttan {len(reservations)} kayıt alındı")
            
            # Tarihe göre sıralama
            if sort_by_date and reservations:
                try:
                    logger.info("Rezervasyonlar giriş tarihine göre sıralanıyor")
                    # Giriş tarihine göre sırala (yeniden eskiye)
                    reservations = sorted(
                        reservations, 
                        key=lambda x: x.get('check_in_date', '0000-00-00'),
                        reverse=True
                    )
                except Exception as sort_error:
                    logger.warning(f"Tarihe göre sıralama hatası: {str(sort_error)}")
            
            # Sonucu hazırla
            if reservations:
                formatted_reservations = []
                for res in reservations:
                    # Her bir rezervasyonu biçimlendir
                    formatted = {
                        'id': res.get('reservation_id', 'N/A'),
                        'name': res.get('customer_name', 'N/A'),
                        'check_in': res.get('check_in_date', 'N/A'),
                        'check_out': res.get('check_out_date', 'N/A'),
                        'adults': res.get('adults', '0'),
                        'children': res.get('children', '0'),
                        'room_type': res.get('room_type', 'N/A'),
                        'price': res.get('price', '0'),
                        'status': res.get('status', 'N/A'),
                        'created_at': res.get('created_at', 'N/A')
                    }
                    formatted_reservations.append(formatted)
                
                result = {
                    "success": True,
                    "count": len(reservations),
                    "total_available": len(reservations),  # Toplam kayıt sayısı
                    "limit": limit,  # Uygulanan limit
                    "filter": {
                        "customer_name": customer_name,
                        "room_type": room_type,
                        "exact_match": exact_match
                    },
                    "reservations": formatted_reservations
                }
            else:
                result = {
                    "success": True,
                    "count": 0,
                    "filter": {
                        "customer_name": customer_name,
                        "room_type": room_type,
                        "exact_match": exact_match
                    },
                    "message": "Hiç rezervasyon bulunamadı."
                }
            
            # Durumu güncelle
            self.state["reservations_result"] = self.state.get("reservations_result", []) + [
                HumanMessage(role="system", content=str(result))
            ]
            logger.info(f"Fetch reservations completed with {len(reservations)} results")
            return self.state
            
        except Exception as e:
            logger.error(f"Rezervasyonlar alınırken hata: {str(e)}")
            
            # Hata durumu
            result = {
                "success": False,
                "error": str(e),
                "message": "Rezervasyonları getirirken bir hata oluştu."
            }
      
            self.state["reservations_result"] = self.state.get("reservations_result", []) + [
                HumanMessage(role="system", content=str(result))
            ]
            
            return self.state

class AddReservationAgent(Agent):
    """
    Rezervasyon ekleyen ajan.
    Yeni rezervasyonu Google Sheets'e ekler.
    """
    def invoke(self, research_question, conversation_state=None, reservation_data=None):
        """
        Yeni rezervasyon ekler.
        
        Args:
            research_question: Araştırma sorusu
            conversation_state: Konuşma durumu
            reservation_data: Rezervasyon verileri (JSON string)
            
        Returns:
            Güncellenmiş durum
        """
        logger.info(f"AddReservationAgent invoked with data: {reservation_data}")
     
        try:
            # Parametre bilgilerini al
            params_data = reservation_data() if callable(reservation_data) else reservation_data
            print('PARAMS_DATA',params_data)
            # JSON parametrelerini ayrıştır
            param_json_data = None
            
            if isinstance(params_data, list) and len(params_data) > 0:
                # Mesaj listesinden veriyi çıkarırken, sondan başa doğru işle (en yeni mesajı bul)
                if len(params_data) > 1:
                    logger.info(f"Birden fazla mesaj tespit edildi ({len(params_data)}), en yeni veriyi kullanıyorum")
                    
                    # Sondan başa doğru geçerli veriyi ara
                    for item in reversed(params_data):
                        if isinstance(item, str):
                            try:
                                potential_data = json.loads(item)
                                # Geçerli veri bulundu
                                param_json_data = potential_data
                                logger.info(f"Tersine sıralamada geçerli JSON veri bulundu: {param_json_data}")
                                break
                            except json.JSONDecodeError:
                                continue
                        elif isinstance(item, HumanMessage):  # HumanMessage tipini kontrol et
                            try:
                                # HumanMessage nesnesinin içeriğini al
                                message_content = item.content
                                potential_data = json.loads(message_content)
                                # Geçerli veri bulundu
                                param_json_data = potential_data
                                logger.info(f"Tersine sıralamada geçerli HumanMessage içeriği bulundu: {message_content}")
                                break
                            except json.JSONDecodeError:
                                continue
                    
                    # Geçerli veri bulunamadıysa, klasik yöntemi dene
                    if param_json_data is None:
                        logger.warning("Tersine taramada geçerli veri bulunamadı, klasik yönteme dönülüyor")
                
                # En yeni veri bulunamadıysa veya tekil mesaj varsa, geleneksel işleme yapılır
                if param_json_data is None:
                    if isinstance(params_data[0], str):
                        try:
                            param_json_data = json.loads(params_data[0])
                            logger.info(f"İlk string mesaj içeriği: {param_json_data}")
                        except json.JSONDecodeError:
                            param_json_data = {"raw_data": params_data[0]}
                    elif isinstance(params_data[0], HumanMessage):  # HumanMessage tipini kontrol et
                        try:
                            # HumanMessage nesnesinin içeriğini al
                            message_content = params_data[0].content
                            logger.info(f"HumanMessage içeriği: {message_content}")
                            param_json_data = json.loads(message_content)
                        except json.JSONDecodeError:
                            param_json_data = {"raw_data": message_content}
                    else:
                        param_json_data = params_data[0]
            elif isinstance(params_data, str):
                try:
                    param_json_data = json.loads(params_data)
                except json.JSONDecodeError:
                    param_json_data = {"raw_data": params_data}
            elif isinstance(params_data, dict):
                param_json_data = params_data
            
            # Eğer hala param_json_data None ise, hata döndür
            if param_json_data is None:
                result = {
                    "success": False,
                    "error": "Geçersiz parametre formatı",
                    "message": "Rezervasyon bilgileri JSON formatında gönderilmelidir."
                }
            else:
                # Gerekli alanları kontrol et
                required_fields = ['customer_name', 'check_in_date', 'check_out_date', 'room_type']
                missing_fields = [field for field in required_fields if field not in param_json_data]
                
                if missing_fields:
                    result = {
                        "success": False,
                        "error": f"Eksik alanlar: {', '.join(missing_fields)}",
                        "message": "Gerekli tüm rezervasyon bilgilerini giriniz."
                    }
                else:
                    # Rezervasyon verileri
                    reservation_data = {
                        'customer_name': param_json_data.get('customer_name'),
                        'check_in_date': param_json_data.get('check_in_date'),
                        'check_out_date': param_json_data.get('check_out_date'),
                        'adults': param_json_data.get('adults', 2),
                        'children': param_json_data.get('children', 0),
                        'room_type': param_json_data.get('room_type'),
                        'price': param_json_data.get('price', 0),
                        'status': param_json_data.get('status', 'Confirmed')
                    }
                    
                
                    # Spreadsheet bilgileri
                    spreadsheet_name = param_json_data.get('spreadsheet_name', DEFAULT_SPREADSHEET)
                    worksheet_name = param_json_data.get('worksheet_name', DEFAULT_WORKSHEET)
                    
                    # Rezervasyonu ekle
                    success = add_reservation(spreadsheet_name, reservation_data, worksheet_name)
                    
                    if success:
                        result = {
                            "success": True,
                            "message": "Rezervasyon başarıyla eklendi.",
                            "reservation": reservation_data
                        }
                    else:
                        result = {
                            "success": False,
                            "error": "Rezervasyon eklenirken bir hata oluştu.",
                            "message": "Lütfen daha sonra tekrar deneyin."
                        }
            
            # Durumu güncelle
            self.state["add_reservation_result"] = self.state.get("add_reservation_result", []) + [
                HumanMessage(role="system", content=str(result))
            ]
            
            # Başarılı işlem sonrası state'i temizle (önceki mesajları temizle)
            if result.get("success", False):
                logger.info("Başarılı ekleme işlemi sonrası state temizleniyor...")
                
                # new_reservation anahtarını temizle
                if "new_reservation" in self.state:
                    del self.state["new_reservation"]
                    logger.info("new_reservation alanı state'ten temizlendi")
                    
                # Son başarılı sonucu tut, diğerlerini temizle
                if "add_reservation_result" in self.state and len(self.state["add_reservation_result"]) > 0:
                    last_result = self.state["add_reservation_result"][-1]
                    self.state["add_reservation_result"] = [last_result]
                    logger.info("add_reservation_result alanı temizlendi, sadece son sonuç tutuldu")
            
            logger.info(f"Add reservation completed: {result['success']}")
            return self.state
            
        except Exception as e:
            logger.error(f"Rezervasyon eklenirken hata: {str(e)}")
            
            # Hata durumu
            result = {
                "success": False,
                "error": str(e),
                "message": "Rezervasyon eklenirken bir hata oluştu."
            }
            
            self.state["add_reservation_result"] = self.state.get("add_reservation_result", []) + [
                HumanMessage(role="system", content=str(result))
            ]
            
            return self.state

class UpdateReservationAgent(Agent):
    """
    Rezervasyon güncelleyen ajan.
    Mevcut rezervasyonu Google Sheets'te günceller.
    """
    def invoke(self, research_question, conversation_state=None, update_data=None):
        """
        Mevcut rezervasyonu günceller.
        
        Args:
            research_question: Araştırma sorusu
            conversation_state: Konuşma durumu
            update_data: Güncelleme verileri (JSON string)
            
        Returns:
            Güncellenmiş durum
        """
        logger.info(f"UpdateReservationAgent invoked with data: {update_data}")
        
        try:
            # Parametre bilgilerini al
            params_data = update_data() if callable(update_data) else update_data
            print('UPDATE_PARMAS_DATA',params_data)
            # JSON parametrelerini ayrıştır
            if isinstance(params_data, list):
                logger.info(f"Liste tipinde veri tespit edildi, uzunluk: {len(params_data)}")
                
                # Birden fazla mesaj varsa, sondan başa doğru işle
                if len(params_data) > 1:
                    logger.info("Birden fazla mesaj tespit edildi, en yeni veriyi kullanmaya çalışıyorum")
                    
                    for item in reversed(params_data):
                        if hasattr(item, 'content'):  # HumanMessage nesnesi mi?
                            content = item.content
                            try:
                                if '{' in content:
                                    potential_data = json.loads(content)
                                    # İçeriği geçerli ise ve rezervasyon ID'si varsa kullan
                                    if 'reservation_id' in potential_data:
                                        params_data = content
                                        logger.info(f"En yeni içerik bulundu (ID içeriyor): {content}")
                                        break
                                    # Eğer müşteri adı içeriyorsa potansiyel olarak kullanılabilir
                                    elif 'customer_name' in potential_data:
                                        params_data = content
                                        logger.info(f"En yeni içerik bulundu (müşteri adı içeriyor): {content}")
                                        # ID olmadığı için aramaya devam et, belki daha iyisi bulunur
                            except json.JSONDecodeError:
                                pass
                        elif isinstance(item, str) and '{' in item:
                            try:
                                potential_data = json.loads(item)
                                # İçeriği geçerli ise kullan
                                if 'reservation_id' in potential_data:
                                    params_data = item
                                    logger.info(f"En yeni string içerik bulundu: {item}")
                                    break
                            except json.JSONDecodeError:
                                pass
                
                # Eğer hala liste tipindeyse ve tek eleman kaldıysa onu al
                if isinstance(params_data, list) and len(params_data) > 0:
                    if hasattr(params_data[0], 'content'):  # HumanMessage nesnesi mi?
                        params_data = params_data[0].content
                    else:
                        params_data = params_data[0]  # String veya başka bir tip

            if not isinstance(params_data, str) or '{' not in params_data:
                result = {
                    "success": False,
                    "error": "Geçersiz parametre formatı",
                    "message": "Güncelleme bilgileri JSON formatında gönderilmelidir."
                }
            else:
                try:
                    params_json = json.loads(params_data)
                    
                    # Gerekli alanları kontrol et
                    if 'reservation_id' not in params_json:
                        result = {
                            "success": False,
                            "error": "Rezervasyon ID'si eksik",
                            "message": "Güncellenecek rezervasyonun ID'si belirtilmelidir."
                        }
                    else:
                        # Spreadsheet bilgileri
                        spreadsheet_name = params_json.pop('spreadsheet_name', DEFAULT_SPREADSHEET)
                        worksheet_name = params_json.pop('worksheet_name', DEFAULT_WORKSHEET)
                        
                        # Rezervasyon ID'sini al
                        reservation_id = params_json.pop('reservation_id')
                        
                        # Güncelleme verileri (ID hariç tüm bilgiler)
                        updated_data = params_json
                        
                        # Rezervasyonu güncelle
                        success = update_reservation(spreadsheet_name, reservation_id, updated_data, worksheet_name)
                        
                        if success:
                            result = {
                                "success": True,
                                "message": f"Rezervasyon (ID: {reservation_id}) başarıyla güncellendi.",
                                "updated_fields": list(updated_data.keys())
                            }
                        else:
                            result = {
                                "success": False,
                                "error": "Rezervasyon güncellenirken bir hata oluştu.",
                                "message": "Rezervasyon bulunamadı veya güncellenemedi."
                            }
                except json.JSONDecodeError:
                    result = {
                        "success": False,
                        "error": "Geçersiz JSON formatı",
                        "message": "Güncelleme verileri geçerli bir JSON formatında olmalıdır."
                    }
            
            # Durumu güncelle
            self.state["update_reservation_result"] = self.state.get("update_reservation_result", []) + [
                HumanMessage(role="system", content=str(result))
            ]
            
            # Başarılı işlem sonrası state'i temizle
            if result.get("success", False):
                logger.info("Başarılı güncelleme işlemi sonrası state temizleniyor...")
                
                # update_reservation anahtarını temizle
                if "update_reservation" in self.state:
                    del self.state["update_reservation"]
                    logger.info("update_reservation alanı state'ten temizlendi")
                    
                # Son başarılı sonucu tut, diğerlerini temizle
                if "update_reservation_result" in self.state and len(self.state["update_reservation_result"]) > 0:
                    last_result = self.state["update_reservation_result"][-1]
                    self.state["update_reservation_result"] = [last_result]
                    logger.info("update_reservation_result alanı temizlendi, sadece son sonuç tutuldu")
            
            logger.info(f"Update reservation completed: {result.get('success')}")
            return self.state
            
        except Exception as e:
            logger.error(f"Rezervasyon güncellenirken hata: {str(e)}")
            
            # Hata durumu
            result = {
                "success": False,
                "error": str(e),
                "message": "Rezervasyon güncellenirken bir hata oluştu."
            }
            
            self.state["update_reservation_result"] = self.state.get("update_reservation_result", []) + [
                HumanMessage(role="system", content=str(result))
            ]
            
            return self.state

class DeleteReservationAgent(Agent):
    """
    Rezervasyon silen ajan.
    Mevcut rezervasyonu Google Sheets'ten siler.
    """
    def invoke(self, research_question, conversation_state=None, delete_data=None):
        """
        Rezervasyonu siler.
        
        Args:
            research_question: Araştırma sorusu
            conversation_state: Konuşma durumu
            delete_data: Silme verileri (JSON string)
            
        Returns:
            Güncellenmiş durum
        """
        logger.info(f"DeleteReservationAgent invoked with data: {delete_data}")
        
        try:
            # Parametre bilgilerini al (callable kontrolü, lambda fonksiyonlarını çağırır)
            params_data = delete_data() if callable(delete_data) else delete_data
            logger.info(f"Çözümlenmiş delete_data: {params_data}")
            
            # JSON parametrelerini ayrıştır - birçok farklı format olabilir
            param_json_data = None
            
            # 1. HumanMessage listesi kontrolü
            if isinstance(params_data, list):
                logger.info(f"Liste tipinde veri tespit edildi, uzunluk: {len(params_data)}")
                message_contents = []
                
                # Listedeki tüm mesajları kontrol et
                for item in params_data:
                    if hasattr(item, 'content'):  # HumanMessage veya AIMessage nesnesi
                        message_contents.append(item.content)
                        logger.info(f"Mesaj içeriği alındı: {item.content}")
                    elif isinstance(item, str):
                        message_contents.append(item)
                        logger.info(f"String eleman alındı: {item}")
                    elif isinstance(item, dict):
                        message_contents.append(json.dumps(item))
                        logger.info(f"Dict eleman alındı: {item}")
                
                # En az bir mesaj içeriği varsa, önce SONDAN başlayarak geçerli JSON içeren ilk mesajı bul
                if message_contents:
                    found_valid_json = False
                    
                    # Sondan başa doğru mesajları kontrol et
                    for content in reversed(message_contents):
                        try:
                            # İçeriği JSON olarak ayrıştırmayı dene
                            potential_data = json.loads(content)
                            
                            # Hata içeren mesajları atla
                            if "error" in potential_data:
                                logger.info(f"Hata içeren mesaj atlanıyor: {potential_data}")
                                continue
                                
                            # Müşteri adı veya reservation_id içermeyen mesajları atla
                            if not potential_data.get("customer_name") and not potential_data.get("reservation_id"):
                                logger.info(f"Tanımlayıcı bilgi içermeyen mesaj atlanıyor: {potential_data}")
                                continue
                                
                            # Geçerli veri bulundu
                            param_json_data = potential_data
                            logger.info(f"Geçerli mesaj bulundu (ters sırada): {param_json_data}")
                            found_valid_json = True
                            break
                        except json.JSONDecodeError:
                            continue
                            
                    # Eğer sondan başa doğru taramada bulunamadıysa, klasik yöntemle devam et
                    if not found_valid_json:
                        try:
                            first_content = message_contents[0]
                            # İçeriği JSON olarak ayrıştırmayı dene
                            param_json_data = json.loads(first_content)
                            logger.info(f"İlk mesajın içeriği JSON olarak ayrıştırıldı: {param_json_data}")
                        except json.JSONDecodeError as e:
                            logger.error(f"İlk mesaj içeriği JSON olarak ayrıştırılamadı: {str(e)}")
                            
                            # Tüm mesajları ayrıştırmayı dene (baştan sona)
                            for content in message_contents:
                                try:
                                    content_json = json.loads(content)
                                    param_json_data = content_json
                                    logger.info(f"Alternatif mesaj içeriği başarıyla ayrıştırıldı: {param_json_data}")
                                    break  # İlk başarılı ayrıştırmada döngüden çık
                                except json.JSONDecodeError:
                                    continue  # Sonraki mesaja geç
                                    
                            # Hiçbir mesaj ayrıştırılamadıysa, ham veriyi kullan
                            if param_json_data is None and message_contents:
                                logger.warning("Hiçbir mesaj JSON olarak ayrıştırılamadı, metin olarak kullanılacak")
                                param_json_data = {"raw_data": message_contents[0]}
            
            # 2. String olarak gelen JSON verisi
            elif isinstance(params_data, str):
                try:
                    param_json_data = json.loads(params_data)
                    logger.info(f"String JSON başarıyla ayrıştırıldı: {param_json_data}")
                except json.JSONDecodeError as e:
                    logger.error(f"JSON ayrıştırma hatası: {str(e)}")
                    if '{' in params_data:
                        # JSON içinde olabilecek sorunları düzeltmeye çalış
                        try:
                            # Çift tırnak ile değiştir
                            fixed_json = params_data.replace("'", '"')
                            param_json_data = json.loads(fixed_json)
                            logger.info(f"Düzeltilmiş JSON başarıyla ayrıştırıldı: {param_json_data}")
                        except json.JSONDecodeError:
                            logger.error("JSON düzeltme girişimi başarısız oldu")
                            param_json_data = {"raw_data": params_data}
                    else:
                        # JSON formatında değil, düz metin
                        param_json_data = {"raw_data": params_data}
                        
            # 3. Dictionary olarak gelen veri
            elif isinstance(params_data, dict):
                param_json_data = params_data
                logger.info(f"Dictionary veri doğrudan kullanıldı: {param_json_data}")
            
            # 4. State doğrudan erişimle veri ekstraksiyonu
            if not param_json_data and self.state.get("delete_reservation"):
                try:
                    state_data = self.state.get("delete_reservation")
                    logger.info(f"State'den delete_reservation alınıyor: {state_data}")
                    
                    # State verisi bir liste mi kontrol et
                    if isinstance(state_data, list):
                        # Listedeki ilk elemanın içeriğini almaya çalış
                        if state_data and hasattr(state_data[0], 'content'):
                            content = state_data[0].content
                            logger.info(f"State listesindeki ilk mesajın içeriği: {content}")
                            param_json_data = json.loads(content)
                        else:
                            logger.error("State'deki liste verisi HumanMessage nesneleri içermiyor")
                    else:
                        # Normal string olarak işle
                        param_json_data = json.loads(state_data)
                except (json.JSONDecodeError, TypeError) as e:
                    logger.error(f"State'deki delete_reservation verisi işlenemedi: {str(e)}")
            
            # Eğer hala param_json_data None ise, hata döndür
            if param_json_data is None:
                logger.error("Geçerli bir JSON verisi elde edilemedi")
                result = {
                    "success": False,
                    "error": "Geçersiz parametre formatı",
                    "message": "Silme parametreleri JSON formatında gönderilmelidir."
                }
            else:
                # Spreadsheet bilgileri
                spreadsheet_name = param_json_data.get('spreadsheet_name', DEFAULT_SPREADSHEET)
                worksheet_name = param_json_data.get('worksheet_name', DEFAULT_WORKSHEET)
                
                # Silme için gerekli bilgileri topla
                reservation_id = param_json_data.get('reservation_id')
                customer_name = param_json_data.get('customer_name')
                room_type = param_json_data.get('room_type')
                exact_match = param_json_data.get('exact_match', True)  # Tam eşleşme veya kısmi eşleşme
                
                logger.info(f"Silme parametreleri: ID={reservation_id}, İsim={customer_name}, Oda Tipi={room_type}, Tam Eşleşme={exact_match}")
                
                # Silme için en az bir kriterin olması gerekiyor: ya ID ya da isim
                if not reservation_id and not customer_name:
                    result = {
                        "success": False,
                        "error": "Tanımlayıcı bilgi eksik",
                        "message": "Silme işlemi için en az bir tanımlayıcı (reservation_id veya customer_name) gereklidir."
                    }
                else:
                    try:
                        # Eğer ID varsa, bununla silmeyi dene
                        if reservation_id:
                            logger.info(f"ID kullanarak silme deneniyor: {reservation_id}")
                            success = delete_reservation(spreadsheet_name, reservation_id, worksheet_name)
                            
                            if success:
                                result = {
                                    "success": True,
                                    "message": f"Rezervasyon (ID: {reservation_id}) başarıyla silindi."
                                }
                            else:
                                # ID ile silme başarısız olduysa ve müşteri adı da varsa, müşteri adıyla dene
                                if customer_name:
                                    logger.info(f"ID ile silme başarısız oldu, müşteri adı kullanılıyor: {customer_name}")
                                    success = delete_reservation(
                                        spreadsheet_name, 
                                        customer_name,
                                        worksheet_name,
                                        use_customer_name=True,
                                        room_type=room_type
                                    )
                                    
                                    if success:
                                        result = {
                                            "success": True,
                                            "message": f"Müşteri adı ile rezervasyon silindi: {customer_name}"
                                        }
                                    else:
                                        result = {
                                            "success": False,
                                            "error": "Rezervasyon silinirken bir hata oluştu.",
                                            "message": f"Rezervasyon bulunamadı veya silinemedi (ID: {reservation_id}, İsim: {customer_name})"
                                        }
                                else:
                                    result = {
                                        "success": False,
                                        "error": "Rezervasyon silinirken bir hata oluştu.",
                                        "message": f"Belirtilen ID ile rezervasyon bulunamadı: {reservation_id}"
                                    }
                        # Sadece müşteri adı varsa
                        else:
                            logger.info(f"Müşteri adı ile silme deneniyor: {customer_name}, Tam Eşleşme: {exact_match}")
                            # Eskiden direct delete_reservation çağrısı vardı, şimdi kendi filtereleme yöntemimizi kullanıyoruz
                            filtered_reservations = get_reservations_by_name(
                                spreadsheet_name,
                                customer_name,
                                exact_match=exact_match,  
                                worksheet_name=worksheet_name,
                                room_type=room_type
                            )
                            
                            if filtered_reservations:
                                success = False
                                deleted_count = 0
                                
                                # Bulunan her rezervasyonu ID'sine göre sil
                                for reservation in filtered_reservations:
                                    if 'reservation_id' in reservation:
                                        res_id = reservation.get('reservation_id')
                                        logger.info(f"Filtrelenmiş rezervasyon siliniyor: ID={res_id}, İsim={reservation.get('customer_name', 'N/A')}")
                                        if delete_reservation(spreadsheet_name, res_id, worksheet_name):
                                            deleted_count += 1
                                            success = True
                                
                                if success:
                                    if room_type:
                                        result = {
                                            "success": True,
                                            "message": f"Müşteri adı ve oda tipi ile {deleted_count} rezervasyon silindi: {customer_name} ({room_type})"
                                        }
                                    
                                    # Tam eşleşme değilse ve birden fazla rezervasyon silindiyse, bilgilendirme ekle
                                    if not exact_match and deleted_count > 1:
                                        result["warning"] = f"Dikkat: Kısmi eşleşme nedeniyle {deleted_count} rezervasyon silindi"
                                else:
                                    if room_type:
                                        result = {
                                            "success": False,
                                            "error": "Rezervasyon silinirken bir hata oluştu.",
                                            "message": f"Belirtilen müşteri adı ve oda tipi ile rezervasyon bulunamadı: {customer_name} ({room_type})"
                                        }
                                    else:
                                        result = {
                                            "success": False,
                                            "error": "Rezervasyon silinirken bir hata oluştu.",
                                            "message": f"Belirtilen müşteri adı ile rezervasyon bulunamadı: {customer_name}"
                                        }
                    except Exception as api_error:
                        logger.error(f"API hatası: {str(api_error)}")
                        result = {
                            "success": False,
                            "error": f"API Hatası: {str(api_error)}",
                            "message": "Rezervasyon silme API'sinde bir hata oluştu."
                        }
            
            # Durumu güncelle
            self.state["delete_reservation_result"] = self.state.get("delete_reservation_result", []) + [
                HumanMessage(role="system", content=str(result))
            ]
            
            # Başarılı işlem sonrası state'i temizle (önceki hata mesajlarını sil)
            if result.get("success", False):
                logger.info("Başarılı silme işlemi sonrası state temizleniyor...")
                
                # delete_reservation anahtarını tamamen sil (gelecekteki kullanımlar için boş bir alan bırak)
                if "delete_reservation" in self.state:
                    del self.state["delete_reservation"]
                    logger.info("delete_reservation alanı state'ten temizlendi")
                    
                # Son başarılı sonucu tut, diğerlerini temizle
                if "delete_reservation_result" in self.state and len(self.state["delete_reservation_result"]) > 0:
                    last_result = self.state["delete_reservation_result"][-1]
                    self.state["delete_reservation_result"] = [last_result]
                    logger.info("delete_reservation_result alanı temizlendi, sadece son sonuç tutuldu")
            
            logger.info(f"Delete reservation completed: {result.get('success')} - {result.get('message')}")
            return self.state
            
        except Exception as e:
            logger.error(f"Rezervasyon silinirken hata: {str(e)}")
            
            # Hata durumu
            result = {
                "success": False,
                "error": str(e),
                "message": "Rezervasyon silinirken bir hata oluştu."
            }
            
            self.state["delete_reservation_result"] = self.state.get("delete_reservation_result", []) + [
                HumanMessage(role="system", content=str(result))
            ]
            
            return self.state

class CheckAvailabilityAgent(Agent):
    """
    Oda müsaitliğini kontrol eden ajan.
    Belirli tarihler için oda müsaitliğini kontrol eder.
    """
    def invoke(self, research_question, conversation_state=None, availability_data=None):
        """
        Oda müsaitliğini kontrol eder.
        
        Args:
            research_question: Araştırma sorusu
            conversation_state: Konuşma durumu
            availability_data: Kontrol verileri (JSON string)
            
        Returns:
            Güncellenmiş durum
        """
        logger.info(f"CheckAvailabilityAgent invoked with data: {availability_data}")
        
        try:
            # Parametre bilgilerini al
            params_data = availability_data() if callable(availability_data) else availability_data
            
            # JSON parametrelerini ayrıştır
            if isinstance(params_data, list) and len(params_data) > 0:
                params_data = params_data[0]
                
            if not isinstance(params_data, str) or '{' not in params_data:
                result = {
                    "success": False,
                    "error": "Geçersiz parametre formatı",
                    "message": "Kontrol parametreleri JSON formatında gönderilmelidir."
                }
            else:
                try:
                    params_json = json.loads(params_data)
                    
                    # Gerekli alanları kontrol et
                    required_fields = ['check_in_date', 'check_out_date']
                    missing_fields = [field for field in required_fields if field not in params_json]
                    
                    if missing_fields:
                        result = {
                            "success": False,
                            "error": f"Eksik alanlar: {', '.join(missing_fields)}",
                            "message": "Giriş ve çıkış tarihleri belirtilmelidir."
                        }
                    else:
                        # Kontrol parametreleri
                        check_in_date = params_json.get('check_in_date')
                        check_out_date = params_json.get('check_out_date')
                        adults = int(params_json.get('adults', 2))
                        children = int(params_json.get('children', 0))
                        room_type = params_json.get('room_type')
                        
                        # Müsaitlik kontrolü yap
                        availability = check_availability(
                            check_in_date=check_in_date,
                            check_out_date=check_out_date,
                            adults=adults,
                            children=children,
                            room_type=room_type
                        )
                        
                        # Sonucu hazırla
                        result = {
                            "success": True,
                            "check_in_date": check_in_date,
                            "check_out_date": check_out_date,
                            "adults": adults,
                            "children": children,
                            "available_rooms": availability.get('available_rooms', [])
                        }
                except json.JSONDecodeError:
                    result = {
                        "success": False,
                        "error": "Geçersiz JSON formatı",
                        "message": "Kontrol parametreleri geçerli bir JSON formatında olmalıdır."
                    }
                except ValueError:
                    result = {
                        "success": False,
                        "error": "Geçersiz sayısal değer",
                        "message": "Yetişkin ve çocuk sayıları tam sayı olmalıdır."
                    }
            
            # Durumu güncelle
            self.state["availability_result"] = self.state.get("availability_result", []) + [
                HumanMessage(role="system", content=str(result))
            ]
            
            logger.info(f"Check availability completed: {result.get('success')}")
            return self.state
            
        except Exception as e:
            logger.error(f"Müsaitlik kontrolü sırasında hata: {str(e)}")
            
            # Hata durumu
            result = {
                "success": False,
                "error": str(e),
                "message": "Müsaitlik kontrolü sırasında bir hata oluştu."
            }
            
            self.state["availability_result"] = self.state.get("availability_result", []) + [
                HumanMessage(role="system", content=str(result))
            ]
            
            return self.state

class EndNodeAgent(Agent):
    """
    Akışı sonlandıran ajan.
    """
    async def invoke(self):
        """
        Akışı sonlandırır.
        
        Returns:
            Güncellenmiş durum
        """
        logger.info("EndNodeAgent invoked - workflow completed")
        
        # End durumunu işaretle
        self.state["end"] = "completed"
        
        return self.state 