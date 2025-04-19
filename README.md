# Otel Rezervasyon Asistanı

WhatsApp Business API, DeepSeek ve Google Tablolar entegrasyonu ile çalışan, akıllı otel rezervasyon asistanı.

## Proje Hakkında

Bu proje, otellerin doğrudan satış kanallarındaki iş yükünü hafifletmek ve müşteri deneyimini iyileştirmek için geliştirilmiş bir yapay zeka çözümüdür. WhatsApp üzerinden müşterilerle iletişim kurarak, rezervasyon süreçlerini otomatikleştirir ve Google Tablolar ile entegre çalışır.

### Temel Özellikler

- WhatsApp üzerinden 7/24 müşteri etkileşimi
- Oda müsaitliği sorgulama
- Rezervasyon oluşturma ve onaylama
- Müşteri bilgilerini toplama ve doğrulama
- Rezervasyon değişikliği ve iptali
- Sık sorulan sorulara yanıt verme

## Kurulum

### Gereksinimler

- Python 3.9+
- WhatsApp Business API hesabı
- OpenRouter API anahtarı (DeepSeek modeli için)
- Google Cloud Projesi ve Servis Hesabı (Sheets API)

### Adımlar

1. Bağımlılıkları yükleyin:
   ```
   pip install -r requirements.txt
   ```

2. `.env` dosyasını yapılandırın:
   ```
   # OpenRouter API (DeepSeek)
   OPENROUTER_API_KEY=your_api_key_here

   # WhatsApp Cloud API
   WHATSAPP_TOKEN=your_whatsapp_token
   WHATSAPP_PHONE_ID=your_phone_id
   WHATSAPP_VERIFY_TOKEN=your_verify_token

   # Google Sheets
   SHEETS_SPREADSHEET_ID=your_spreadsheet_id
   GOOGLE_CREDENTIALS_FILE=path_to_credentials.json
   ```

3. Google Servis Hesabı kimlik bilgilerini `google_credentials.json` dosyasına kaydedin

4. Google Tablolar'ı oluşturun ve ilgili çalışma sayfalarını ekleyin:
   - `availability`: Müsaitlik bilgileri
   - `reservations`: Rezervasyon kayıtları
   - `rooms`: Oda bilgileri
   - `customers`: Müşteri bilgileri

## Kullanım

Uygulamayı başlatmak için:

```bash
python app.py
```

Bu, Flask sunucusunu başlatır ve WhatsApp API için webhook'ları dinlemeye başlar.

### Test İşlemleri

Sistemi WhatsApp'a bağlamadan test etmek için:

```bash
curl -X POST http://localhost:5000/test \
  -H "Content-Type: application/json" \
  -d '{"sender_id": "test_user", "message": "Merhaba, 15-20 Temmuz tarihleri arasında 2 kişi için oda müsaitliği öğrenmek istiyorum"}'
```

## Proje Yapısı

Detaylı proje yapısı için [docs/structure.md](docs/structure.md) belgesine bakın.

## Geliştirme

Projeye katkıda bulunmak istiyorsanız:

1. Proje mimarisini ve mevcut kodu inceleyin
2. Yeni özellikler eklemeden önce test yazın
3. Geliştirme planı için [docs/PROJECT.md](docs/PROJECT.md) dosyasını takip edin

## Lisans

Bu proje özel kullanım içindir ve tüm hakları saklıdır.
# hotel_assistant
