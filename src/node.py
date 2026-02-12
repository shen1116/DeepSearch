from .state import AgentState, SubagentState
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
import json_repair
from .tools import TOOLS
from .chat_model import chat_model


def initialize_node(state: AgentState) -> AgentState:
    state["plan"] = ""
    state["subagents"] = {}
    state["subagent_responses"] = {}
    state["key_info"] = ""
    return state

def planner_agent_node(state: AgentState) -> AgentState:

    # 1. 构造 system_prompt
    from .agents.planner import SYSTEM_PROMPT
    system_prompt = SYSTEM_PROMPT.substitute(
        problem=state["problem"],
        plan=state["plan"],
        subagent_responses=state["subagent_responses"],
        key_info=state["key_info"]
    )
    messages = [SystemMessage(content=system_prompt)]

    # 2. 调用 llm
    llm = chat_model.bind_tools([])
    response = llm.invoke(messages)

    # 3. 解析 response，得到
    from .parser import extract_planner_response_state
    parsed = extract_planner_response_state(response.content)

    # 4. 更新 state
    state["plan"] = parsed["plan"]
    state["subagents"] = parsed["subagents"]
    state["key_info"] = parsed["key_info"]
    return state
    

def invoke_subagent_node(state: AgentState) -> AgentState:
    from .agents.search import SEARCH_AGENT_NAME

    # 1. 构造 system_prompt
    subagent_name = state["subagent"]["name"]
    system_prompt = ""
    if subagent_name == SEARCH_AGENT_NAME:
        from .agents.search import SEARCH_AGENT_SYSTEM_PROMPT
        system_prompt = SEARCH_AGENT_SYSTEM_PROMPT.substitute(task=state["subagent"]["task"])

    # 2. 选择 tools
    tools = []
    if subagent_name == SEARCH_AGENT_NAME:
        from .agents.search import SEARCH_AGENT_DEFAULT_TOOLS
        tools = SEARCH_AGENT_DEFAULT_TOOLS

    # 3. 构造 subagent state
    subagent_state = {
        "id": state["subagent"]["id"],
        "name": subagent_name,
        "task": state["subagent"]["task"],
        "tools": tools,
        "result": "",
        "messages": [
            SystemMessage(content=system_prompt),
        ]
    }

    # 4. 调用 subagent
    from .graph import create_subgraph
    subgraph = create_subgraph()
    subgraph_output = subgraph.invoke(subagent_state)
    return {
        "subagent_responses": {
            subgraph_output["id"]: subgraph_output["result"]
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