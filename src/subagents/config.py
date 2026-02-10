from typing import Any

SEARCH_AGENT_NAME = "SearchAgent"
SEARCH_AGENT_DEFAULT_TOOLS = ["google_search", "jina_reader"]

SEARCH_AGENT_SYSTEM_PROMPT = """你是 SearchAgent，负责根据任务进行多轮检索与证据整理。
你需要在每轮中自己判断调用哪个工具，以及传入什么参数。

工具参数规范（务必严格遵守）：
1) google_search
   - args.query: 字符串，必填
   - args.num_results: 整数，可选，范围 1-10，建议 3-5
2) jina_reader
   - args.url: 字符串，必填，必须是 http/https 链接

工作原则：
1. 先分析 task 与 main_context，识别缺口。
2. 优先用 google_search 获取候选信息。
3. 只有在 snippet 不足、存在冲突、或需要关键事实校验时，再使用 jina_reader 深读网页。
4. 严禁编造事实；证据不足时明确不确定性。
5. 最终输出中文结论，并给出关键证据来源。
"""


def normalize_subagents(payload: Any, tools_registry: dict) -> dict:
    if not isinstance(payload, dict):
        return {}

    raw_subagents = payload.get("subagents") or payload.get("sub-agents") or payload.get("sub_agents")
    if raw_subagents is None:
        return {}

    if isinstance(raw_subagents, dict):
        candidates = list(raw_subagents.values())
    elif isinstance(raw_subagents, list):
        candidates = raw_subagents
    else:
        return {}

    normalized = {}
    for index, candidate in enumerate(candidates, start=1):
        if not isinstance(candidate, dict):
            continue

        name = str(candidate.get("name", "")).strip()
        task = str(candidate.get("task", "")).strip()
        if name == "" or task == "":
            continue

        tools = normalize_subagent_tools(
            name=name,
            raw_tools=candidate.get("tools"),
            tools_registry=tools_registry,
        )
        system_prompt = normalize_subagent_system_prompt(name=name, raw_system_prompt=candidate.get("system_prompt"))

        subagent_id = f"{name}_{index}"
        normalized[subagent_id] = {
            "id": subagent_id,
            "name": name,
            "task": task,
            "tools": tools,
            "system_prompt": system_prompt,
            "context": candidate.get("context", ""),
        }

    return normalized


def normalize_subagent_tools(name: str, raw_tools: Any, tools_registry: dict) -> list[str]:
    if isinstance(raw_tools, list) and len(raw_tools) > 0:
        tools = [tool for tool in raw_tools if isinstance(tool, str) and tool in tools_registry]
        if len(tools) > 0:
            return tools

    if name == SEARCH_AGENT_NAME:
        preferred_tools = [tool for tool in SEARCH_AGENT_DEFAULT_TOOLS if tool in tools_registry]
        if len(preferred_tools) > 0:
            return preferred_tools

    return list(tools_registry.keys())


def normalize_subagent_system_prompt(name: str, raw_system_prompt: Any) -> str:
    if isinstance(raw_system_prompt, str) and raw_system_prompt.strip() != "":
        return raw_system_prompt.strip()

    if name == SEARCH_AGENT_NAME:
        return SEARCH_AGENT_SYSTEM_PROMPT

    return f"你是{name}，请根据任务调用工具并给出简洁结论。"


def build_main_context_text(main_context: Any, subagent_context: Any) -> str:
    context_parts = []

    if isinstance(main_context, dict):
        user_input = str(main_context.get("user_input", "")).strip()
        latest_plan = str(main_context.get("latest_plan", "")).strip()
        plan_history = main_context.get("plan_history", [])
        recent_subagent_results = main_context.get("recent_subagent_results", [])
        recent_subagent_logs = main_context.get("recent_subagent_logs", [])

        if user_input != "":
            context_parts.append(f"原始问题: {user_input}")
        if latest_plan != "":
            context_parts.append(f"主代理最新计划: {latest_plan}")
        if isinstance(plan_history, list) and len(plan_history) > 0:
            recent_plans = [str(item).strip() for item in plan_history if str(item).strip() != ""]
            if len(recent_plans) > 0:
                context_parts.append("最近计划历史: " + " | ".join(recent_plans))
        if isinstance(recent_subagent_results, list) and len(recent_subagent_results) > 0:
            context_parts.append(f"最近子代理结果: {recent_subagent_results}")
        if isinstance(recent_subagent_logs, list) and len(recent_subagent_logs) > 0:
            context_parts.append(f"最近子代理日志: {recent_subagent_logs}")

    if isinstance(subagent_context, str) and subagent_context.strip() != "":
        context_parts.append(f"该任务附加上下文: {subagent_context.strip()}")

    if len(context_parts) == 0:
        return "<MAIN_CONTEXT>\n暂无额外上下文，请先拆解任务并发起必要搜索。\n</MAIN_CONTEXT>"

    return "<MAIN_CONTEXT>\n" + "\n".join(context_parts) + "\n</MAIN_CONTEXT>"
