import json
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage

from ..chat_model import chat_model
from ..planner.parsing import safe_parse_json
from ..prompt import SEARCH_FINAL_ANSWER_PROMPT, SEARCH_ROUND_PLANNER_PROMPT, SEARCH_TOOL_SPECS
from ..state import SubagentState
from ..tools import TOOLS

MAX_SEARCH_ROUNDS = 4
MAX_ACTIONS_PER_ROUND = 3


def run_search_agent(state: SubagentState) -> SubagentState:
    task = state["task"]
    main_context = str(state.get("main_context", ""))
    available_tools = _collect_available_tools(state.get("tools", []))
    system_prompt = state["system_prompt"]
    llm = chat_model.bind_tools([])

    rounds: list[dict] = []
    important_info_summary = str(state.get("search_important_info_summary", "")).strip()
    important_info_history = [
        str(item).strip() for item in state.get("search_important_info_history", []) if str(item).strip() != ""
    ]
    final_status = "completed"

    for round_index in range(1, MAX_SEARCH_ROUNDS + 1):
        round_plan = _plan_next_round(
            llm=llm,
            task=task,
            main_context=main_context,
            rounds=rounds,
            important_info_memory=important_info_summary,
        )

        status = str(round_plan.get("status", "search")).strip().lower()
        next_important_info_summary = _extract_important_info_summary(
            raw_summary=round_plan.get("important_info_summary"),
            fallback=important_info_summary,
        )
        if next_important_info_summary != "":
            important_info_summary = next_important_info_summary
            if len(important_info_history) == 0 or important_info_history[-1] != next_important_info_summary:
                important_info_history.append(next_important_info_summary)

        actions: list[dict] = []
        action_results: list[dict] = []
        if status != "done":
            actions = _build_actions(
                raw_actions=round_plan.get("actions"),
                available_tools=available_tools,
            )
            action_results = [_execute_action(action=action) for action in actions]

        round_record = {
            "round":
            round_index,
            "status":
            status,
            "analysis":
            str(round_plan.get("analysis", "")).strip(),
            "knowledge_gaps": [str(item).strip() for item in round_plan.get("knowledge_gaps", [])
                               if str(item).strip() != ""] if isinstance(round_plan.get("knowledge_gaps"), list) else [],
            "important_info_summary":
            important_info_summary,
            "actions":
            actions,
            "action_results":
            action_results,
        }
        rounds.append(round_record)

        if status == "done":
            final_status = "done" if round_index == 1 else "early_stop_done"
            break
    else:
        final_status = "max_rounds_reached"

    final_answer = _finalize_search_answer(
        llm=llm,
        task=task,
        main_context=main_context,
        rounds=rounds,
        important_info_summary=important_info_summary,
        important_info_history=important_info_history,
        system_prompt=system_prompt,
    )

    return {
        "result": final_answer,
        "messages": [AIMessage(content=final_answer)],
        "logs": [{
            "status": final_status,
            "total_rounds": len(rounds)
        }],
        "search_rounds": rounds,
        "search_status": final_status,
        "search_important_info_summary": important_info_summary,
        "search_important_info_history": important_info_history,
    }


def _plan_next_round(
    llm: Any,
    task: str,
    main_context: str,
    rounds: list[dict],
    important_info_memory: str,
) -> dict:
    round_system_prompt = SEARCH_ROUND_PLANNER_PROMPT.format(
        task=task,
        main_context=main_context,
        important_info_memory=important_info_memory if important_info_memory != "" else "暂无已确认的重要信息",
        search_tool_specs=SEARCH_TOOL_SPECS,
    )

    response = llm.invoke([
        SystemMessage(content=round_system_prompt),
    ])

    parsed = safe_parse_json(response.content)
    if not isinstance(parsed, dict) or len(parsed) == 0:
        return {
            "status": "search",
            "analysis": "策略解析失败。",
            "important_info_summary": important_info_memory,
            "knowledge_gaps": ["缺少可解析的策略输出"],
            "actions": [],
        }
    return parsed


def _extract_important_info_summary(raw_summary: Any, fallback: str) -> str:
    if isinstance(raw_summary, str):
        return raw_summary.strip()

    if isinstance(raw_summary, list):
        lines = [str(item).strip() for item in raw_summary if str(item).strip() != ""]
        return "\n".join(lines).strip()

    return fallback.strip()


def _collect_available_tools(tools: Any) -> list[str]:
    if isinstance(tools, list):
        available_tools = []
        for tool in tools:
            if isinstance(tool, str) and tool in TOOLS and tool not in available_tools:
                available_tools.append(tool)
        if len(available_tools) > 0:
            return available_tools

    if "google_search" in TOOLS:
        return ["google_search"]

    if len(TOOLS) > 0:
        return [next(iter(TOOLS.keys()))]

    return []


def _build_actions(raw_actions: Any, available_tools: list[str]) -> list[dict]:
    if not isinstance(raw_actions, list):
        return []

    actions: list[dict] = []
    for raw_action in raw_actions:
        if not isinstance(raw_action, dict):
            continue

        tool_name = str(raw_action.get("tool", "")).strip()
        if tool_name not in available_tools:
            continue

        args = raw_action.get("args", {})
        if not isinstance(args, dict):
            continue

        if tool_name == "google_search":
            query = str(args.get("query", "")).strip()
            if query == "":
                continue
            try:
                num_results = int(args.get("num_results", 5))
            except Exception:
                num_results = 5
            action_args = {"query": query, "num_results": max(1, min(num_results, 10))}
        elif tool_name == "jina_reader":
            url = str(args.get("url", "")).strip()
            if url == "":
                continue
            action_args = {"url": url}
        else:
            continue

        actions.append({
            "tool": tool_name,
            "args": action_args,
            "purpose": str(raw_action.get("purpose", "")).strip(),
        })

    return actions[:MAX_ACTIONS_PER_ROUND]


def _execute_action(action: dict) -> dict:
    tool_name = action["tool"]
    args = action["args"]
    purpose = action.get("purpose", "")

    try:
        tool_output = TOOLS[tool_name].invoke(args)
        output = json.loads(tool_output) if isinstance(tool_output, str) else tool_output
        if not isinstance(output, dict):
            output = {"raw": str(tool_output)}
        return {
            "tool": tool_name,
            "purpose": purpose,
            "args": args,
            "ok": True,
            "output": output,
        }
    except Exception as error:
        return {
            "tool": tool_name,
            "purpose": purpose,
            "args": args,
            "ok": False,
            "error": str(error),
        }


def _finalize_search_answer(
    llm: Any,
    task: str,
    main_context: str,
    rounds: list[dict],
    important_info_summary: str,
    important_info_history: list[str],
    system_prompt: str,
) -> str:
    final_system_prompt = (f"{system_prompt}\n\n" + SEARCH_FINAL_ANSWER_PROMPT.format(
        task=task,
        main_context=main_context if main_context != "" else "暂无主上下文",
        important_info_summary=(important_info_summary if important_info_summary != "" else "暂无已确认的重要信息"),
        important_info_history_json=json.dumps(important_info_history, ensure_ascii=False),
        total_rounds=len(rounds),
        search_rounds_json=json.dumps(rounds, ensure_ascii=False),
    ))
    response = llm.invoke([
        SystemMessage(content=final_system_prompt),
    ])
    return response.content
