# OTEL REZERVASYON ASİSTANI - PROJE GELİŞTİRME PLANI

## 1. Proje Özeti

### Vizyon
Otellerin doğrudan satış kanallarındaki iş yükünü hafifletmek ve müşteri deneyimini iyileştirmek için yapay zeka destekli bir rezervasyon asistanı geliştirmek.

### Amaç
Web Arayüzü üzerinden müşterilerle etkileşime geçen, rezervasyon süreçlerini otomatikleştiren ve Google Tablolar ile entegre çalışan akıllı bir asistan sistemi oluşturmak.

### Temel Özellikler
- Oda müsaitliği sorgulama 
- Rezervasyon oluşturma ve onaylama
- Müşteri bilgilerini toplama ve doğrulama
- Ödeme seçenekleri sunma
- Rezervasyon değişikliği ve iptali
- Sık sorulan sorulara yanıt verme
- Google Tablolar ile entegrasyon

## 2. Teknoloji Yığını

### Ana Bileşenler
- **WhatsApp Business API**: Müşterilerle iletişim kanalı
- **LangGraph**: Ajan iş akışı ve orkestrasyon
- **DeepSeek (OpenRouter üzerinden)**: Dil işleme ve doğal dil anlama
- **Google Sheets API**: Veri saklama ve yönetim
- **Python**: Temel programlama dili

### Kütüphaneler ve Araçlar
- LangChain & LangGraph: Ajan yapısı ve akış kontrolü
- OpenRouter API: LLM hizmetlerine erişim (DeepSeek)
- gspread / Google API Client: Google Tablolar entegrasyonu
- Flask: API uç noktaları (gerekirse)
- python-dotenv: Ortam değişkenlerinin yönetimi
- logging: Günlük tutma
- pytest: Test otomasyonu

## 3. Ajan Mimarisi

### Ana Ajanlar
1. **Karşılama ve Anlama Ajanı**
   - Müşteri mesajlarını analiz etme
   - Müşteri talebini sınıflandırma
   - Gerekli bilgileri toplama ve doğrulama
   - Akış yönlendirmesi

2. **Rezervasyon Yönetim Ajanı**
   - Müsaitlik kontrolü
   - Fiyat hesaplama
   - Rezervasyon oluşturma
   - Değişiklikler ve iptaller
   - Google Tablolara veri yazma/okuma

3. **İletişim ve Destek Ajanı** (Opsiyonel - ilerleyen aşamalarda)
   - Sık sorulan soruları yanıtlama
   - Sorun çözümü
   - İnsan destek ekibine yönlendirme

### Durum Yönetimi
- Her müşteri etkileşimi için durum takibi
- Konuşma geçmişinin saklanması
- Değişkenlerin ve veri noktalarının tutulması

## 4. Veri Modeli

### Google Tablolar Yapısı
1. **Otel Bilgileri Tablosu**
   - Odalar, tipleri, kapasiteleri
   - Fiyatlar ve sezonlar
   - Politikalar (iptal, değişiklik, vb.)

2. **Müsaitlik Tablosu**
   - Tarih bazlı müsaitlik bilgileri
   - Dolu, boş, bakımda vb. durumlar

3. **Rezervasyonlar Tablosu**
   - Rezervasyon ID
   - Müşteri bilgileri
   - Giriş/çıkış tarihleri
   - Oda tipi ve sayısı
   - Fiyat detayları
   - Durum (onaylandı, iptal edildi, vb.)

4. **Müşteri Tablosu**
   - Müşteri bilgileri
   - İletişim bilgileri
   - Geçmiş rezervasyonlar
   - Tercihler

## 5. Geliştirme Aşamaları

### Aşama 1: Temel Yapı ve Planlama
- Proje mimarisinin oluşturulması
- Gerekli API anahtarlarının alınması
- Ortam değişkenlerinin yapılandırılması
- Google Tablolar şemalarının hazırlanması
- Temel ajanların tasarlanması

### Aşama 2: Karşılama ve Anlama Ajanı Geliştirme
- Temel anlama yeteneklerinin implementasyonu
- Kullanıcı taleplerini sınıflandırma
- İstek türlerine göre veri toplama mantığı
- Akış yönetimi

### Aşama 3: Rezervasyon Yönetim Ajanı Geliştirme
- Google Tablolar entegrasyonu
- Müsaitlik kontrolü
- Fiyat hesaplama
- Rezervasyon oluşturma
- Temel CRUD işlemleri

### Aşama 4: WhatsApp Business API Entegrasyonu
- API bağlantısının kurulması
- Mesaj formatının oluşturulması
- Test etkileşimlerinin yapılması
- Webhook yapılandırması

### Aşama 5: Testler ve İyileştirmeler
- Birim testlerinin yazılması
- Entegrasyon testleri
- Kullanıcı senaryoları testleri
- Performans iyileştirmeleri

### Aşama 6: İleri Özellikler (Opsiyonel)
- İletişim ve Destek Ajanı eklenmesi
- Çoklu dil desteği
- Ödeme entegrasyonu
- Raporlama sistemi

## 6. API Entegrasyonları

### Gemini 
- API konfigürasyonu
- Model parametrelerinin ayarlanması
- Prompt şablonlarının hazırlanması
- Yanıt formatlama

### Google Sheets API
- OAuth2 kimlik doğrulama
- Veri okuma/yazma işlemleri
- Formül ve hesaplamalar
- Hücre formatlaması

## 7. Başarı Metrikleri ve KPI'lar

- Başarılı rezervasyon oranı (tamamlanan/başlatılan)
- Ortalama işlem süresi
- Ajan tarafından çözülen talep yüzdesi
- İnsan müdahalesi gerektiren durum sayısı
- Kullanıcı memnuniyet oranı
- Sistem hata oranı

## 8. Güvenlik ve Veri Koruma

- Kişisel verilerin şifrelenmesi
- API anahtarlarının güvenli yönetimi
- Veri erişim kısıtlamaları
- Günlüklerin anonimleştirilmesi
- KVKK / GDPR uyumluluğu

## 9. İlk Sprint Görevleri

1. Proje yapısını oluştur ve temel dosyaları hazırla
2. Geliştirme ortamını kur (venv, dependencies)
3. OpenRouter API bağlantısını test et
4. Google Sheets bağlantı ve CRUD işlemlerini oluştur
5. Basit prompt şablonlarını geliştir
6. Karşılama ve Anlama Ajanı için prototip oluştur
7. Temel akış grafiğini tanımla
8. Rezervasyon sorgulama senaryosu için test akışı oluştur 