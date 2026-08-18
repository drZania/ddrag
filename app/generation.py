"""Ollama generation integration for grounded answers."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import get_settings


class OllamaGenerationError(RuntimeError):
    """Raised when Ollama cannot generate a grounded answer."""


def generate_answer(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    base_url: str | None = None,
) -> str:
    """Generate a grounded answer through Ollama's chat API."""

    settings = get_settings()
    resolved_model = (model or settings.generation_model).strip()
    resolved_base_url = (base_url or settings.ollama_base_url).rstrip("/")

    if not resolved_model:
        raise OllamaGenerationError("generation model must not be blank")
    if not resolved_base_url:
        raise OllamaGenerationError("ollama base URL must not be blank")

    payload = {
        "model": resolved_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
    }
    request = Request(
        f"{resolved_base_url}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=60) as response:
            body = response.read()
    except (HTTPError, URLError, OSError) as exc:
        raise OllamaGenerationError(f"Ollama generation request failed: {exc}") from exc

    try:
        decoded = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise OllamaGenerationError("Ollama returned malformed JSON") from exc

    if isinstance(decoded, dict):
        error_detail = decoded.get("error")
        if error_detail:
            raise OllamaGenerationError(f"Ollama returned an error: {error_detail}")

    message = decoded.get("message") if isinstance(decoded, dict) else None
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content

    response_text = decoded.get("response") if isinstance(decoded, dict) else None
    if isinstance(response_text, str):
        return response_text

    raise OllamaGenerationError("Ollama returned malformed response")


__all__ = ["OllamaGenerationError", "generate_answer"]
