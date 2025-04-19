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
    understanding_response: Annotated[list, add_messages]
    reservation_response: Annotated[list, add_messages]
    support_response: Annotated[list, add_messages]
    
    # Google Sheets Tool araç yanıtları
    reservations_result: Annotated[list, add_messages]  # Tüm rezervasyon listesi
    add_reservation_result: Annotated[list, add_messages]  # Rezervasyon ekleme sonucu
    update_reservation_result: Annotated[list, add_messages]  # Rezervasyon güncelleme sonucu
    delete_reservation_result: Annotated[list, add_messages]  # Rezervasyon silme sonucu
    
    # Tool istekleri için geçici veri alanları
    reservation_query: Annotated[list, add_messages]  # Rezervasyon sorgulama parametreleri
    new_reservation: Annotated[list, add_messages]  # Yeni rezervasyon verileri
    update_reservation: Annotated[list, add_messages]  # Güncelleme verileri
    delete_reservation: Annotated[list, add_messages]  # Silme parametreleri
    availability_check: Annotated[list, add_messages]  # Müsaitlik kontrol parametreleri
    
    # İnsan yardımı/müdahalesi için
    human_response: Annotated[list, add_messages]

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
    if state_key == "understanding_all":
        return state["understanding_response"]
    elif state_key == "understanding_latest":
        if state["understanding_response"]:
            return state["understanding_response"][-1]
        else:
            return state["understanding_response"]
    
    elif state_key == "reservation_all":
        return state["reservation_response"]
    elif state_key == "reservation_latest":
        if state["reservation_response"]:
            return state["reservation_response"][-1]
        else:
            return state["reservation_response"]
    
    elif state_key == "support_all":
        return state["support_response"]
    elif state_key == "support_latest":
        if state["support_response"]:
            return state["support_response"][-1]
        else:
            return state["support_response"]
    
    
    # Google Sheets - Rezervasyon listesi sonuçları
    elif state_key == "reservations_result":
        return state.get("reservations_result", [])
    elif state_key == "reservations_result_all":
        return state.get("reservations_result", [])
    elif state_key == "reservations_result_latest":
        if state.get("reservations_result", []):
            return state["reservations_result"][-1]
        else:
            return state.get("reservations_result", [])
    
    # Google Sheets - Rezervasyon ekleme sonuçları
    elif state_key == "add_reservation_result":
        return state.get("add_reservation_result", [])
    elif state_key == "add_reservation_result_all":
        return state.get("add_reservation_result", [])
    elif state_key == "add_reservation_result_latest":
        if state.get("add_reservation_result", []):
            return state["add_reservation_result"][-1]
        else:
            return state.get("add_reservation_result", [])
    
    # Google Sheets - Rezervasyon güncelleme sonuçları
    elif state_key == "update_reservation_result":
        return state.get("update_reservation_result", [])
    elif state_key == "update_reservation_result_all":
        return state.get("update_reservation_result", [])
    elif state_key == "update_reservation_result_latest":
        if state.get("update_reservation_result", []):
            return state["update_reservation_result"][-1]
        else:
            return state.get("update_reservation_result", [])
    
    # Google Sheets - Rezervasyon silme sonuçları
    elif state_key == "delete_reservation_result":
        return state.get("delete_reservation_result", [])
    elif state_key == "delete_reservation_result_all":
        return state.get("delete_reservation_result", [])
    elif state_key == "delete_reservation_result_latest":
        if state.get("delete_reservation_result", []):
            return state["delete_reservation_result"][-1]
        else:
            return state.get("delete_reservation_result", [])
    
    # Tool istekleri için geçici veri alanları
    elif state_key == "reservation_query":
        return state.get("reservation_query", [])
    elif state_key == "new_reservation":
        return state.get("new_reservation", [])
    elif state_key == "update_reservation":
        return state.get("update_reservation", [])
    elif state_key == "delete_reservation":
        return state.get("delete_reservation", [])
    elif state_key == "availability_check":
        return state.get("availability_check", [])
    
    # İnsan müdahalesi yanıtları
    elif state_key == "human_all":
        return state.get("human_response", [])
    elif state_key == "human_latest":
        if state.get("human_response", []):
            return state["human_response"][-1]
        else:
            return state.get("human_response", [])
    
    else:
        return None

# Örnek bir durum örneği (test için)
state = {
    "research_question": "",
    "understanding_response": [],
    "reservation_response": [],
    "support_response": [],
    "reservations_result": [],
    "add_reservation_result": [],
    "update_reservation_result": [],
    "delete_reservation_result": [],
    "reservation_query": [],
    "new_reservation": [],
    "update_reservation": [],
    "delete_reservation": [],
    "availability_check": [],
    "human_response": [],
}