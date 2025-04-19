# Altıkulaç Otel Rezervasyon Sistemi - Geliştirici Kılavuzu

Bu kılavuz, Altıkulaç Otel Rezervasyon Sistemi projesi üzerinde geliştirme yapmak isteyen geliştiriciler için hazırlanmıştır. Kurulum adımları, kodlama standartları ve katkı sağlama süreci hakkında bilgi verir.

## 1. Geliştirme Ortamı Kurulumu

### 1.1 Ön Koşullar

- Python 3.10 veya üzeri
- pip (Python paket yöneticisi)
- Git
- VSCode veya tercih ettiğiniz bir IDE

### 1.2 Projeyi Klonlama

```bash
git clone https://github.com/kullanici/altikulac-otel-asistani.git
cd altikulac-otel-asistani
```

### 1.3 Sanal Ortam Oluşturma

```bash
# Sanal ortam oluştur
python -m venv venv

# Sanal ortamı etkinleştir
# Windows için:
venv\Scripts\activate
# MacOS/Linux için:
source venv/bin/activate
```

### 1.4 Bağımlılıkları Kurma

```bash
pip install -r requirements.txt
```

### 1.5 Ortam Değişkenlerini Yapılandırma

Proje kök dizininde `.env` dosyası oluşturun ve aşağıdaki değişkenleri ekleyin:

```
GEMINI_API_KEY=your_gemini_api_key
GOOGLE_APPLICATION_CREDENTIALS=./google_credentials.json
```

### 1.6 Google Sheets API Kimlik Bilgilerini Ayarlama

