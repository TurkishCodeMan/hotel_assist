# MCP Araçları Dokümantasyonu

Bu dokümanda, Altıkulaç Otel Rezervasyon Sistemi'nin kullandığı MCP (Model-Code-Protocol) araçları detaylandırılmıştır. Bu araçlar, sistem ile Google Sheets arasında veri alışverişi yaparak rezervasyon işlemlerini gerçekleştirir.

## 1. MCP Genel Bakış

MCP, yapay zeka modellerinin kod çalıştırmasına ve dış sistemlerle etkileşime girmesine olanak sağlayan bir protokoldür. Bu projede MCP, Google Sheets ile entegrasyon sağlamak için kullanılır.

```
+------------------------+      +----------------------+
|                        |      |                      |
|  LangGraph Motoru      |<---->|  MCP İstemcisi      |
|                        |      |                      |
+------------------------+      +----------------------+
                                          |
                                          v
                                +----------------------+
                                |                      |
                                |  Google Sheets       |
                                |  MCP Sunucusu        |
                                |                      |
                                +----------------------+
                                          |
                                          v
                                +----------------------+
                                |                      |
                                |  Google Sheets API   |
                                |                      |
                                +----------------------+
```

## 2. MCP Araçları

### 2.1 get_reservations

Rezervasyon kayıtlarını sorgular ve listeler.

**Açıklama**: Bu araç, Google Sheets'ten rezervasyon verilerini alır. İsteğe bağlı olarak müşteri adına göre filtreleme yapabilir.

**Parametreler**:
- `random_string`: Bir dummy parametre (opsiyonel)

**Kullanım Örneği**:
```python
result = await session.call_tool("get_reservations", arguments={})
```

**Dönüş Değeri**:
```json
[
  {
    "reservation_id": "12345",
    "customer_name": "Ahmet Yılmaz",
    "check_in_date": "2023-12-15",
    "check_out_date": "2023-12-18",
    "room_type": "Deluxe",
    "adults": 2,
    "children": 0
  },
  {
    "reservation_id": "12346",
    "customer_name": "Ayşe Demir",
    "check_in_date": "2023-12-20",
    "check_out_date": "2023-12-25",
    "room_type": "Standard",
    "adults": 1,
    "children": 1
  }
]
```

### 2.2 add_new_reservation

Yeni bir rezervasyon ekler.

**Açıklama**: Bu araç, yeni bir rezervasyon kaydı oluşturur ve Google Sheets'e ekler.

**Parametreler**:
- `customer_name` (string, zorunlu): Müşteri adı
- `check_in_date` (string, zorunlu): Giriş tarihi (YYYY-MM-DD formatında)
- `check_out_date` (string, zorunlu): Çıkış tarihi (YYYY-MM-DD formatında)
- `adults` (integer, zorunlu): Yetişkin sayısı
- `children` (integer, zorunlu): Çocuk sayısı
- `room_type` (string, zorunlu): Oda tipi (örn. Standard, Deluxe, Suite)

**Kullanım Örneği**:
```python
result = await session.call_tool("add_new_reservation", arguments={
    "customer_name": "Mehmet Yıldız",
    "check_in_date": "2024-01-10",
    "check_out_date": "2024-01-15",
    "adults": 2,
    "children": 1,
    "room_type": "Suite"
})
```

**Dönüş Değeri**:
```json
{
  "status": "success",
  "message": "Rezervasyon başarıyla eklendi.",
  "reservation_id": "12347",
  "details": {
    "customer_name": "Mehmet Yıldız",
    "check_in_date": "2024-01-10",
    "check_out_date": "2024-01-15",
    "room_type": "Suite",
    "adults": 2,
    "children": 1
  }
}
```

### 2.3 update_existing_reservation

Mevcut bir rezervasyonu günceller.

**Açıklama**: Bu araç, rezervasyon ID'sine göre bir kaydı günceller. Sadece değiştirilmek istenen alanlar belirtilir.

**Parametreler**:
- `reservation_id` (string, zorunlu): Güncellenecek rezervasyonun ID'si
- `customer_name` (string, opsiyonel): Müşteri adı
- `check_in_date` (string, opsiyonel): Giriş tarihi (YYYY-MM-DD formatında)
- `check_out_date` (string, opsiyonel): Çıkış tarihi (YYYY-MM-DD formatında)
- `adults` (integer, opsiyonel): Yetişkin sayısı
- `children` (integer, opsiyonel): Çocuk sayısı
- `room_type` (string, opsiyonel): Oda tipi

**Kullanım Örneği**:
```python
result = await session.call_tool("update_existing_reservation", arguments={
    "reservation_id": "12347",
    "check_in_date": "2024-01-12",
    "adults": 3
})
```

**Dönüş Değeri**:
```json
{
  "status": "success",
  "message": "Rezervasyon başarıyla güncellendi.",
  "updated_fields": ["check_in_date", "adults"],
  "details": {
    "customer_name": "Mehmet Yıldız",
    "check_in_date": "2024-01-12",
    "check_out_date": "2024-01-15",
    "room_type": "Suite",
    "adults": 3,
    "children": 1
  }
}
```

