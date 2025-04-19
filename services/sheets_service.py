"""
Google Sheets Servisi
------------------
Rezervasyon sistemi için Google Sheets işlemlerini yöneten servis sınıfı.
"""

import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import logging
from datetime import datetime

# Logger ayarları
logger = logging.getLogger(__name__)

# Google Sheets API için kapsam ve kimlik bilgileri
SCOPES = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
CREDENTIALS_FILE = 'google_credentials.json'

def get_sheet_client():
    """
    Google Sheets API istemcisini döndürür.
    Kimlik bilgilerini dosyadan veya çevre değişkenlerinden okur.
    """
    try:
        # 1. Önce GOOGLE_CREDENTIALS çevre değişkenini kontrol et
        if os.environ.get('GOOGLE_CREDENTIALS'):
            import json
            logger.info("Kimlik bilgileri çevre değişkeninden okunuyor...")
            credentials_json = os.environ.get('GOOGLE_CREDENTIALS')
            
            # JSON formatı düzeltme - bazen çevre değişkenleri tırnak içine alınır
            if credentials_json.startswith("'") and credentials_json.endswith("'"):
                credentials_json = credentials_json[1:-1]
                
            credentials_dict = json.loads(credentials_json)
            credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, SCOPES)
            
        # 2. Sonra google_credentials.json dosyasını kontrol et
        elif os.path.exists(CREDENTIALS_FILE):
            logger.info(f"Kimlik bilgileri dosyadan okunuyor: {CREDENTIALS_FILE}")
            credentials = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, SCOPES)
            
        else:
            raise FileNotFoundError(
                f"Kimlik bilgileri bulunamadı: {CREDENTIALS_FILE} dosyası mevcut değil "
                f"ve GOOGLE_CREDENTIALS çevre değişkeni tanımlanmamış."
            )
            
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        logger.error(f"Google Sheets API bağlantı hatası: {str(e)}")
        raise

def open_sheet(spreadsheet_name_or_key, worksheet_name=None):
    """
    Belirtilen tabloyu ve sayfayı açar.
    
    Args:
        spreadsheet_name_or_key (str): Tablo adı veya benzersiz anahtarı
        worksheet_name (str, optional): Sayfa adı (belirtilmezse ilk sayfa kullanılır)
    
    Returns:
        tuple: (Spreadsheet object, Worksheet object)
    """
    try:
        client = get_sheet_client()
        
        # Anahtarla veya adla tablo aç
        if spreadsheet_name_or_key.startswith('1'):  # Muhtemelen bir anahtar
            spreadsheet = client.open_by_key(spreadsheet_name_or_key)
        else:
            spreadsheet = client.open(spreadsheet_name_or_key)
        
        # Belirli bir sayfa iste veya ilk sayfayı al
        if worksheet_name:
            worksheet = spreadsheet.worksheet(worksheet_name)
        else:
            worksheet = spreadsheet.sheet1
            
        return spreadsheet, worksheet
    except gspread.exceptions.SpreadsheetNotFound:
        logger.error(f"Tablo bulunamadı: {spreadsheet_name_or_key}")
        raise
    except gspread.exceptions.WorksheetNotFound:
        logger.error(f"Sayfa bulunamadı: {worksheet_name}")
        raise
    except Exception as e:
        logger.error(f"Tablo açılırken hata: {str(e)}")
        raise

def create_spreadsheet(spreadsheet_name, share_with=None):
    """
    Yeni bir Google Tablosu oluşturur.
    
    Args:
        spreadsheet_name (str): Oluşturulacak tablonun adı
        share_with (str, optional): Tablonun paylaşılacağı e-posta adresi
    
    Returns:
        gspread.Spreadsheet: Oluşturulan tablo nesnesi
    """
    try:
        client = get_sheet_client()
        spreadsheet = client.create(spreadsheet_name)
        
        # Belirtilirse, tablo paylaş
        if share_with:
            spreadsheet.share(share_with, perm_type='user', role='writer')
            
        return spreadsheet
    except Exception as e:
        logger.error(f"Tablo oluşturulurken hata: {str(e)}")
        raise

