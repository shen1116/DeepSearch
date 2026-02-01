.env
```
# Chat Model
OPENAI_MODEL=deepseek-chat
OPENAI_API_KEY=*************
OPENAI_API_BASE=https://api.deepseek.com

# LangSmith Configuration (for debugging and tracing)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=***************
LANGCHAIN_PROJECT=DeepSearch

PYTHONUNBUFFERED=1
PYTHONDONTWRITEBYTECODE=1
```


```
uv sync
uv run python main.py
```