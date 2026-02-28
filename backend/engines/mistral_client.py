from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Iterable, Iterator
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .prompt_composer import ChatMessage


class MistralClientError(RuntimeError):
    """Raised for Mistral API request/response failures."""


@dataclass(frozen=True)
class MistralChatConfig:
    model: str = "mistral-small-latest"
    temperature: float = 0.7
    top_p: float = 0.95
    max_tokens: int = 220
    timeout_seconds: float = 30.0
    endpoint: str = "https://api.mistral.ai/v1/chat/completions"


class MistralChatClient:
    """Thin Mistral chat client supporting sync and streaming responses."""

    def __init__(self, api_key: str | None = None, config: MistralChatConfig | None = None) -> None:
        self.config = config or MistralChatConfig()
        self.api_key = (api_key or os.getenv("MISTRAL_API_KEY") or "").strip()
        if not self.api_key:
            raise ValueError("MISTRAL_API_KEY is required")

    def chat(self, messages: Iterable[ChatMessage]) -> str:
        payload = self._build_payload(messages=messages, stream=False)
        response_obj = self._post_json(payload)
        text = self._extract_chat_text(response_obj)
        if not text:
            raise MistralClientError("Mistral returned an empty response")
        return text

    def stream_chat(self, messages: Iterable[ChatMessage]) -> Iterator[str]:
        payload = self._build_payload(messages=messages, stream=True)
        request = self._build_request(payload)

        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="ignore").strip()
                    if not line or not line.startswith("data:"):
                        continue

                    data = line[5:].strip()
                    if not data:
                        continue
                    if data == "[DONE]":
                        break

                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    chunk = self._extract_stream_text(event)
                    if chunk:
                        yield chunk
        except HTTPError as exc:
            raise self._http_error(exc) from exc
        except URLError as exc:
            raise MistralClientError(f"Failed to reach Mistral API: {exc}") from exc

    def _build_payload(self, messages: Iterable[ChatMessage], stream: bool) -> dict[str, Any]:
        return {
            "model": self.config.model,
            "messages": list(messages),
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "max_tokens": self.config.max_tokens,
            "stream": stream,
        }

    def _build_request(self, payload: dict[str, Any]) -> Request:
        body = json.dumps(payload).encode("utf-8")
        return Request(
            url=self.config.endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = self._build_request(payload)

        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            raise self._http_error(exc) from exc
        except URLError as exc:
            raise MistralClientError(f"Failed to reach Mistral API: {exc}") from exc

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise MistralClientError("Mistral returned invalid JSON") from exc

        if not isinstance(parsed, dict):
            raise MistralClientError("Mistral returned an unexpected payload type")
        return parsed

    def _extract_chat_text(self, response_obj: dict[str, Any]) -> str:
        choices = response_obj.get("choices")
        if not isinstance(choices, list) or not choices:
            raise MistralClientError("Mistral response missing choices")

        first = choices[0]
        if not isinstance(first, dict):
            raise MistralClientError("Mistral choice payload is invalid")

        message = first.get("message")
        if not isinstance(message, dict):
            raise MistralClientError("Mistral response missing message")

        return self._normalize_content(message.get("content"), strip=True)

    def _extract_stream_text(self, event: dict[str, Any]) -> str:
        choices = event.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""

        first = choices[0]
        if not isinstance(first, dict):
            return ""

        delta = first.get("delta")
        if not isinstance(delta, dict):
            return ""

        return self._normalize_content(delta.get("content"), strip=False)

    def _normalize_content(self, content: Any, strip: bool) -> str:
        if isinstance(content, str):
            return content.strip() if strip else content

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if isinstance(text, str):
                        parts.append(text)
            joined = "".join(parts)
            return joined.strip() if strip else joined

        return ""

    def _http_error(self, exc: HTTPError) -> MistralClientError:
        try:
            body = exc.read().decode("utf-8", errors="ignore")
        except Exception:
            body = ""

        detail = body.strip() or f"HTTP {exc.code}"
        return MistralClientError(f"Mistral API error: {detail}")
