import json
import logging
from typing import Any, Dict, List, Optional
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph

from agents.agents import ReservationAgent, MemoryExtractionAgent, MemoryInjectionAgent
from agents.tools_agents import (
    EndNodeAgent
)
from states.state import AgentGraphState
from prompts.prompts import RESERVATION_SYSTEM_PROMPT, MEMORY_ANALYSIS_PROMPT
from utils.vector_store import get_vector_store

logger = logging.getLogger(__name__)

def create_graph(server=None, model=None, stop=None, model_endpoint=None, temperature=0.5, session=None, agent_mcp_config=None):
    """LangGraph oluşturur
    
    Args:
        server: LLM sunucusu (gemini, groq vb.)
        model: Kullanılacak model
        stop: Durdurma belirteçleri
        model_endpoint: Model endpoint URL'si
        temperature: Sıcaklık değeri
        tools: MCP araçları listesi (artık agent_mcp_config içinde)
        session: MCP oturumu (artık agent_mcp_config içinde)
        agent_mcp_config: Ajan-MCP eşleştirme yapılandırması (opsiyonel)
    
    Returns:
        StateGraph: Oluşturulan graf
    """
    graph = StateGraph(AgentGraphState)
    
    # Varsayılan agent-MCP yapılandırması
    # MemoryInjectionAgent için de varsayılanlar eklenebilir
    default_agent_config = {
        "reservation_agent": {
            "server": server,
            "model": model,
            "model_endpoint": model_endpoint,
            "tools": None, # Araçlar ilgili agent'a özel olmalı
            "session": session # Session ilgili agent'a özel olmalı
        },
        "memory_extraction_agent": {
            "server": "groq", # Hafıza çıkarımı için farklı model/server
            "model": "llama-3.1-8b-instant",
            "model_endpoint": model_endpoint,
            "tools": None,
            "session": None # Hafıza çıkarımının kendi session'ı olmayabilir
        },
        "memory_injection_agent": {
            "server": server, # Anı analizi için ana modeli kullanabilir
            "model": model, 
            "model_endpoint": model_endpoint,
            "tools": None,
            "session": None # Session gerektirmez
        }
    }
    
    # Verilen yapılandırma ile varsayılanı birleştir
    agent_config = default_agent_config
    if agent_mcp_config:
        for agent_name, config in agent_mcp_config.items():
            if agent_name in agent_config:
                # Mevcut config üzerine yazarken None değerlerini atlama
                merged_config = {k: v for k, v in config.items() if v is not None}
                agent_config[agent_name].update(merged_config)
            else:
                agent_config[agent_name] = config

    # ----- Async Düğümler ------
    async def reservation_agent_node(state):
        cfg = agent_config.get("reservation_agent", {})
        # Reservation agent'a state içindeki memory context'i de verebiliriz
        # Örneğin prompt'a ekleyerek:
        # memory_ctx = state.get("retrieved_memories_context", "")
        # formatted_prompt = RESERVATION_SYSTEM_PROMPT.format(..., memory_context=memory_ctx)
        return await ReservationAgent(
            state=state,
            model=cfg.get("model", model),
            server=cfg.get("server", server),
            model_endpoint=cfg.get("model_endpoint", model_endpoint),
            stop=stop,
            guided_json=None,
            temperature=temperature,
            session=cfg.get("session"), # Agent config'den al
        ).invoke(
            research_question=state.get('research_question'),
            conversation_state=state,
            tools=cfg.get("tools"),
            feedback=state.get('memory_injection_response')
        )
    
    async def memory_extraction_node(state):
        cfg = agent_config.get("memory_extraction_agent", {})
        # cfg loglaması kaldırıldı
        # print(cfg,"cfg") 
        return await MemoryExtractionAgent(
            state=state,
            model=cfg.get("model", model),
            server=cfg.get("server", "groq"),
            model_endpoint=cfg.get("model_endpoint", model_endpoint),
            stop=stop,
            guided_json=None,
            temperature=temperature,
            session=cfg.get("session")
        ).invoke(
            research_question=state.get('research_question'),
            conversation_state=state,
            vector_store=get_vector_store()
        )
        
    # Memory Injection Node
    async def memory_injection_node(state):
        cfg = agent_config.get("memory_injection_agent", {})
        return await MemoryInjectionAgent(
            state=state, # State'i ajana başlatırken ver
            model=cfg.get("model", model),
            server=cfg.get("server", server),
            model_endpoint=cfg.get("model_endpoint", model_endpoint),
            stop=stop,
            guided_json=None,
            temperature=temperature,
            session=cfg.get("session")
        ).invoke(
            vector_store=get_vector_store(),
            num_memories=cfg.get("num_memories", 3),  # Varsayılan 3 anı
            conversation_state=state  # State'i invoke'a geç
        )

    async def end_node(state):
        return await EndNodeAgent(
            state=state,
            model=model,
            server=server
        ).invoke()

    # ----- Düğümleri ekle -----
    graph.add_node("memory_extraction_agent", memory_extraction_node)
    graph.add_node("memory_injection_agent", memory_injection_node) # Yeni düğümü ekle
    graph.add_node("reservation_agent", reservation_agent_node)
    graph.add_node("final_node", end_node)

    # ----- Akış Yönleri (Kenarlar) -----
    graph.set_entry_point("memory_extraction_agent")
    graph.set_finish_point("final_node")
    
    # Güncellenmiş akış:
    # memory_extraction -> memory_injection -> reservation -> final_node
    graph.add_edge("memory_extraction_agent", "memory_injection_agent")
    graph.add_edge("memory_injection_agent", "reservation_agent")
    graph.add_edge("reservation_agent", "final_node")

    # Eski kenar kaldırıldı:
    # graph.add_edge("memory_extraction_agent", "reservation_agent")
  
    return graph

def compile_workflow(graph):
    logger.info("LangGraph derleniyor...")
    return graph.compile()

def build_graph() -> Any:
    try:
        graph = create_graph()
        return compile_workflow(graph)
    except Exception as e:
        logger.error(f"Graph oluşturma hatası: {str(e)}")
        raise