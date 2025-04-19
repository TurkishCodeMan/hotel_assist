# Altıkulaç Otel Rezervasyon Sistemi - Mimari Dokümantasyon

Bu dokümanda, Altıkulaç Otel Rezervasyon Sistemi'nin mimari yapısı, bileşenleri ve veri akışı detaylandırılmıştır.

## 1. Genel Mimari

Altıkulaç Otel Rezervasyon Sistemi, LangGraph tabanlı bir ajan mimarisi kullanır ve Google Gemini API ile entegre çalışır. Sistem, MCP (Model-Code-Protocol) üzerinden dış araçlarla iletişim kurarak rezervasyon işlemlerini gerçekleştirir.

### 1.1 Mimari Şema

```
+------------------------+      +----------------------+
|                        |      |                      |
|  Streamlit Arayüzü     |<---->|  LangGraph Motoru    |
|                        |      |                      |
+------------------------+      +----------------------+
            ^                              ^
            |                              |
            v                              v
+------------------------+      +----------------------+
|                        |      |                      |
|  MCP Bağlantı Katmanı  |<---->|  Gemini API         |
|                        |      |                      |
+------------------------+      +----------------------+
            ^
            |
            v
+------------------------+
|                        |
|  Google Sheets         |
|  (Veri Depolama)       |
|                        |
+------------------------+
```

### 1.2 Temel Bileşenler

1. **Streamlit Arayüzü**: Kullanıcıların sistemle etkileşime girdiği web tabanlı arayüz
2. **LangGraph Motoru**: Ajan iş akışını yöneten ve durumu takip eden merkezi bileşen
3. **MCP Bağlantı Katmanı**: Dış sistemlerle etkileşimi sağlayan protokol katmanı
4. **Gemini API**: Doğal dil işleme ve anlama yetenekleri için kullanılan LLM servisi
5. **Google Sheets**: Rezervasyon verilerinin depolanması ve yönetilmesi için kullanılan veri tablosu

## 2. Ajan Mimarisi

Sistem, basitleştirilmiş bir ajan mimarisi kullanır. Gereksiz ajan katmanları kaldırılarak doğrudan MCP araçlarıyla iletişim sağlanır.

### 2.1 Mevcut Ajanlar

1. **ReservationAgent**: Kullanıcı mesajlarını işleyen, anlayan ve uygun araçları çağıran ana ajan
2. **EndNodeAgent**: İş akışının sonlandırılması ve son yanıtın formatlanması için kullanılan ajan

### 2.2 İş Akışı Grafiği

```
+-----------------+      +------------+
|                 |      |            |
| ReservationAgent|----->| EndNode    |
|                 |      |            |
+-----------------+      +------------+
```

## 3. Veri Akışı

Sistemdeki veri akışı aşağıdaki adımları takip eder:

1. Kullanıcı, Streamlit arayüzünden bir mesaj gönderir
2. Streamlit, mesajı LangGraph motoruna iletir
3. ReservationAgent, mesajı analiz eder ve gerekli MCP araçlarını belirler
4. ReservationAgent, MCP araçlarını çağırarak Google Sheets'ten veri alır veya günceller
5. İşlem sonuçları EndNode'a iletilir
6. EndNode, son kullanıcı yanıtını oluşturur
7. Yanıt, Streamlit arayüzü üzerinden kullanıcıya gösterilir

### 3.1 Durum (State) Yönetimi

Sistem, ajanlar arasında durum bilgisini taşıyan bir `AgentGraphState` nesnesi kullanır. Bu nesne, konuşma geçmişi, kullanıcı soruları ve ajan yanıtları gibi verileri içerir.

Örnek durum nesnesi:
```python
{
    "research_question": ["Yarın için iki kişilik bir oda var mı?"],
    "reservation_response": {"role": "assistant", "content": "..."},
    "messages": [...]
}
```

## 4. MCP (Model-Code-Protocol) Entegrasyonu

MCP, sistem ile dış kaynaklar (bu durumda Google Sheets) arasında bir köprü görevi görür.

### 4.1 MCP Araçları

Sistem, aşağıdaki MCP araçlarını kullanır:

1. **get_reservations**: Mevcut rezervasyonları sorgular
2. **add_new_reservation**: Yeni bir rezervasyon ekler
3. **update_existing_reservation**: Var olan bir rezervasyonu günceller
4. **delete_existing_reservation**: Bir rezervasyonu siler

### 4.2 MCP Bağlantı Yönetimi

