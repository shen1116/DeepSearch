from langchain_core.tools import tool

@tool
def get_news(topic: str) -> str:
    """Get the news of a topic"""
    return f"The news of {topic} is good."
