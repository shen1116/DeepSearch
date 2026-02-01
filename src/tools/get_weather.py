from langchain_core.tools import tool

@tool
def get_weather(city: str) -> str:
    """Get the weather of a city"""
    return f"The weather of {city} is sunny."