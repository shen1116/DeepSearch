import json
import os
from urllib.parse import urlparse

import requests

from langchain_core.tools import tool


@tool
def jina_reader(url: str) -> str:
    """Read webpage content via Jina Reader (https://r.jina.ai/{url})."""
    normalized_url = _normalize_url(url)
    if normalized_url == "":
        return json.dumps({"error": "invalid url"}, ensure_ascii=False)

    reader_url = f"https://r.jina.ai/{normalized_url}"
    headers = {"User-Agent": "DeepSearch/1.0"}

    jina_api_key = os.getenv("JINA_API_KEY", "").strip()
    if jina_api_key != "":
        headers["Authorization"] = f"Bearer {jina_api_key}"

    try:
        response = requests.get(reader_url, headers=headers, timeout=30)
        raw_text = response.text
        if response.status_code >= 400:
            body = raw_text[:500]
            return json.dumps(
                {
                    "error": "jina reader http error",
                    "status": response.status_code,
                    "detail": body,
                    "reader_url": reader_url,
                },
                ensure_ascii=False,
            )
    except requests.RequestException as error:
        return json.dumps(
            {
                "error": "jina reader network error",
                "detail": str(error),
                "reader_url": reader_url,
            },
            ensure_ascii=False,
        )
    except Exception as error:
        return json.dumps(
            {
                "error": "jina reader unknown error",
                "detail": str(error),
                "reader_url": reader_url,
            },
            ensure_ascii=False,
        )

    text = raw_text.strip()

    return json.dumps(
        {
            "url": normalized_url,
            "content": text,
        },
        ensure_ascii=False,
    )


def _normalize_url(url: str) -> str:
    if not isinstance(url, str):
        return ""

    candidate = url.strip()
    if candidate == "":
        return ""

    parsed = urlparse(candidate)
    if parsed.scheme == "":
        candidate = f"https://{candidate}"
        parsed = urlparse(candidate)

    if parsed.scheme not in ("http", "https"):
        return ""
    if parsed.netloc == "":
        return ""

    return candidate
