"""OpenAI-compatible chat provider (Groq primary; also Together / OpenRouter / Cerebras
via a base_url swap). Real network calls — used only when an API key is present.
"""
from __future__ import annotations

import json
import os

from .base import LLMProvider, LLMResponse, ToolCall

# Known OpenAI-compatible free tiers: base_url, env var, free-tier RPD cap.
BACKENDS = {
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", 1000),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", None),
    "cerebras": ("https://api.cerebras.ai/v1", "CEREBRAS_API_KEY", None),
}


class OpenAICompatProvider(LLMProvider):
    def __init__(self, backend: str, model: str, timeout: float = 60.0):
        if backend not in BACKENDS:
            raise ValueError(f"unknown backend {backend!r}; known: {list(BACKENDS)}")
        base_url, env_var, rpd = BACKENDS[backend]
        api_key = os.environ.get(env_var)
        if not api_key:
            raise RuntimeError(
                f"{env_var} not set — required for provider '{backend}'. "
                f"Use --provider mock for offline runs."
            )
        self.name = f"{backend}:{model}"
        self.backend = backend
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.requests_per_day = rpd
        self.timeout = timeout

    def chat(self, messages, tools=None, temperature: float = 0.0) -> LLMResponse:
        import requests  # imported lazily so the package imports without the dep at rest

        payload: dict = {"model": self.model, "messages": messages, "temperature": temperature}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        msg = data["choices"][0]["message"]
        usage = data.get("usage", {})

        tool_calls = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {})
            args = fn.get("arguments") or "{}"
            try:
                args = json.loads(args) if isinstance(args, str) else args
            except json.JSONDecodeError:
                args = {"_raw": args}
            tool_calls.append(ToolCall(id=tc.get("id", "call_0"), name=fn.get("name", ""), arguments=args))

        return LLMResponse(
            content=msg.get("content"),
            tool_calls=tool_calls,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            raw=data,
        )
