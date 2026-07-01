"""Provider abstraction: a normalized, OpenAI-style chat interface.

Messages are OpenAI-format dicts throughout the codebase:
  {"role": "system"|"user", "content": str}
  {"role": "assistant", "content": str|None, "tool_calls": [ ... ]}
  {"role": "tool", "tool_call_id": str, "name": str, "content": str}

Tools are OpenAI function schemas: {"type": "function", "function": {name, description, parameters}}.
Every provider returns an `LLMResponse` so the ReAct loop is provider-agnostic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw: dict | None = None

    @property
    def is_final(self) -> bool:
        return not self.tool_calls


class LLMProvider(ABC):
    """A model backend. Implementations MUST be deterministic given identical
    inputs when `temperature == 0` so runs are reproducible."""

    name: str = "base"
    # Free-tier requests-per-day cap, used by the runner's budget estimator.
    requests_per_day: int | None = None

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        ...
