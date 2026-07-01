"""Per-episode observable state. Graders read ONLY this — never the transcript —
so attack success is deterministic and un-gameable.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentState:
    # Secrets planted in the scenario the attacker wants to exfiltrate.
    secret: dict = field(default_factory=dict)
    # Every SINK invocation (send_email / http_post), recorded — NOT executed.
    sink_calls: list[dict] = field(default_factory=list)
    # Every tool call the agent made (name + args), for forbidden-tool checks.
    tool_calls: list[dict] = field(default_factory=list)
    # Tool calls blocked by a defense (e.g. privilege_gate), for auditing.
    blocked_calls: list[dict] = field(default_factory=list)
    # The agent's final natural-language answer (drives the utility grader).
    final_answer: str | None = None

    def record_tool_call(self, name: str, args: dict) -> None:
        self.tool_calls.append({"name": name, "args": args})

    def record_sink(self, name: str, args: dict) -> None:
        self.sink_calls.append({"name": name, "args": args})
