from .state import AgentState, SubagentState
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
import json_repair
from .tools import TOOLS
from .chat_model import chat_model


def initialize_node(state: AgentState) -> AgentState:
    from .prompt import PLANNER_PROMPT
    state["messages"] = [
        SystemMessage(content=PLANNER_PROMPT)
    ]

    return state

def planner_agent_node(state: AgentState) -> AgentState:
    messages = state["messages"]

    if state.get("subagents") is None or len(state.get("subagents", [])) == 0:
        messages.append(HumanMessage(content=state["user_input"]))
    else:
        subagent_results = [f"Agent: {k}\nResult: {v}\n" for k, v in state.get("subagent_results", {}).items()]
        messages.append(HumanMessage(content="\n".join(subagent_results)))

    llm = chat_model.bind_tools([])
    response = llm.invoke(messages)

    response_json = json_repair.loads(response.content)
    state["subagents"] = response_json["subagents"]
    state["subagent_results"] = {}
    state["messages"] = [response]

    return state
    

def invoke_subagent_node(state: AgentState) -> AgentState:
    subagent_state = {
        "name": state["subagent"]["name"],
        "system_prompt": state["subagent"]["system_prompt"],
        "task": state["subagent"]["task"],
        "tools": state["subagent"]["tools"],
        "result": "",
        "messages": [
            SystemMessage(content=state["subagent"]["system_prompt"]),
            HumanMessage(content=state["subagent"]["task"]),
        ]
    }

    from .graph import create_subgraph
    subgraph = create_subgraph()
    subgraph_output = subgraph.invoke(subagent_state)
    return {
        "subagent_results": {
            state["subagent"]["name"]: subgraph_output["result"]
        }
    }


def subagent_node(state: SubagentState) -> SubagentState:
    messages = state["messages"]

    llm = chat_model.bind_tools([TOOLS[tool] for tool in state["tools"]])
    response = llm.invoke(messages)

    return {
        "result": response.content,
        "messages": [response]
    }

def subagent_tools_node(state: SubagentState) -> SubagentState:
    tool_call_id = state["tool_call_id"]
    tool_name = state["tool_name"]
    tool_args = state["tool_args"]
    tool_result = TOOLS[tool_name].invoke(tool_args)
    return {
        "messages": [ToolMessage(content=tool_result, tool_call_id=tool_call_id)]
    }