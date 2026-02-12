import re
from typing import Any
import json_repair

def extract_planner_response_state(content: str) -> dict:
    parsed = safe_parse_json(content)
    new_plan = ""
    if isinstance(parsed, dict):
        raw_plan = (parsed.get("NEW_PLAN") or parsed.get("new_plan"))
        if isinstance(raw_plan, str):
            new_plan = raw_plan.strip()
        elif isinstance(raw_plan, list):
            plan_lines = [str(item).strip() for item in raw_plan if str(item).strip() != ""]
            new_plan = "\n".join(plan_lines).strip()

    if new_plan == "":
        new_plan = extract_tag_content(content, "NEW_PLAN")

    key_info_summary = ""
    if isinstance(parsed, dict):
        raw_summary = (parsed.get("KEY_INFO_SUMMARY") or parsed.get("key_info_summary"))
        if isinstance(raw_summary, str):
            key_info_summary = raw_summary.strip()
        elif isinstance(raw_summary, list):
            summary_lines = [str(item).strip() for item in raw_summary if str(item).strip() != ""]
            key_info_summary = "\n".join(summary_lines).strip()

    if key_info_summary == "":
        key_info_summary = extract_tag_content(content, "KEY_INFO_SUMMARY")

    subagents = normalize_subagents(parsed)
    return {
        "plan": new_plan,
        "subagents": subagents,
        "key_info": key_info_summary,
    }


def safe_parse_json(text: Any) -> dict:
    if not isinstance(text, str) or text.strip() == "":
        return {}

    subagent_match = re.search(r"<SUBAGENTS>\s*([\s\S]*?)\s*</SUBAGENTS>", text, flags=re.IGNORECASE)
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


def normalize_subagents(payload: Any) -> dict:
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

        subagent_id = f"{name}_{index}"
        normalized[subagent_id] = {
            "id": subagent_id,
            "name": name,
            "task": task,
        }

    return normalized

