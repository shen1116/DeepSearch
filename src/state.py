from typing import TypedDict, Annotated
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage


def merge_dicts(left: dict, right: dict) -> dict:
    if right == {}:
        return {}
    return {**left, **right}


class AgentState(TypedDict):
    user_input: str
    messages: Annotated[list[BaseMessage], add_messages]
    subagents: dict
    subagent_results: Annotated[dict, merge_dicts]


class SubagentState(TypedDict):
    name: str
    system_prompt: str
    task: str
    tools: list[str]
    result: str
    messages: Annotated[list[BaseMessage], add_messages]
