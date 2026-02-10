from langgraph.graph import StateGraph
from .state import AgentState, SubagentState
from .node import initialize_node, planner_agent_node, subagent_node, invoke_subagent_node, subagent_tools_node
from langgraph.graph import START
from .edge import tools_edge, spawn_subagent_edge


def create_subgraph():
    subgraph = StateGraph(SubagentState)

    subgraph.add_node("subagent", subagent_node)
    subgraph.add_node("tools", subagent_tools_node)

    subgraph.add_edge(START, "subagent")
    subgraph.add_conditional_edges("subagent", tools_edge)
    subgraph.add_edge("tools", "subagent")

    return subgraph.compile()


def create_graph():
    graph = StateGraph(AgentState)

    graph.add_node("initialize", initialize_node)
    graph.add_node("planner_agent", planner_agent_node)
    graph.add_node("invoke_subagent", invoke_subagent_node)

    graph.add_edge(START, "initialize")
    graph.add_edge("initialize", "planner_agent")
    graph.add_conditional_edges("planner_agent", spawn_subagent_edge)
    graph.add_edge("invoke_subagent", "planner_agent")

    return graph.compile()
