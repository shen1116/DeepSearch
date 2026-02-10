from typing import TypedDict, Annotated
from typing_extensions import NotRequired
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage


def merge_dicts(left: dict, right: dict) -> dict:
    if right == {}:
        return {}
    return {**left, **right}


class AgentState(TypedDict):
    user_input: str
    messages: NotRequired[Annotated[list[BaseMessage], add_messages]]
    subagents: NotRequired[dict]
    subagent_results: NotRequired[Annotated[dict, merge_dicts]]
    subagent_logs: NotRequired[Annotated[dict, merge_dicts]]
    new_plan: NotRequired[str]
    important_info_summary: NotRequired[str]
    plan_history: NotRequired[list[str]]
    important_info_history: NotRequired[list[str]]
    subagents_history: NotRequired[list[dict]]
    subagent_results_history: NotRequired[list[dict]]
    subagent_logs_history: NotRequired[list[dict]]
    subagent: NotRequired[dict]
    main_context: NotRequired[dict]


class SubagentState(TypedDict):
    name: str
    system_prompt: str
    task: str
    tools: list[str]
    result: str
    messages: Annotated[list[BaseMessage], add_messages]
    main_context: NotRequired[str]
    logs: NotRequired[list[dict]]
    search_rounds: NotRequired[list[dict]]
    search_status: NotRequired[str]
    search_important_info_summary: NotRequired[str]
    search_important_info_history: NotRequired[list[str]]
    tool_call_id: NotRequired[str]
    tool_name: NotRequired[str]
    tool_args: NotRequired[dict]
