from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from .chat_model import chat_model
from .planner import extract_planner_response_state
from .state import AgentState, SubagentState
from .subagents import (
    SEARCH_AGENT_NAME,
    build_main_context_text,
    normalize_subagent_system_prompt,
    normalize_subagent_tools,
    run_search_agent,
)
from .tools import TOOLS


def initialize_node(state: AgentState) -> AgentState:
    from .prompt import PLANNER_PROMPT

    state["messages"] = [
        SystemMessage(
            content=PLANNER_PROMPT.substitute(
                problem=state["user_input"],
                important_info_memory="暂无已确认的重要信息",
            )
        )
    ]
    state["new_plan"] = ""
    state["important_info_summary"] = ""
    state["subagents"] = {}
    state["subagent_results"] = {}
    state["subagent_logs"] = {}
    state["plan_history"] = []
    state["important_info_history"] = []
    state["subagents_history"] = []
    state["subagent_results_history"] = []
    state["subagent_logs_history"] = []

    return state


def planner_agent_node(state: AgentState) -> AgentState:
    messages = state["messages"]
    subagent_results = state.get("subagent_results", {})
    subagent_logs = state.get("subagent_logs", {})
    current_important_info = str(state.get("important_info_summary", "")).strip()

    if current_important_info != "":
        messages.append(HumanMessage(content=f"<KEY_INFO_MEMORY>\n{current_important_info}\n</KEY_INFO_MEMORY>"))

    if state.get("subagents") is not None and len(state.get("subagents", [])) != 0:
        subagent_response_messages = [f"Agent: {k}\nResult: {v}\n" for k, v in subagent_results.items()]
        messages.append(HumanMessage(content="\n".join(subagent_response_messages)))

    llm = chat_model.bind_tools([])
    response = llm.invoke(messages)

    parsed_response = extract_planner_response_state(response.content, tools_registry=TOOLS)
    new_plan = parsed_response["new_plan"]
    next_subagents = parsed_response["subagents"]
    next_important_info = str(parsed_response.get("important_info_summary", "")).strip()

    if len(subagent_results) > 0:
        state["subagent_results_history"] = state.get("subagent_results_history", []) + [dict(subagent_results)]
    if len(subagent_logs) > 0:
        state["subagent_logs_history"] = state.get("subagent_logs_history", []) + [dict(subagent_logs)]
    if new_plan != "":
        state["plan_history"] = state.get("plan_history", []) + [new_plan]
    if next_important_info != "":
        state["important_info_history"] = state.get("important_info_history", []) + [next_important_info]
    if len(next_subagents) > 0:
        state["subagents_history"] = state.get("subagents_history", []) + [dict(next_subagents)]

    state["new_plan"] = new_plan
    if next_important_info != "":
        state["important_info_summary"] = next_important_info
    state["subagents"] = next_subagents
    state["subagent_results"] = {}
    state["subagent_logs"] = {}
    state["messages"] = messages + [response]

    return state


def invoke_subagent_node(state: AgentState) -> AgentState:
    subagent = state["subagent"]
    subagent_id = subagent.get("id") or subagent["name"]

    subagent_tools = normalize_subagent_tools(
        name=subagent["name"],
        raw_tools=subagent.get("tools"),
        tools_registry=TOOLS,
    )
    subagent_system_prompt = normalize_subagent_system_prompt(
        name=subagent["name"],
        raw_system_prompt=subagent.get("system_prompt"),
    )
    main_context_text = build_main_context_text(
        main_context=state.get("main_context"),
        subagent_context=subagent.get("context"),
    )

    subagent_state = {
        "name":
        subagent["name"],
        "system_prompt":
        subagent_system_prompt,
        "task":
        subagent["task"],
        "tools":
        subagent_tools,
        "main_context":
        main_context_text,
        "logs": [],
        "search_rounds": [],
        "search_status":
        "",
        "search_important_info_summary":
        "",
        "search_important_info_history":
        [],
        "result":
        "",
        "messages": [
            SystemMessage(content=subagent_system_prompt),
            HumanMessage(content=f"<TASK>\n{subagent['task']}\n</TASK>\n\n{main_context_text}"),
        ],
    }

    if subagent["name"] == SEARCH_AGENT_NAME:
        search_output = run_search_agent(subagent_state)
        search_log = {
            "agent": subagent["name"],
            "status": search_output.get("search_status", ""),
            "round_count": len(search_output.get("search_rounds", [])),
            "rounds": search_output.get("search_rounds", []),
            "important_info_summary": search_output.get("search_important_info_summary", ""),
            "important_info_history": search_output.get("search_important_info_history", []),
            "trace": search_output.get("logs", []),
        }
        return {
            "subagent_results": {
                subagent_id: search_output["result"]
            },
            "subagent_logs": {
                subagent_id: search_log
            },
        }

    from .graph import create_subgraph

    subgraph = create_subgraph()
    subgraph_output = subgraph.invoke(subagent_state)
    generic_log = {
        "agent": subagent["name"],
        "status": "completed",
        "round_count": 1,
        "trace": [{
            "phase": "single_pass",
            "message_count": len(subgraph_output.get("messages", []))
        }],
    }
    return {
        "subagent_results": {
            subagent_id: subgraph_output["result"]
        },
        "subagent_logs": {
            subagent_id: generic_log
        },
    }


def subagent_node(state: SubagentState) -> SubagentState:
    messages = state["messages"]

    llm = chat_model.bind_tools([])
    response = llm.invoke(messages)

    return {"result": response.content, "messages": [response]}


def subagent_tools_node(state: SubagentState) -> SubagentState:
    tool_call_id = state["tool_call_id"]
    tool_name = state["tool_name"]
    tool_args = state["tool_args"]
    tool_result = TOOLS[tool_name].invoke(tool_args)
    return {"messages": [ToolMessage(content=tool_result, tool_call_id=tool_call_id)]}
