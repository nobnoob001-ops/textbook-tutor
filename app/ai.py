import httpx

_TIMEOUT = httpx.Timeout(180.0, connect=20.0)


def _headers(api_key: str) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def embed_texts(
    texts: list[str], base_url: str, api_key: str, model: str
) -> list[list[float]]:
    if not base_url:
        raise ValueError(
            "Embedding API URL is not set. Ask the admin to add it in Settings."
        )
    url = base_url.rstrip("/") + "/embeddings"
    payload = {"model": model, "input": texts}
    with httpx.Client(timeout=_TIMEOUT) as client:
        response = client.post(url, json=payload, headers=_headers(api_key))
        response.raise_for_status()
        data = response.json()
    return [item["embedding"] for item in data["data"]]


def chat_completion(
    messages: list[dict], base_url: str, api_key: str, model: str
) -> str:
    if not base_url:
        raise ValueError(
            "Chat API URL is not set. Ask the admin to add it in Settings."
        )
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {"model": model, "messages": messages}
    with httpx.Client(timeout=_TIMEOUT) as client:
        response = client.post(url, json=payload, headers=_headers(api_key))
        response.raise_for_status()
        data = response.json()
    return data["choices"][0]["message"]["content"]
