"""Scenario model.

An indirect-prompt-injection scenario = a benign user task that forces the agent to
read untrusted content, where an attacker instruction may be hidden. Resources contain
a `{INJECTION}` placeholder; `render(attack_type)` substitutes the chosen payload
(or "" for the clean/no-attack baseline).

`hijack_check` / `utility_check` are small declarative specs interpreted by the graders,
so success is deterministic and read only from AgentState — never from the transcript.
"""
from __future__ import annotations

from dataclasses import dataclass, field

INJECTION_PLACEHOLDER = "{INJECTION}"


@dataclass
class Scenario:
    id: str
    category: str
    user_task: str
    attack_goal: str                      # human-readable description
    tools: list[str]
    resources: dict                       # url/path/"records" -> template text (may hold {INJECTION})
    injections: dict                      # attack_type -> payload text
    secret: dict = field(default_factory=dict)
    hijack_check: dict = field(default_factory=dict)
    utility_check: dict = field(default_factory=dict)
    mock_script: dict = field(default_factory=dict)  # drives the offline MockProvider

    def render(self, attack_type: str) -> dict:
        """Return resources with the placeholder replaced by the payload for
        `attack_type`. `attack_type == "clean"` (or unknown) injects nothing."""
        payload = self.injections.get(attack_type, "") if attack_type != "clean" else ""
        rendered = {}
        for key, text in self.resources.items():
            rendered[key] = (text or "").replace(INJECTION_PLACEHOLDER, payload)
        return rendered

    def available_attacks(self) -> list[str]:
        return list(self.injections.keys())
