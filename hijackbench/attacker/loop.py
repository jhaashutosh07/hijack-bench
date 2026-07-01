"""The adaptive attack loop: iterate an attacker against a defended target until it breaks
the defense or exhausts its round budget."""
from __future__ import annotations

from .base import Attacker, AttackRound, AdaptiveResult
from ..providers.registry import build_provider
from ..defenses import build_defense
from ..agent import run_episode
from ..graders import grade_hijack


def run_adaptive(target_spec: str, scenario, defense_name: str, attacker: Attacker,
                 *, max_rounds: int = 5, max_steps: int = 8, log=None) -> AdaptiveResult:
    history: list[AttackRound] = []
    for r in range(1, max_rounds + 1):
        payload = attacker.propose(defense_name, scenario, history)
        provider = build_provider(target_spec, scenario)
        defense = build_defense(defense_name)
        resources = scenario.render_payload(payload)

        result = run_episode(provider, scenario, defense, resources, max_steps=max_steps)
        hijacked = grade_hijack(scenario, result.state)
        history.append(AttackRound(payload=payload, hijacked=hijacked))
        if log:
            log(f"  round {r}: hijacked={hijacked}  payload={payload.strip()[:70]!r}")
        if hijacked:
            return AdaptiveResult(scenario.id, defense_name, target_spec, True, r, payload, history)
    return AdaptiveResult(scenario.id, defense_name, target_spec, False, max_rounds, None, history)
