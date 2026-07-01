"""Known free-tier models + their parameter scale.

The scale label is a first-class analysis axis (the benchmark's pre-committed open
question: does defense ranking change with model scale?). `run` records it per cell so
the report can group ASR/defense-effectiveness by 8B → 32B → 70B.

`recommended_suite` gives a ready scale sweep you can pass to `run --provider`.
"""
from __future__ import annotations

# spec -> {"scale": label, "params_b": approx billions, "family": str}
KNOWN_MODELS: dict[str, dict] = {
    "groq:llama-3.1-8b-instant":   {"scale": "8B",  "params_b": 8,   "family": "llama-3.1"},
    "groq:qwen-qwq-32b":           {"scale": "32B", "params_b": 32,  "family": "qwen-qwq"},
    "groq:llama-3.3-70b-versatile":{"scale": "70B", "params_b": 70,  "family": "llama-3.3"},
    "groq:llama-4-scout-17b-16e-instruct": {"scale": "17Bx16", "params_b": 17, "family": "llama-4-scout"},
    "gemini:gemini-1.5-flash":     {"scale": "flash", "params_b": None, "family": "gemini-1.5"},
    "gemini:gemini-2.0-flash":     {"scale": "flash", "params_b": None, "family": "gemini-2.0"},
    "mock":                        {"scale": "mock", "params_b": None, "family": "mock"},
    "mock:leaky":                  {"scale": "mock", "params_b": None, "family": "mock"},
}

# A ready-made model-scale sweep for `--provider`.
RECOMMENDED_SUITE = [
    "groq:llama-3.1-8b-instant",
    "groq:qwen-qwq-32b",
    "groq:llama-3.3-70b-versatile",
]


def model_scale(spec: str) -> str:
    m = KNOWN_MODELS.get(spec)
    if m:
        return m["scale"]
    # Unknown spec: best-effort label from the model name.
    return "unknown"
