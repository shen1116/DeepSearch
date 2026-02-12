from src.prompt import PLANNER_PROMPT

state = {
    "user_input": "请根据以下线索找出这位艺术家的姓名：曾在中国中央美术学院及德国杜塞尔多夫艺术学院深造，并赴德国留学。在德国学习期间，他师从三位知名艺术家，其中一位艺术家的作品曾在2012年创下在世艺术家拍卖的最高价纪录",
    "plans": "",
    "subagent_results": {},
    "key_info_memory": []
}

system_prompt = PLANNER_PROMPT.substitute(
    problem=state["user_input"],
    plans=state["plans"],
    subagent_responses=state["subagent_results"],
    key_info_memory=state["key_info_memory"]
)

print(system_prompt)
    