MCP bağlantıları `managed_mcp_connection` context manager'ı ile yönetilir. Bu yapı:

- MCP sunucusuna bağlantı kurar
- Kullanılabilir araçları listeler
- İstek gönderir ve yanıtları alır
- Bağlantıyı güvenli bir şekilde kapatır

## 5. LLM Entegrasyonu

Sistem, Google'ın Gemini AI modelleri ile entegre çalışır.

### 5.1 Model Konfigürasyonu

Şu anda sistem, aşağıdaki yapılandırma ile çalışır:

- **Model**: gemini-2.0-flash
- **Sıcaklık**: 0.1-0.5 (dinamik ayarlanabilir)
- **Maksimum Token**: 2048

### 5.2 Prompt Şablonları

Sistem, `prompts/prompts.py` dosyasında tanımlanan özelleştirilmiş sistem promptları kullanır. Bu promptlar:

- Türkçe dil işleme
- Rezervasyon işlemlerini anlama
- Tool kullanımını yönlendirme

için özel olarak tasarlanmıştır.

## 6. Kullanıcı Arayüzü

Kullanıcı arayüzü, Streamlit kütüphanesi kullanılarak oluşturulmuştur.

### 6.1 Temel Bileşenler

- **Konuşma Geçmişi**: Kullanıcı ve asistan mesajlarını gösteren alan
- **Mesaj Girişi**: Kullanıcının yeni mesajlar yazabileceği form
- **Yan Panel**: Sistem durumunu ve istatistikleri gösteren panel

### 6.2 Asenkron UI Güncellemeleri

Streamlit arayüzü, asenkron işlemleri desteklemek için `asyncio` ile entegre edilmiştir. Bu, uzun süren LLM ve MCP çağrıları sırasında UI'nin donmasını önler.

## 7. Veri Modeli

### 7.1 Rezervasyon Şeması

Rezervasyon verilerinin yapısı:

```json
{
  "reservation_id": "12345",
  "customer_name": "Ahmet Yılmaz",
  "check_in_date": "2023-12-15",
  "check_out_date": "2023-12-18",
  "room_type": "Deluxe",
  "adults": 2,
  "children": 1
}
```

### 7.2 Google Sheets Entegrasyonu

Sistem, rezervasyon verilerini Google Sheets'te saklar ve yönetir. Sheets şu sütunları içerir:

- Rezervasyon ID
- Müşteri Adı
- Giriş Tarihi
- Çıkış Tarihi
- Oda Tipi
- Yetişkin Sayısı
- Çocuk Sayısı
- Durum

## 8. Hata İşleme Mekanizmaları

### 8.1 Bağlantı Hataları

Sistem, MCP bağlantı hatalarını yakalamak ve işlemek için gelişmiş mekanizmalar kullanır:

- Otomatik yeniden bağlanma
- Timeout yönetimi
- Bağlantı durumu izleme

### 8.2 LLM Yanıt Hataları

LLM'den gelen hatalı veya beklenmeyen yanıtlar için:

- Formatlanmamış yanıtları işleme
- JSON ayrıştırma hatalarını telafi etme
- Kullanıcı dostu hata mesajları oluşturma

## 9. Güvenlik Önlemleri

### 9.1 API Anahtarı Yönetimi

- API anahtarları `.env` dosyasında saklanır
- Ortam değişkenleri üzerinden erişilir

### 9.2 Veri Koruması

- Kişisel rezervasyon verileri şifrelenmez
- Kullanıcı adı ve iletişim bilgileri için belirli koruma önlemleri yoktur (geliştirme alanı)

## 10. Dağıtım Mimarisi

### 10.1 Geliştirme Ortamı

- Python virtual environment
- Streamlit yerel sunucu
- MCP yerel sunucu

### 10.2 Üretim Ortamı

- Streamlit Cloud veya özel sunucu
- Kalıcı MCP bağlantıları
- Google Sheets API kimlik doğrulama

## 11. Gelecek Mimari İyileştirmeler

1. **Servis Katmanı**: İş mantığını ajanlardan ayırmak
2. **Veritabanı Geçişi**: Google Sheets'ten daha güçlü bir veritabanına geçiş
3. **Önbellek Katmanı**: Sık kullanılan veriler için önbellek
4. **Mikro Servis Mimarisi**: Bileşenleri ayrı servisler olarak ayırma
5. **Konteynerizasyon**: Docker ile dağıtım ve ölçeklendirme 