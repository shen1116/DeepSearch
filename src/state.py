from typing import TypedDict, Annotated
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage
import operator


def merge_dicts(left: dict, right: dict) -> dict:
    if right == {}:
        return {}
    return {**left, **right}


class AgentState(TypedDict):
    problem: str
    plan: str
    subagents: dict
    subagent_responses: Annotated[dict, merge_dicts]
    key_info: str


class SubagentState(TypedDict):
    id: str
    name: str
    task: str
    result: str
    tools: list[str]
    messages: Annotated[list[BaseMessage], add_messages]