def get_all_reservations(spreadsheet_name_or_key, worksheet_name=None):
    """
    Tüm rezervasyon verilerini listeler.
    
    Args:
        spreadsheet_name_or_key (str): Tablo adı veya benzersiz anahtarı
        worksheet_name (str, optional): Sayfa adı
    
    Returns:
        list: Rezervasyon bilgilerini içeren sözlük listesi
    """
    try:
        _, worksheet = open_sheet(spreadsheet_name_or_key, worksheet_name)
        
        # Debug: Tablo içeriğini göster
        print(f"DEBUG: Tablo içeriği kontrolü")
        all_values = worksheet.get_all_values()
        print(f"DEBUG: Toplam satır sayısı: {len(all_values)}")
        if len(all_values) > 0:
            print(f"DEBUG: İlk satır (headers): {all_values[0]}")
        if len(all_values) > 1:
            print(f"DEBUG: İkinci satır (ilk veri): {all_values[1]}")
        
        # Tüm verileri sözlük listesi olarak al
        records = worksheet.get_all_records()
        print(f"DEBUG: get_all_records sonucu: {len(records)} kayıt")
        
        # Başka bir şekilde deneyelim
        if len(records) == 0 and len(all_values) > 1:
            print("DEBUG: Manuel kayıt oluşturma deneniyor")
            records = []
            headers = all_values[0]
            for row in all_values[1:]:  # Başlık satırını atla
                record = {}
                for i, header in enumerate(headers):
                    if i < len(row):  # Dizin sınırlarını kontrol et
                        record[header] = row[i]
                    else:
                        record[header] = ''  # Boş hücreleri boş string ile doldur
                records.append(record)
            print(f"DEBUG: Manuel oluşturulan kayıt sayısı: {len(records)}")
        
        return records
    except Exception as e:
        logger.error(f"Rezervasyon verileri alınırken hata: {str(e)}")
        print(f"DEBUG HATA: {str(e)}")
        return []

def get_reservations_by_name(spreadsheet_name_or_key, customer_name, exact_match=True, worksheet_name=None, room_type=None):
    """
    Müşteri adına göre rezervasyonları filtreler.
    
    Args:
        spreadsheet_name_or_key (str): Tablo adı veya benzersiz anahtarı
        customer_name (str): Filtrelenecek müşteri adı
        exact_match (bool): True ise tam eşleşme arar, False ise içeren kayıtları bulur
        worksheet_name (str, optional): Sayfa adı
        room_type (str, optional): Oda tipi filtresi
    
    Returns:
        list: Filtrelenmiş rezervasyon bilgilerini içeren sözlük listesi
    """
    try:
        logger.info(f"Müşteri adı filtreleme: Müşteri={customer_name}, Oda Tipi={room_type}, Tam Eşleşme={exact_match}")
        
        # Tüm rezervasyonları al
        records = get_all_reservations(spreadsheet_name_or_key, worksheet_name)
        
        if not records:
            logger.warning("Filtrelenecek kayıt bulunamadı")
            return []
        
        # Filtreleme öncesi kayıt sayısı
        logger.info(f"Filtreleme öncesi toplam kayıt: {len(records)}")
        
        # Filtreleme işlemi
        filtered_records = []
        for record in records:
            # Müşteri adı kontrolü (customer_name alanı varsa)
            if 'customer_name' not in record:
                logger.warning("Kayıtta 'customer_name' alanı bulunamadı")
                continue
                
            current_name = record.get('customer_name', '')
            
            # İsim eşleşme kontrolü (büyük/küçük harf duyarsız)
            if exact_match:
                # Tam eşleşme kontrolü
                name_match = (current_name.lower() == customer_name.lower())
            else:
                # İçerme kontrolü
                name_match = (customer_name.lower() in current_name.lower())
            
            # Oda tipi kontrolü (belirtilmişse)
            room_match = True
            if room_type and 'room_type' in record:
                current_room = record.get('room_type', '')
                room_match = (current_room.lower() == room_type.lower())
            
            # Hem isim hem de oda tipi eşleşiyorsa listeye ekle
            if name_match and room_match:
                filtered_records.append(record)
                logger.debug(f"Eşleşen kayıt: {record}")
        
        logger.info(f"Filtreleme sonrası eşleşen kayıt: {len(filtered_records)}")
        return filtered_records
        
    except Exception as e:
        logger.error(f"İsme göre rezervasyon filtreleme hatası: {str(e)}")
        print(f"DEBUG FILTRELEME HATASI: {str(e)}")
        return []

