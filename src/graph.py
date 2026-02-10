from langgraph.graph import END, START, StateGraph
from .state import AgentState, SubagentState
from .node import initialize_node, invoke_subagent_node, planner_agent_node, subagent_node
from .edge import spawn_subagent_edge


def create_subgraph():
    subgraph = StateGraph(SubagentState)

    subgraph.add_node("subagent", subagent_node)

    subgraph.add_edge(START, "subagent")
    subgraph.add_edge("subagent", END)

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
