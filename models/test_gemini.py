# test_gemini.py
import sys
import os
# Ana dizini import yoluna ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
import json
from models.llm import GeminiModel, GeminiJSONModel
from dotenv import load_dotenv

# Logging yapılandırması
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# .env dosyasından API anahtarını yükle
load_dotenv()

def test_gemini_standard():
    """Standart Gemini modelini test eder"""
    try:
        # Normal model örneği oluştur
        model = GeminiModel(temperature=0.5)
        
        # Test mesajları
        messages = [
            {"role": "system", "content": "Sen yardımcı bir asistansın."},
            {"role": "user", "content": "Merhaba, bugün nasılsın?"}
        ]
        
        # Model yanıtını al
        response = model.invoke(messages)
        
        print("=== STANDART MODEL TESTİ ===")
        print(f"Soru: {messages[1]['content']}")
        print(f"Yanıt: {response.content}")
        print("===========================\n")
        
        return True
    except Exception as e:
        print(f"Standart model testi başarısız: {str(e)}")
        return False

def test_gemini_json():
    """JSON formatında çıktı veren Gemini modelini test eder"""
    try:
        # JSON model örneği oluştur
        json_model = GeminiJSONModel(temperature=0.5)
        
        # Test mesajları - JSON formatında çıktı isteyen bir sistem promptu içerir
        messages = [
            {"role": "system", "content": """Sen bir otel rezervasyon asistanısın. 
            Lütfen aşağıdaki JSON formatında yanıt ver:
            ```json
            {
              "request_type": "booking",
              "missing_information": ["check_in_date"],
              "needs_clarification": true
            }
            ```"""},
            {"role": "user", "content": "Oda rezervasyonu yapmak istiyorum."}
        ]
        
        # Model yanıtını al
        response = json_model.invoke(messages)
        
        print("=== JSON MODEL TESTİ ===")
        print(f"Soru: {messages[1]['content']}")
        print(f"Yanıt: {response.content}")
        
        # JSON olarak ayrıştırmayı dene
        try:
            json_start = response.content.find("{")
            json_end = response.content.rfind("}")
            
            if json_start >= 0 and json_end >= 0:
                json_str = response.content[json_start:json_end+1]
                parsed_json = json.loads(json_str)
                print("JSON ayrıştırma başarılı:")
                print(json.dumps(parsed_json, indent=2, ensure_ascii=False))
                
                # JSON'da gerekli anahtarlar var mı kontrol et
                required_keys = ["request_type", "needs_clarification"]
                missing_keys = [key for key in required_keys if key not in parsed_json]
                
                if missing_keys:
                    print(f"Uyarı: JSON'da eksik anahtarlar var: {missing_keys}")
                else:
                    print("Tüm gerekli anahtarlar mevcut.")
            else:
                print("Yanıtta geçerli bir JSON bulunamadı!")
        except json.JSONDecodeError:
            print("JSON ayrıştırma hatası: Yanıt geçerli bir JSON formatında değil!")
            
        print("=======================\n")
        
        return True
    except Exception as e:
        print(f"JSON model testi başarısız: {str(e)}")
        return False

if __name__ == "__main__":
    print("Gemini LLM modellerini test ediliyor...\n")
    
    standard_test = test_gemini_standard()
    json_test = test_gemini_json()
    
    if standard_test and json_test:
        print("Tüm testler başarıyla tamamlandı! ✅")
    else:
        print("Bazı testler başarısız oldu! ❌") 