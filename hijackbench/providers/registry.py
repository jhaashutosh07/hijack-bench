"""Build a provider from a spec string.

    "mock"                      -> scriptable offline provider (seeded from the scenario)
    "groq:llama-3.1-8b-instant" -> OpenAI-compatible backend + model
    "openrouter:...", "cerebras:..."

The mock is seeded per-episode from the scenario, so `scenario` is passed in.
"""
from __future__ import annotations

from .mock import MockProvider
from .openai_compat import OpenAICompatProvider, BACKENDS


def parse_spec(spec: str) -> tuple[str, str | None]:
    backend, _, model = spec.partition(":")
    return backend, (model or None)


def build_provider(spec: str, scenario=None):
    backend, model = parse_spec(spec)
    if backend == "mock":
        script = getattr(scenario, "mock_script", None) if scenario is not None else None
        secret = getattr(scenario, "secret", None) if scenario is not None else None
        policy = model or "naive"  # "mock" -> naive, "mock:leaky" -> leaky
        return MockProvider(script=script, secret=secret, policy=policy)
    if backend in BACKENDS:
        if not model:
            raise ValueError(f"provider '{backend}' needs a model, e.g. '{backend}:llama-3.1-8b-instant'")
        return OpenAICompatProvider(backend=backend, model=model)
    raise ValueError(f"unknown provider spec {spec!r}")


def free_tier_rpd(spec: str) -> int | None:
    backend, _ = parse_spec(spec)
    if backend == "mock":
        return None  # unlimited / free
    return BACKENDS.get(backend, (None, None, None))[2]