def add_reservation(spreadsheet_name_or_key, reservation_data, worksheet_name=None):
    """
    Tabloya yeni bir rezervasyon ekler.
    
    Args:
        spreadsheet_name_or_key (str): Tablo adı veya benzersiz anahtarı
        reservation_data (dict): Eklencek rezervasyon verileri
        worksheet_name (str, optional): Sayfa adı
    
    Returns:
        bool: İşlem başarılı ise True, değilse False
    """
    try:
        _, worksheet = open_sheet(spreadsheet_name_or_key, worksheet_name)
        
        # DEBUG: Tablo bilgilerini göster
        print(f"DEBUG: Tablo başlıkları ve boyut kontrolü")
        try:
            all_values = worksheet.get_all_values()
            print(f"DEBUG: Mevcut satır sayısı: {len(all_values)}")
            if len(all_values) > 0:
                print(f"DEBUG: Başlık satırı: {all_values[0]}")
        except Exception as e:
            print(f"DEBUG: Tablo verileri alınırken hata: {str(e)}")
        
        # Başlıkları al
        headers = worksheet.row_values(1)
        print(f"DEBUG: Alınan başlıklar: {headers}")
        print(f"DEBUG: Eklenecek veri: {reservation_data}")
        
        # Veri satırını hazırla
        row_data = []
        for header in headers:
            if header == 'reservation_id' and header not in reservation_data:
                # Otomatik rezervasyon ID oluştur (timestamp)
                res_id = f"RES_{int(datetime.now().timestamp())}"
                row_data.append(res_id)
                print(f"DEBUG: Otomatik ID oluşturuldu: {res_id}")
            elif header == 'created_at' and header not in reservation_data:
                # Oluşturma zamanı ekle
                created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                row_data.append(created_at)
                print(f"DEBUG: Zaman damgası eklendi: {created_at}")
            else:
                # Belirtilen veriyi ekle veya boş bırak
                value = reservation_data.get(header, '')
                row_data.append(value)
        
        print(f"DEBUG: Oluşturulan veri satırı: {row_data}")
        
        # Satırı tabloya ekle
        result = worksheet.append_row(row_data)
        print(f"DEBUG: API yanıtı: {result}")
        
        # Ekleme sonrasını kontrol et
        try:
            new_values = worksheet.get_all_values()
            print(f"DEBUG: Ekleme sonrası satır sayısı: {len(new_values)}")
            if len(new_values) > 1:
                print(f"DEBUG: Son satır: {new_values[-1]}")
        except Exception as e:
            print(f"DEBUG: Kontrol hatası: {str(e)}")
        
        return True
    except Exception as e:
        logger.error(f"Rezervasyon eklenirken hata: {str(e)}")
        print(f"DEBUG EKLEME HATASI: {str(e)}")
        return False

