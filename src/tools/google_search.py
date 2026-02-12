import json
import os
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from langchain_core.tools import tool


@tool
def google_search(query: str, num_results: int = 5) -> str:
    """Search web pages via Serper API and return concise JSON results."""
    api_key = os.getenv("SERPER_API_KEY", "").strip()
    base_url = os.getenv("SERPER_BASE_URL", "https://google.serper.dev").strip().rstrip("/")

    if query.strip() == "":
        return json.dumps({"error": "query is empty"}, ensure_ascii=False)

    if api_key == "":
        return json.dumps(
            {
                "error": "missing SERPER_API_KEY",
                "hint": "set SERPER_API_KEY in your .env",
            },
            ensure_ascii=False,
        )

    safe_num = max(1, min(num_results, 10))
    payload = json.dumps(
        {
            "q": query,
            "num": safe_num,
            "hl": "zh-cn",
            "safe": "off",
        }
    ).encode("utf-8")
    url = f"{base_url}/search"
    request = Request(
        url,
        data=payload,
        method="POST",
        headers={
            "User-Agent": "DeepSearch/1.0",
            "Content-Type": "application/json",
            "X-API-KEY": api_key,
        },
    )

    try:
        with urlopen(request, timeout=20) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = ""
        try:
            body = error.read().decode("utf-8")
        except Exception:
            body = ""
        return json.dumps(
            {
                "error": "serper search http error",
                "status": error.code,
                "detail": body[:500],
            },
            ensure_ascii=False,
        )
    except URLError as error:
        return json.dumps(
            {
                "error": "serper search network error",
                "detail": str(error.reason),
            },
            ensure_ascii=False,
        )
    except Exception as error:
        return json.dumps(
            {"error": "serper search unknown error", "detail": str(error)},
            ensure_ascii=False,
        )

    items = response_payload.get("organic", []) or []
    results = []
    for item in items:
        results.append(
            {
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            }
        )

    return json.dumps(
        {
            "query": query,
            "total_results": response_payload.get("searchInformation", {}).get(
                "totalResults", str(len(results))
            ),
            "results": results,
        },
        ensure_ascii=False,
    )