1. [Google Cloud Console](https://console.cloud.google.com/)'a gidin
2. Yeni bir proje oluşturun veya mevcut bir projeyi seçin
3. Google Sheets API'yi etkinleştirin
4. Servis hesabı kimlik bilgilerini oluşturun
5. JSON kimlik bilgilerini indirin ve `google_credentials.json` olarak kaydedin

## 2. Projeyi Çalıştırma

### 2.1 MCP Sunucusunu Başlatma

```bash
# Ayrı bir terminal penceresinde
source venv/bin/activate
cd google-sheets-mcp
python sheet.py
```

### 2.2 Streamlit Uygulamasını Başlatma

```bash
source venv/bin/activate
streamlit run streamlit_fix.py
```

Uygulama varsayılan olarak `http://localhost:8501` adresinde çalışacaktır.

## 3. Kod Yapısı ve Organizasyonu

### 3.1 Klasör Yapısı

- `agent_graph/`: LangGraph ajan grafikleri
- `agents/`: Ajan sınıfları ve mantık
- `models/`: LLM modelleri ve entegrasyonları
- `prompts/`: Sistem ve kullanıcı promptları
- `states/`: Durum nesneleri ve yönetimi
- `utils/`: Yardımcı fonksiyonlar
- `docs/`: Dokümantasyon dosyaları
- `tests/`: Test dosyaları
- `google-sheets-mcp/`: Google Sheets MCP sunucusu

### 3.2 Anahtar Dosyalar

- `streamlit_fix.py`: Ana uygulama giriş noktası
- `agent_graph/graph.py`: LangGraph akış tanımı
- `agents/agents.py`: Temel ajan sınıfları
- `models/llm.py`: Gemini AI entegrasyonu
- `prompts/prompts.py`: Sistem promptları
- `google-sheets-mcp/sheet.py`: MCP sunucusu

## 4. Geliştirme İş Akışı

### 4.1 Yeni Özellik Geliştirme

1. Ana repoyu güncel tutun: `git pull origin main`
2. Yeni bir dal oluşturun: `git checkout -b feature/yeni-ozellik`
3. Değişikliklerinizi yapın
4. Testleri çalıştırın: `pytest`
5. Değişikliklerinizi commit edin: `git commit -m "Yeni özellik: açıklama"`
6. Dalınızı push edin: `git push origin feature/yeni-ozellik`
7. Pull Request oluşturun

### 4.2 Hata Düzeltme

1. Ana repoyu güncel tutun: `git pull origin main`
2. Yeni bir dal oluşturun: `git checkout -b fix/hata-aciklamasi`
3. Düzeltmenizi yapın
4. Testleri çalıştırın: `pytest`
5. Değişikliklerinizi commit edin: `git commit -m "Düzeltme: hata açıklaması"`
6. Dalınızı push edin: `git push origin fix/hata-aciklamasi`
7. Pull Request oluşturun

## 5. Kodlama Standartları

### 5.1 Python Stil Kılavuzu

Proje, [PEP 8](https://www.python.org/dev/peps/pep-0008/) stil kılavuzunu takip eder:

- 4 boşluk girintileme (tab değil)
- Satır uzunluğu maksimum 88 karakter
- Modül/sınıf/fonksiyon adları için snake_case
- Sınıflar için CamelCase
- Sabitler için UPPER_CASE

### 5.2 Dokümantasyon Standartları

- Her modül, sınıf ve fonksiyon için docstring ekleyin
- [Google docstring formatını](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html) kullanın
- Karmaşık kod bloklarını açıklayan yorumlar ekleyin

Örnek:
```python
def process_reservation(data: dict) -> dict:
    """
    Rezervasyon verilerini işler ve formatlar.
    
    Args:
        data: İşlenecek ham rezervasyon verisi.
        
    Returns:
        İşlenmiş ve formatlanmış rezervasyon verisi.
        
    Raises:
        ValueError: Eksik zorunlu alanlar olduğunda.
    """
    # Fonksiyon implementasyonu...
```

### 5.3 Commit Mesajı Kuralları

Commit mesajları için aşağıdaki formatı kullanın:

```
<tip>: <kısa açıklama>

<detaylı açıklama>
```

Tipler:
- feat: Yeni özellik
- fix: Hata düzeltmesi
- docs: Sadece dokümantasyon değişiklikleri
- style: Kod davranışını etkilemeyen değişiklikler (boşluk, biçimlendirme, vb.)
- refactor: Hata düzeltmesi veya özellik eklemeyen kod değişikliği
- test: Test eklemek veya var olanları düzeltmek
- chore: Yapı değişiklikleri, bağımlılık güncellemeleri vb.

## 6. Mimari Değişiklikler

### 6.1 Yeni Ajanlar Ekleme

Yeni bir ajan eklemek için:

1. `agents/` klasöründe yeni bir sınıf oluşturun
2. `Agent` sınıfından miras alın
3. `invoke` metodunu override edin
4. `agent_graph/graph.py` dosyasında gerekli değişiklikleri yapın

### 6.2 Yeni Araçlar Ekleme

Yeni bir MCP aracı eklemek için:

1. `google-sheets-mcp/sheet.py` dosyasında yeni fonksiyonu tanımlayın
2. MCP sınıfına yeni fonksiyonu ekleyin
3. Dokümantasyonu `docs/MCP_TOOLS.md` dosyasında güncelleyin

### 6.3 Prompt Şablonlarını Değiştirme

Prompt şablonları değiştirmek için:

1. `prompts/prompts.py` dosyasında ilgili şablonu güncelleyin
2. Değişikliğin etkisini test edin
3. Dokümantasyonu güncelleyin

## 7. Test Stratejisi

### 7.1 Birim Testleri

Birim testleri `tests/` klasörü altında bulunur ve her modül için ayrı test dosyaları içerir:

```
tests/
  ├── test_agents.py
  ├── test_llm.py
  ├── test_utils.py
  └── ...
```

Birim testi yazmak için `pytest` kullanın:

```python
def test_reservation_formatting():
    # Test kodu...
    assert result == expected
```

### 7.2 Entegrasyon Testleri

Entegrasyon testleri, bileşenlerin birlikte çalışmasını kontrol eder:

```python
def test_reservation_flow():
    # Test kodu...
    assert result == expected
```

### 7.3 Test Çalıştırma

```bash
# Tüm testleri çalıştır
pytest

# Belirli bir test dosyasını çalıştır
pytest tests/test_agents.py

# Belirli bir testi çalıştır
pytest tests/test_agents.py::test_reservation_agent
```

## 8. Sorun Giderme

### 8.1 Yaygın Hatalar ve Çözümleri

- **MCP Bağlantı Hataları**: MCP sunucusunun çalıştığından emin olun
- **API Anahtar Hataları**: `.env` dosyasında API anahtarlarını kontrol edin
- **Gemini API Hataları**: API limitleri ve model parametrelerini kontrol edin
- **JSON Ayrıştırma Hataları**: LLM yanıtlarının formatını kontrol edin

### 8.2 Loglama

Sistemin davranışını anlamak için logları kullanın:

```python
import logging
logger = logging.getLogger(__name__)

# Log seviyelerini kullanma
logger.debug("Ayrıntılı teknik bilgi")
logger.info("Genel bilgi")
logger.warning("Uyarı")
logger.error("Hata")
logger.critical("Kritik hata")
```

## 9. Performans İpuçları

### 9.1 Ajan Optimizasyonu

- Ajan sayısını minimum tutun (basit akış)
- LLM çağrı sayısını azaltın
- Durumu verimli yönetin

### 9.2 MCP Optimizasyonu

- Uzun süreli bağlantılar için bağlantı havuzu kullanın
- Hata durumlarında otomatik yeniden deneme mekanizmaları ekleyin
- Sık kullanılan veri için önbellek kullanın

### 9.3 LLM Optimizasyonu

- Prompt mühendisliğini optimize edin
- Gereksiz bağlam paylaşımını sınırlayın
- Token kullanımını azaltmak için mesaj geçmişini özetleyin

## 10. Katkı Sağlama

Proje daha iyi hale getirmek için katkılarınızı bekliyoruz! İşte katkı sağlamanın bazı yolları:

1. Hata raporlama
2. Yeni özellik önerileri
3. Dokümantasyon iyileştirmeleri
4. Kod iyileştirmeleri ve optimizasyonlar
5. Test kapsamını artırma

Herhangi bir sorunuz varsa, `@gelistirici_kullanici` ile iletişime geçebilirsiniz. 