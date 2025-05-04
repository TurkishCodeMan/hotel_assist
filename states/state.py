from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

# Otel Rezervasyon Ajanları için Durum Sınıfı
class AgentGraphState(TypedDict):
    """
    Otel Rezervasyon ajanları için durum sınıfı.
    TypedDict olarak tanımlanmıştır.
    """
    # Giriş değerleri
    research_question: Annotated[str, add_messages]
    
    # Ajan yanıtları
    memory_injection_response:Annotated[list,add_messages]
    memory_extraction_response: Annotated[list, add_messages]
    reservation_response: Annotated[list, add_messages]
    support_response: Annotated[list, add_messages]


    # İnsan yardımı/müdahalesi için
    human_response: Annotated[list, add_messages]
    messages:Annotated[list,add_messages]

# Durum yardımcı fonksiyonları
def get_agent_graph_state(state: AgentGraphState, state_key: str):
    """
    Ajan grafik durumundan belirli bir değer alır
    
    Args:
        state: Ajan durum nesnesi
        state_key: Alınacak durumun anahtarı ve ek koşullar (_latest veya _all)
        
    Returns:
        Durumun değeri veya boş değer
    """
    # Temel durum değerleri
    if state_key == "research_question":
        return state.get("research_question", "")
    
    # Ajan yanıtları
    if state_key == "memory_extraction_response":
        return state.get("memory_extraction_response", [])
    elif state_key == "memory_extraction_latest":
        return state.get("memory_extraction_response", [])[-1] if state.get("memory_extraction_response") else []
    
    elif state_key == "memory_injection_response":
        return state.get("memory_injection_response", [])
    elif state_key == "memory_injection_latest":
        return state.get("memory_injection_response", [])[-1] if state.get("memory_injection_response") else []

    elif state_key == "reservation_response":
        return state.get("reservation_response", [])
    elif state_key == "reservation_latest":
        return state.get("reservation_response", [])[-1] if state.get("reservation_response") else []
    
    elif state_key == "support_response":
        return state.get("support_response", [])
    elif state_key == "support_latest":
        return state.get("support_response", [])[-1] if state.get("support_response") else []
    
    # İnsan müdahalesi yanıtları
    elif state_key == "human_response":
        return state.get("human_response", [])
    elif state_key == "human_latest":
        return state.get("human_response", [])[-1] if state.get("human_response") else []
    
    # Mesajlar
    elif state_key == "messages":
        return state.get("messages", [])
    elif state_key == "messages_latest":
        return state.get("messages", [])[-1] if state.get("messages") else []
    
    # Diğer durumlar için None döndür
    return None

# Örnek bir durum örneği (test için)
state = {
    "research_question": "",  # Araştırma sorusu
    "memory_extraction_response": [],  # Hafıza çıkarma yanıtları
    "memory_injection_response": [],  # Hafıza enjeksiyon yanıtları
    "reservation_response": [],  # Rezervasyon yanıtları
    "support_response": [],  # Destek yanıtları
    "human_response": [],  # İnsan müdahalesi yanıtları
    "messages": []  # Mesaj geçmişi
}