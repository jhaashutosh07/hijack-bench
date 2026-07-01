"""Adaptive attack-loop tests: the harness must report the honest defense contrast —
content/prompt defenses fall to adaptation, structural gating holds."""
from hijackbench.scenarios import load_all
from hijackbench.attacker import ScriptedAttacker, run_adaptive

SCN = next(s for s in load_all() if s.id == "file-exfil-handoff")


def test_adaptive_breaks_none_immediately():
    res = run_adaptive("mock", SCN, "none", ScriptedAttacker(), max_rounds=5)
    assert res.broken is True
    assert res.rounds_used == 1


def test_adaptive_breaks_sanitizer_after_escalation():
    # The literal/keyword payloads are redacted; the obfuscated token-free one gets through.
    res = run_adaptive("mock", SCN, "sanitizer", ScriptedAttacker(), max_rounds=5)
    assert res.broken is True
    assert res.rounds_used >= 2, "sanitizer should survive the naive payload, fall to the evasive one"
    assert res.winning_payload is not None


def test_adaptive_cannot_break_privilege_gate():
    # Structural control: no wording defeats it because the sink itself is blocked.
    res = run_adaptive("mock", SCN, "privilege_gate", ScriptedAttacker(), max_rounds=5)
    assert res.broken is False
    assert res.rounds_used == 5


def test_adaptive_result_reports_asr_and_history():
    res = run_adaptive("mock", SCN, "sanitizer", ScriptedAttacker(), max_rounds=5)
    assert 0.0 <= res.asr <= 1.0
    assert len(res.history) == res.rounds_used