def update_reservation(spreadsheet_name_or_key, reservation_id, updated_data, worksheet_name=None):
    """
    Mevcut bir rezervasyonu günceller.
    
    Args:
        spreadsheet_name_or_key (str): Tablo adı veya benzersiz anahtarı
        reservation_id (str): Güncellenecek rezervasyon ID'si
        updated_data (dict): Güncelleme verileri
        worksheet_name (str, optional): Sayfa adı
    
    Returns:
        bool: İşlem başarılı ise True, değilse False
    """
    try:
        _, worksheet = open_sheet(spreadsheet_name_or_key, worksheet_name)
        
        # Başlıkları al
        headers = worksheet.row_values(1)
        
        # Rezervasyon ID'sinin hangi sütunda olduğunu bul
        if 'reservation_id' not in headers:
            logger.error("Tabloda 'reservation_id' sütunu bulunamadı")
            return False
            
        id_col = headers.index('reservation_id') + 1
        
        # ID'si eşleşen satırı bul
        cell = worksheet.find(reservation_id)
        if not cell or cell.col != id_col:
            logger.error(f"Rezervasyon bulunamadı: {reservation_id}")
            return False
            
        row_num = cell.row
        
        # Her bir hücreyi güncelle
        for key, value in updated_data.items():
            if key in headers:
                col_num = headers.index(key) + 1
                worksheet.update_cell(row_num, col_num, value)
                
        return True
    except Exception as e:
        logger.error(f"Rezervasyon güncellenirken hata: {str(e)}")
        return False

def delete_reservation(spreadsheet_name_or_key, reservation_id, worksheet_name=None, use_customer_name=False, room_type=None):
    """
    Bir rezervasyonu siler.
    
    Args:
        spreadsheet_name_or_key (str): Tablo adı veya benzersiz anahtarı
        reservation_id (str): Silinecek rezervasyon ID'si veya müşteri adı
        worksheet_name (str, optional): Sayfa adı
        use_customer_name (bool): True ise reservation_id parametresi müşteri adı olarak kabul edilir
        room_type (str, optional): Oda tipi (müşteri adıyla birlikte filtrelerken kullanılır)
    
    Returns:
        bool: İşlem başarılı ise True, değilse False
    """
    try:
        logger.info(f"Rezervasyon silme işlemi başlatıldı: ID/İsim={reservation_id}, Oda Tipi={room_type}, use_customer_name={use_customer_name}")
        _, worksheet = open_sheet(spreadsheet_name_or_key, worksheet_name)
        
        # Tüm verileri al
        all_data = worksheet.get_all_values()
        headers = all_data[0] if all_data else []
        
        # Debug bilgisi
        logger.debug(f"Tablo başlıkları: {headers}")
        logger.debug(f"Toplam kayıt sayısı: {len(all_data) - 1}")
        
        if use_customer_name:
            # Müşteri adına göre sil
            if 'customer_name' not in headers:
                logger.error("Tabloda 'customer_name' sütunu bulunamadı")
                return False
                
            customer_col = headers.index('customer_name')
            
            # Oda tipi filtresi için kolon indeksi
            room_type_col = -1
            if room_type and 'room_type' in headers:
                room_type_col = headers.index('room_type')
            
            deleted_rows = []
            
            # Her satırı kontrol et - büyük/küçük harf duyarsız
            for i, row in enumerate(all_data[1:], start=2):  # 1 tabanlı satır indeksi, başlık satırını atla
                # Satırın kısa olma durumunu kontrol et
                if customer_col < len(row):
                    row_customer_name = row[customer_col]
                    
                    # Müşteri adı eşleşiyor mu?
                    customer_match = (row_customer_name and reservation_id and 
                                    row_customer_name.lower() == reservation_id.lower())
                    
                    # Oda tipi kontrolü
                    room_type_match = True  # Varsayılan olarak eşleşti kabul et
                    if room_type and room_type_col >= 0 and room_type_col < len(row):
                        # Oda tipi belirtilmişse ve eşleşmiyorsa bu satırı atla
                        row_room_type = row[room_type_col]
                        room_type_match = (row_room_type.lower() == room_type.lower())
                    
                    # Hem müşteri adı hem de (belirtildiyse) oda tipi eşleşiyorsa, sil
                    if customer_match and room_type_match:
                        deleted_rows.append(i)
                        logger.info(f"Silme için işaretlenen satır: {i}, Müşteri: {row_customer_name}, Oda: {row[room_type_col] if room_type_col >= 0 and room_type_col < len(row) else 'N/A'}")
                else:
                    # Satır, customer_name sütununu içermiyorsa atla
                    logger.warning(f"Satır {i} eksik veri içeriyor, müşteri adı sütunu yok")
            
            # Satırları büyükten küçüğe doğru sil (indeks kayması olmaması için)
            if deleted_rows:
                logger.info(f"Toplam {len(deleted_rows)} rezervasyon silinecek")
                for row_idx in sorted(deleted_rows, reverse=True):
                    logger.info(f"Satır siliniyor: {row_idx}")
                    worksheet.delete_rows(row_idx)
                return True
            else:
                filter_desc = f"müşteri adı '{reservation_id}'"
                if room_type:
                    filter_desc += f" ve oda tipi '{room_type}'"
                logger.warning(f"Şu kriterlerle rezervasyon bulunamadı: {filter_desc}")
                return False
        else:
            # Rezervasyon ID'sine göre sil
            if 'reservation_id' not in headers:
                logger.error("Tabloda 'reservation_id' sütunu bulunamadı")
                return False
                
            id_col = headers.index('reservation_id')
            
            # Her satırı kontrol et
            for i, row in enumerate(all_data[1:], start=2):  # 1 tabanlı satır indeksi
                # Satırın kısa olma durumunu kontrol et
                if id_col < len(row):
                    row_id = row[id_col]
                    if row_id == reservation_id:
                        logger.info(f"Rezervasyon bulundu, siliniyor: Satır={i}, ID={reservation_id}")
                        worksheet.delete_rows(i)
                        return True
                else:
                    # Satır, id sütununu içermiyorsa atla
                    logger.warning(f"Satır {i} eksik veri içeriyor, ID sütunu yok")
            
            logger.warning(f"Şu ID ile rezervasyon bulunamadı: {reservation_id}")
            return False
    except Exception as e:
        logger.error(f"Rezervasyon silinirken hata: {str(e)}")
        return False

