import re
from typing import Any

import json_repair


def extract_planner_response_state(content: str, tools_registry: dict) -> dict:
    from ..subagents.config import normalize_subagents

    parsed = safe_parse_json(content)
    new_plan = ""
    if isinstance(parsed, dict):
        raw_plan = (
            parsed.get("NEW_PLAN")
            or parsed.get("new_plan")
            or parsed.get("newPlan")
            or parsed.get("plan")
        )
        if isinstance(raw_plan, str):
            new_plan = raw_plan.strip()
        elif isinstance(raw_plan, list):
            plan_lines = [str(item).strip() for item in raw_plan if str(item).strip() != ""]
            new_plan = "\n".join(plan_lines).strip()

    if new_plan == "":
        new_plan = extract_tag_content(content, "NEW_PLAN")

    subagents = normalize_subagents(parsed, tools_registry=tools_registry)
    return {"new_plan": new_plan, "subagents": subagents}


def safe_parse_json(text: Any) -> dict:
    if not isinstance(text, str) or text.strip() == "":
        return {}

    subagent_match = re.search(r"<Sub_Agent>\s*([\s\S]*?)\s*</Sub_Agent>", text, flags=re.IGNORECASE)
    payload = subagent_match.group(1).strip() if subagent_match else text.strip()

    try:
        parsed = json_repair.loads(payload)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    if payload != text.strip():
        try:
            parsed = json_repair.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    return {}


def extract_tag_content(content: str, tag_name: str) -> str:
    if not content:
        return ""
    pattern = rf"<{tag_name}>\s*([\s\S]*?)\s*</{tag_name}>"
    match = re.search(pattern, content, flags=re.IGNORECASE)
    if match is None:
        return ""
    return match.group(1).strip()
