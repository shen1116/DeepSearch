from langgraph.graph import END
from langgraph.types import Send
from .state import AgentState, SubagentState

def tools_edge(state: SubagentState):
    tool_calls = state["messages"][-1].tool_calls

    if tool_calls is None or len(tool_calls) == 0:
        return END
    return [
        Send(
            "tools", 
            {
                "tool_call_id": tool_call["id"], 
                "tool_name": tool_call["name"], 
                "tool_args": tool_call["args"]
            }
        ) for tool_call in tool_calls]



def spawn_subagent_edge(state: AgentState):
    if len(state["subagents"]) == 0:
        return END
    main_context = {
        "user_input": state.get("user_input", ""),
        "latest_plan": state.get("new_plan", ""),
        "plan_history": state.get("plan_history", [])[-3:],
        "recent_subagent_results": state.get("subagent_results_history", [])[-2:],
        "recent_subagent_logs": state.get("subagent_logs_history", [])[-2:],
    }
    return [
        Send("invoke_subagent", {"subagent": subagent, "main_context": main_context})
        for subagent in state["subagents"].values()
    ]
