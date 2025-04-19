import json
import logging
from typing import Any
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph

from agents.agents import ReservationAgent
from agents.tools_agents import (
    EndNodeAgent
)
from states.state import AgentGraphState
from prompts.prompts import RESERVATION_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

def create_graph(server=None, model=None, stop=None, model_endpoint=None, temperature=0.5, tools=None, session=None):
    graph = StateGraph(AgentGraphState)

    # ----- Async Düğümler -----
    async def reservation_agent_node(state):
        return await ReservationAgent(
            state=state,
            model=model,
            server=server,
            model_endpoint=model_endpoint,
            stop=stop,
            guided_json=None,
            temperature=temperature,
            session=session,
        ).invoke(
            research_question=state['research_question'],
            conversation_state=state,
            prompt=RESERVATION_SYSTEM_PROMPT,
            tools=tools,
            feedback=state['reservation_response'],
        )

    async def end_node(state):
        return await EndNodeAgent(
            state=state,
            model=model,
            server=server
        ).invoke()

    # ----- Düğümleri ekle -----
    graph.add_node("reservation_agent", reservation_agent_node)

    graph.add_node("end", end_node)

    # Giriş ve çıkış noktaları
    graph.set_entry_point("reservation_agent")
    graph.set_finish_point("end")


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