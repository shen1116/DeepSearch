import json
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from ..chat_model import chat_model
from ..planner.parsing import safe_parse_json
from ..state import SubagentState
from ..tools import TOOLS

MAX_SEARCH_ROUNDS = 4
MAX_ACTIONS_PER_ROUND = 3

TOOL_SPECS = """
可用工具及参数（必须严格按下面结构传参）：

1) google_search
- 用途：先检索候选网页
- args:
  - query: str，必填，搜索关键词
  - num_results: int，可选，1-10，建议 3-5
- 示例：
  {"tool":"google_search","args":{"query":"杭州 亚运会 开幕 时间","num_results":5}}

2) jina_reader
- 用途：读取具体网页正文（深读）
- args:
  - url: str，必填，完整的 http/https 链接
- 示例：
  {"tool":"jina_reader","args":{"url":"https://example.com/news"}}
"""

SEARCH_ROUND_PLANNER_PROMPT = f"""你是 SearchAgent 的检索执行规划器。
你的任务是：根据 task、main_context、历史轮次证据，决定本轮是否继续检索，以及调用哪些工具。

{TOOL_SPECS}

请严格输出 JSON 对象，格式如下：
{{
  "status": "search" 或 "done",
  "analysis": "本轮判断",
  "knowledge_gaps": ["仍缺失的信息1", "仍缺失的信息2"],
  "actions": [
    {{
      "tool": "google_search 或 jina_reader",
      "args": {{...}},
      "purpose": "本次调用目的"
    }}
  ]
}}

规则：
1. 若信息不足，status 必须为 "search"，并给出 1-3 个 actions。
2. 若信息已足够回答，status 必须为 "done"，actions 为空列表。
3. 是否使用 jina_reader 由你自行判断；当 snippet 充分时可不深读。
4. 禁止输出 JSON 以外内容。
"""

SEARCH_FINAL_ANSWER_PROMPT = """你是 SearchAgent 的总结器。
请基于任务、上下文和多轮检索证据，输出最终回答。要求：
1. 使用中文。
2. 明确区分“事实结论”和“不确定部分”。
3. 尽量引用证据中的链接（若有）。
4. 输出结构必须是：
   - 任务理解
   - 检索过程摘要
   - 关键证据
   - 最终回答
   - 不确定性与建议
"""


def run_search_agent(state: SubagentState) -> SubagentState:
    task = state["task"]
    main_context = str(state.get("main_context", ""))
    available_tools = _collect_available_tools(state.get("tools", []))
    system_prompt = state["system_prompt"]
    llm = chat_model.bind_tools([])

    rounds: list[dict] = []
    final_status = "completed"

    for round_index in range(1, MAX_SEARCH_ROUNDS + 1):
        round_plan = _plan_next_round(
            llm=llm,
            task=task,
            main_context=main_context,
            rounds=rounds,
            round_index=round_index,
            available_tools=available_tools,
        )

        status = str(round_plan.get("status", "search")).strip().lower()
        actions = _build_actions(
            raw_actions=round_plan.get("actions"),
            available_tools=available_tools,
        )

        if status == "done" and len(rounds) > 0:
            final_status = "early_stop_done"
            break

        action_results = [_execute_action(action=action) for action in actions]

        round_record = {
            "round": round_index,
            "status": status,
            "analysis": str(round_plan.get("analysis", "")).strip(),
            "knowledge_gaps": [
                str(item).strip()
                for item in round_plan.get("knowledge_gaps", [])
                if str(item).strip() != ""
            ]
            if isinstance(round_plan.get("knowledge_gaps"), list)
            else [],
            "actions": actions,
            "action_results": action_results,
        }
        rounds.append(round_record)

    final_answer = _finalize_search_answer(
        llm=llm,
        task=task,
        main_context=main_context,
        rounds=rounds,
        system_prompt=system_prompt,
    )

    return {
        "result": final_answer,
        "messages": [AIMessage(content=final_answer)],
        "logs": [{"status": final_status, "total_rounds": len(rounds)}],
        "search_rounds": rounds,
        "search_status": final_status,
    }


def _plan_next_round(
    llm: Any,
    task: str,
    main_context: str,
    rounds: list[dict],
    round_index: int,
    available_tools: list[str],
) -> dict:
    planning_input = {
        "task": task,
        "main_context": main_context,
        "round_index": round_index,
        "available_tools": available_tools,
        "recent_rounds": rounds[-3:],
    }

    response = llm.invoke(
        [
            SystemMessage(content=SEARCH_ROUND_PLANNER_PROMPT),
            HumanMessage(content=json.dumps(planning_input, ensure_ascii=False)),
        ]
    )

    parsed = safe_parse_json(response.content)
    if not isinstance(parsed, dict) or len(parsed) == 0:
        return {
            "status": "search",
            "analysis": "策略解析失败。",
            "knowledge_gaps": ["缺少可解析的策略输出"],
            "actions": [],
        }
    return parsed


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

        actions.append(
            {
                "tool": tool_name,
                "args": action_args,
                "purpose": str(raw_action.get("purpose", "")).strip(),
            }
        )

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
    system_prompt: str,
) -> str:
    synthesis_input = {
        "task": task,
        "main_context": main_context,
        "total_rounds": len(rounds),
        "rounds": rounds,
    }
    final_system_prompt = f"{system_prompt}\n\n{SEARCH_FINAL_ANSWER_PROMPT}"
    response = llm.invoke(
        [
            SystemMessage(content=final_system_prompt),
            HumanMessage(content=json.dumps(synthesis_input, ensure_ascii=False)),
        ]
    )
    return response.content