def check_availability(check_in_date, check_out_date, adults=2, children=0, room_type=None):
    """
    Belirtilen kriterlere göre oda müsaitliğini kontrol eder.
    Bu işlev şuanda sadece bir örnek olarak bulunmaktadır.
    Gerçek bir uygulamada, rezervasyon verileri kontrol edilmeli.
    
    Args:
        check_in_date (str): Giriş tarihi (YYYY-MM-DD)
        check_out_date (str): Çıkış tarihi (YYYY-MM-DD)
        adults (int): Yetişkin sayısı
        children (int): Çocuk sayısı
        room_type (str, optional): Oda tipi
    
    Returns:
        dict: Müsaitlik sonuçları
    """
    # Bu örnek işlev rezervasyon sisteminize göre geliştirilmelidir
    # Şu an için sabit bir yanıt döndürüyor
    
    # Gerçek bir uygulamada:
    # 1. Tablo verilerini alın
    # 2. Tarih aralığında çakışan rezervasyonları kontrol edin
    # 3. Müsait odaları ve fiyatları hesaplayın
    
    available_rooms = [
        {"room_type": "Standard", "price": 100, "available": True},
        {"room_type": "Deluxe", "price": 150, "available": True},
        {"room_type": "Suite", "price": 250, "available": True}
    ]
    
    # Eğer oda tipi belirtilmişse, sadece o oda tipini göster
    if room_type:
        available_rooms = [room for room in available_rooms if room["room_type"].lower() == room_type.lower()]
    
    return {
        "check_in_date": check_in_date,
        "check_out_date": check_out_date,
        "adults": adults,
        "children": children,
        "available_rooms": available_rooms
    }
