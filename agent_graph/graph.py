import json
import logging
from typing import Any, Dict, List, Optional
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph

from agents.agents import ReservationAgent, MemoryExtractionAgent
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
        tools: MCP araçları listesi
        session: MCP oturumu
        agent_mcp_config: Ajan-MCP eşleştirme yapılandırması (opsiyonel)
    
    Returns:
        StateGraph: Oluşturulan graf
    """
    graph = StateGraph(AgentGraphState)
    
    # Varsayılan agent-MCP yapılandırması
    default_agent_config = {
        "reservation_agent": {
            "server": server,
            "model": model,
            "model_endpoint": model_endpoint,
            "tools": None,
            "session": session
        },
        "memory_extraction_agent": {
            "server": "groq",
            "model": "llama-3.1-8b-instant",  # Groq tarafından desteklenen bir model
            "model_endpoint": model_endpoint,
            "tools": None,
            "session": None
        }
    }
    
    # Verilen yapılandırma ile varsayılanı birleştir (verilen değerler önceliklidir)
    agent_config = default_agent_config
    if agent_mcp_config:
        for agent_name, config in agent_mcp_config.items():
            if agent_name in agent_config:
                agent_config[agent_name].update(config)
            else:
                agent_config[agent_name] = config

    # ----- Async Düğümler -----
    async def reservation_agent_node(state):
        cfg = agent_config.get("reservation_agent", {})
        return await ReservationAgent(
            state=state,
            model=cfg.get("model", model),
            server=cfg.get("server", server),
            model_endpoint=cfg.get("model_endpoint", model_endpoint),
            stop=stop,
            guided_json=None,
            temperature=temperature,
            session=cfg.get("session", session),
        ).invoke(
            research_question=state['research_question'],
            conversation_state=state,
            prompt=RESERVATION_SYSTEM_PROMPT,
            tools=cfg.get("tools", None),
            feedback=None,
        )
    
    async def memory_extraction_node(state):
        cfg = agent_config.get("memory_extraction_agent", {})
        print(cfg,"cfg")
        return await MemoryExtractionAgent(
            state=state,
            model=cfg.get("model", model),
            server=cfg.get("server", "groq"),  # Memory için varsayılan olarak groq
            model_endpoint=cfg.get("model_endpoint", model_endpoint),
            stop=stop,
            guided_json=None,
            temperature=temperature,
            session=cfg.get("session", session)
        ).invoke(
            research_question=state['research_question'],
            conversation_state=state,
            prompt=MEMORY_ANALYSIS_PROMPT,
            tools=cfg.get("tools", None),
            feedback=None,
            vector_store=get_vector_store()
        )

    async def end_node(state):
        return await EndNodeAgent(
            state=state,
            model=model,
            server=server
        ).invoke()

    # ----- Düğümleri ekle -----
    graph.add_node("reservation_agent", reservation_agent_node)
    graph.add_node("memory_extraction_agent", memory_extraction_node)
    graph.add_node("end", end_node)

    # Giriş ve çıkış noktaları
    graph.set_entry_point("memory_extraction_agent")
    graph.set_finish_point("end")
    
    # MemoryExtractionAgent'tan ReservationAgent'a kenar ekle
    graph.add_edge("memory_extraction_agent", "reservation_agent")
    
    # Kenarlar (akış yönleri)
    graph.add_edge("reservation_agent", "end")

  
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