### 2.4 delete_existing_reservation

Bir rezervasyonu siler.

**Açıklama**: Bu araç, rezervasyon ID'sine veya müşteri adına göre rezervasyonları siler.

**Parametreler**:
- `reservation_id` (string, opsiyonel): Silinecek rezervasyonun ID'si
- `customer_name` (string, opsiyonel): Rezervasyonları silinecek müşterinin adı
- `room_type` (string, opsiyonel): Müşteri adına göre filtreleme yaparken oda tipi
- `use_customer_name` (boolean, opsiyonel): Kullanımdan kaldırılmış, geriye dönük uyumluluk için korunmuş

**Not**: Ya `reservation_id` ya da `customer_name` belirtilmelidir.

**Kullanım Örneği**:
```python
# ID ile silme
result = await session.call_tool("delete_existing_reservation", arguments={
    "reservation_id": "12347"
})

# Müşteri adı ile silme
result = await session.call_tool("delete_existing_reservation", arguments={
    "customer_name": "Mehmet Yıldız"
})

# Müşteri adı ve oda tipi ile silme
result = await session.call_tool("delete_existing_reservation", arguments={
    "customer_name": "Mehmet Yıldız",
    "room_type": "Suite"
})
```

**Dönüş Değeri**:
```json
{
  "status": "success",
  "message": "Rezervasyon başarıyla silindi.",
  "deleted_reservation": {
    "reservation_id": "12347",
    "customer_name": "Mehmet Yıldız",
    "check_in_date": "2024-01-12",
    "check_out_date": "2024-01-15",
    "room_type": "Suite"
  }
}
```

## 3. MCP Bağlantısı ve Kullanımı

### 3.1 MCP Oturumu Başlatma

```python
# MCP sunucusunu başlat
command = "python"
mcp_path = "/path/to/google-sheets-mcp/sheet.py"
server_params = StdioServerParameters(command=command, args=[mcp_path])

# İstemci akışını oluştur
client_stream = stdio_client(server_params)
stdio, write = await stack.enter_async_context(client_stream)

# Oturumu başlat
session = ClientSession(stdio, write)
await stack.enter_async_context(session)
await session.initialize()

# Kullanılabilir araçları listele
tools_response = await session.list_tools()
tools = tools_response.tools
```

### 3.2 MCP Araç Çağrısı Yapma

```python
try:
    # Araç çağrısı yap
    result = await session.call_tool(tool_name, arguments=arguments)
    
    # Sonucu işle
    if result:
        # Başarılı
        processed_result = process_result(result)
        return processed_result
    else:
        # Boş sonuç
        return {"error": "Araç sonucu boş döndü."}
        
except Exception as e:
    # Hata durumu
    error_message = f"Araç çağrısı hatası: {str(e)}"
    return {"error": error_message}
```

### 3.3 MCP Oturumunu Kapatma

```python
# Oturumu güvenli bir şekilde kapat
await session.close()
```

## 4. MCP Hata İşleme

### 4.1 Genel MCP Hataları ve Çözümleri

| Hata Tipi | Açıklama | Çözüm |
|-----------|----------|-------|
| Bağlantı Hatası | MCP sunucusuna bağlanılamadı | MCP sunucusunun çalıştığını doğrula |
| Zaman Aşımı | MCP sunucusu yanıt vermiyor | Timeout değerini artır veya yeniden dene |
| Araç Bulunamadı | Belirtilen araç mevcut değil | Araç adını ve kullanılabilir araçları kontrol et |
| Parametre Hatası | Gerekli parametre eksik veya yanlış | Parametre adlarını ve tiplerini kontrol et |

### 4.2 Google Sheets Özel Hataları

| Hata Kodu | Açıklama | Çözüm |
|-----------|----------|-------|
| 404 | Belirtilen rezervasyon bulunamadı | Rezervasyon ID'sini veya adını kontrol et |
| 409 | Çakışan rezervasyon bulundu | Tarih aralığını veya oda tipini değiştir |
| 403 | Erişim yetkisi hatası | API kimlik bilgilerini kontrol et |

## 5. MCP Tool Performans İyileştirmeleri

### 5.1 MCP Araç Çağrılarını Optimize Etme

1. **Toplu İşlemler**: Mümkünse, birden fazla rezervasyon işlemini tek bir çağrıda yapın
2. **Seçici Sorgulamalar**: Sadece ihtiyaç duyulan verileri sorgulayın
3. **Önbelleğe Alma**: Sık kullanılan verileri önbelleğe alın
4. **Bağlantı Havuzu**: Uzun süreli veya sık kullanımlar için bağlantı havuzu oluşturun

### 5.2 Hata Durumlarında Otomatik Kurtarma

1. **Yeniden Deneme Stratejileri**: Geçici hatalar için otomatik yeniden deneme mekanizmaları
2. **Degrade Mod**: Bazı araçlar kullanılamadığında sınırlı işlevsellikle devam etme
3. **Yedek Mekanizmalar**: Kritik işlevler için alternatif yöntemler 