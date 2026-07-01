"""Google Gemini provider (free tier), native generativelanguage REST API.

Gemini is not OpenAI-shaped, so this adapter translates our OpenAI-style messages/tools
to Gemini `contents`/`tools` and normalizes the response back into an `LLMResponse`.

Note: written to the documented v1beta API shape; exercise it with a real GEMINI_API_KEY
(the offline `mock` provider covers keyless CI). See README for free-tier limits.
"""
from __future__ import annotations

import os

from .base import LLMProvider, LLMResponse, ToolCall

_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _to_gemini_tools(tools: list[dict] | None) -> list[dict] | None:
    if not tools:
        return None
    decls = []
    for t in tools:
        fn = t.get("function", {})
        decls.append({"name": fn.get("name"), "description": fn.get("description", ""),
                      "parameters": fn.get("parameters", {"type": "object", "properties": {}})})
    return [{"functionDeclarations": decls}]


def _to_gemini_contents(messages: list[dict]) -> tuple[str, list[dict]]:
    """Return (system_instruction, contents). Gemini uses roles 'user'/'model' and
    represents tool results as functionResponse parts."""
    system = ""
    contents = []
    for m in messages:
        role = m.get("role")
        if role == "system":
            system += (m.get("content") or "") + "\n"
        elif role == "user":
            contents.append({"role": "user", "parts": [{"text": m.get("content") or ""}]})
        elif role == "assistant":
            parts = []
            if m.get("content"):
                parts.append({"text": m["content"]})
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function", {})
                import json as _json
                args = fn.get("arguments") or "{}"
                try:
                    args = _json.loads(args) if isinstance(args, str) else args
                except _json.JSONDecodeError:
                    args = {}
                parts.append({"functionCall": {"name": fn.get("name"), "args": args}})
            contents.append({"role": "model", "parts": parts or [{"text": ""}]})
        elif role == "tool":
            contents.append({"role": "user", "parts": [{"functionResponse": {
                "name": m.get("name", "tool"), "response": {"content": m.get("content") or ""}}}]})
    return system.strip(), contents


class GeminiProvider(LLMProvider):
    def __init__(self, model: str, timeout: float = 60.0):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set. Use --provider mock for offline runs.")
        self.name = f"gemini:{model}"
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.requests_per_day = 1500  # typical free-tier order of magnitude; verify per model

    def chat(self, messages, tools=None, temperature: float = 0.0) -> LLMResponse:
        import requests

        system, contents = _to_gemini_contents(messages)
        body: dict = {"contents": contents, "generationConfig": {"temperature": temperature}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        gtools = _to_gemini_tools(tools)
        if gtools:
            body["tools"] = gtools

        url = f"{_BASE}/{self.model}:generateContent?key={self.api_key}"
        resp = requests.post(url, json=body, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        candidates = data.get("candidates", [])
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        text_bits, tool_calls = [], []
        for i, p in enumerate(parts):
            if "text" in p:
                text_bits.append(p["text"])
            elif "functionCall" in p:
                fc = p["functionCall"]
                tool_calls.append(ToolCall(id=f"call_{i}", name=fc.get("name", ""),
                                           arguments=fc.get("args", {}) or {}))
        usage = data.get("usageMetadata", {})
        return LLMResponse(
            content=("".join(text_bits) or None) if not tool_calls else "".join(text_bits) or None,
            tool_calls=tool_calls,
            prompt_tokens=usage.get("promptTokenCount", 0),
            completion_tokens=usage.get("candidatesTokenCount", 0),
            raw=data,
        )
