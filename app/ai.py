import json
import re
import time

import httpx

_TIMEOUT = httpx.Timeout(300.0, connect=20.0)
_MAX_ATTEMPTS = 4
_RETRYABLE = (429, 500, 502, 503)


def _headers(api_key: str) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


_GEMINI_HOST = "generativelanguage.googleapis.com"


def embed_texts(
    texts: list[str],
    base_url: str,
    api_key: str,
    model: str,
    mode: str = "passage",
) -> list[list[float]]:
    if not base_url:
        raise ValueError(
            "Embedding API URL is not set. Ask the admin to add it in Settings."
        )
    if _GEMINI_HOST in base_url:
        return _gemini_embed_texts(texts, api_key, model)
    url = base_url.rstrip("/") + "/embeddings"
    payload = {"model": model, "input": texts}
    if "integrate.api.nvidia.com" in base_url:
        payload["input_type"] = "passage" if mode == "passage" else "query"
    for attempt in range(_MAX_ATTEMPTS):
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                response = client.post(url, json=payload, headers=_headers(api_key))
                if response.status_code in _RETRYABLE and attempt < _MAX_ATTEMPTS - 1:
                    _sleep_for_retry(attempt, response)
                    continue
                response.raise_for_status()
                data = response.json()
            return [item["embedding"] for item in data["data"]]
        except httpx.HTTPStatusError as e:
            if e.response.status_code in _RETRYABLE and attempt < _MAX_ATTEMPTS - 1:
                _sleep_for_retry(attempt, e.response)
                continue
            raise


def _gemini_embed_texts(
    texts: list[str], api_key: str, model: str
) -> list[list[float]]:
    url = (
        f"https://{_GEMINI_HOST}/v1beta/models/{model}:batchEmbedContents"
    )
    payload = {
        "requests": [
            {
                "model": f"models/{model}",
                "content": {"parts": [{"text": text}]},
            }
            for text in texts
        ]
    }
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    for attempt in range(_MAX_ATTEMPTS):
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                response = client.post(url, json=payload, headers=headers)
                if response.status_code in _RETRYABLE and attempt < _MAX_ATTEMPTS - 1:
                    _sleep_for_retry(attempt, response)
                    continue
                response.raise_for_status()
                data = response.json()
            return [item["values"] for item in data["embeddings"]]
        except httpx.HTTPStatusError as e:
            if e.response.status_code in _RETRYABLE and attempt < _MAX_ATTEMPTS - 1:
                _sleep_for_retry(attempt, e.response)
                continue
            raise


def chat_completion(
    messages: list[dict], base_url: str, api_key: str, model: str
) -> str:
    if not base_url:
        raise ValueError(
            "Chat API URL is not set. Ask the admin to add it in Settings."
        )
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {"model": model, "messages": messages}
    for attempt in range(_MAX_ATTEMPTS):
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                response = client.post(url, json=payload, headers=_headers(api_key))
                if response.status_code in _RETRYABLE and attempt < _MAX_ATTEMPTS - 1:
                    _sleep_for_retry(attempt, response)
                    continue
                response.raise_for_status()
                data = response.json()
            choices = data.get("choices") or [{}]
            content = (choices[0] or {}).get("message", {}).get("content")
            if content is None and attempt < _MAX_ATTEMPTS - 1:
                time.sleep(float(2**attempt))
                continue
            return content or ""
        except httpx.HTTPStatusError as e:
            if e.response.status_code in _RETRYABLE and attempt < _MAX_ATTEMPTS - 1:
                _sleep_for_retry(attempt, e.response)
                continue
            raise


def chat_completion_stream(
    messages: list[dict], base_url: str, api_key: str, model: str
):
    if not base_url:
        raise ValueError(
            "Chat API URL is not set. Ask the admin to add it in Settings."
        )
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {"model": model, "messages": messages, "stream": True}
    for attempt in range(_MAX_ATTEMPTS):
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                with client.stream(
                    "POST", url, json=payload, headers=_headers(api_key)
                ) as response:
                    if response.status_code in _RETRYABLE and attempt < _MAX_ATTEMPTS - 1:
                        _sleep_for_retry(attempt, response)
                        continue
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data = line[6:]
                        if data.strip() == "[DONE]":
                            return
                        try:
                            chunk = json.loads(data)
                        except Exception:
                            continue
                        choices = chunk.get("choices") or [{}]
                        delta = (choices[0] or {}).get("delta") or {}
                        content = delta.get("content")
                        if content:
                            yield content
                    return
        except httpx.HTTPStatusError as e:
            if e.response.status_code in _RETRYABLE and attempt < _MAX_ATTEMPTS - 1:
                _sleep_for_retry(attempt, e.response)
                continue
            raise


def _parse_retry_seconds(text: str) -> float:
    match = re.search(r"[Pp]lease retry in ([0-9.]+)s", text)
    if match:
        try:
            return float(match.group(1))
        except Exception:
            return 0.0
    return 0.0


def _sleep_for_retry(attempt: int, response) -> None:
    delay = 0.0
    try:
        body = response.read() if hasattr(response, "read") else None
        text = body.decode(errors="ignore") if isinstance(body, bytes) else ""
        delay = _parse_retry_seconds(text)
    except Exception:
        pass
    if delay <= 0:
        delay = float(2**attempt)
    time.sleep(min(delay + 1.0, 20.0))
