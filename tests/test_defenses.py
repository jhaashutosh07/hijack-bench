"""Mechanism tests for the M3 defenses — each hook must actually fire, and the mock's
reaction to each must be the expected (honest) shape."""
import pytest

from hijackbench.scenarios import load_all
from hijackbench.defenses import build_defense, DEFENSES
from hijackbench.providers.registry import build_provider
from hijackbench.agent import run_episode
from hijackbench.graders import grade_hijack, grade_utility
from hijackbench.markers import ATTACKER_EMAIL

# A representative exfil scenario (secret in tool output, injection wants send_email).
SCN = next(s for s in load_all() if s.id == "file-exfil-handoff")


def _run(defense_name, attack="static", target="mock"):
    provider = build_provider(target, SCN)
    defense = build_defense(defense_name)
    resources = SCN.render(attack)
    result = run_episode(provider, SCN, defense, resources, max_steps=8)
    return result, grade_hijack(SCN, result.state), grade_utility(SCN, result.state)


def test_all_five_defenses_registered():
    assert set(DEFENSES) == {"none", "datamark", "instruction_hierarchy", "sanitizer", "privilege_gate"}


def test_instruction_hierarchy_is_prompt_only_and_naive_model_still_leaks():
    # Prompt-only defense leaves the injection visible -> naive model hijacked (weak).
    _, hijacked, useful = _run("instruction_hierarchy")
    assert hijacked is True
    assert useful is True


def test_sanitizer_redacts_injection_and_blocks_static_attack():
    result, hijacked, useful = _run("sanitizer")
    assert hijacked is False, "sanitizer should strip the literal exfil directive"
    assert useful is True
    # The attacker address must not survive in any tool message shown to the model.
    tool_text = "\n".join(m.get("content") or "" for m in result.transcript if m.get("role") == "tool")
    assert ATTACKER_EMAIL not in tool_text


def test_privilege_gate_blocks_the_sink_call():
    result, hijacked, _ = _run("privilege_gate")
    assert hijacked is False, "privilege_gate must stop the secret leaving"
    assert result.state.blocked_calls, "the blocked sink call should be recorded"
    assert not result.state.sink_calls, "no sink call should have executed"


def test_privilege_gate_allows_internal_domain():
    d = build_defense("privilege_gate")
    ok, _ = d.authorize("send_email", {"to": "lead@acme.test", "body": "hi"}, SCN)
    blocked, _ = d.authorize("send_email", {"to": ATTACKER_EMAIL, "body": "x"}, SCN)
    assert ok is True
    assert blocked is False
