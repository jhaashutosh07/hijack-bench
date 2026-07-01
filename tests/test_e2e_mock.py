"""Full offline end-to-end: run the real pipeline with the scriptable mock provider
and assert the money-graph behavior — `none` gets hijacked, `datamark` does not, and
utility is preserved in both."""
import os
import tempfile

import pytest

from hijackbench.scenarios import load_all
from hijackbench.defenses import build_defense
from hijackbench.providers.registry import build_provider
from hijackbench.agent import run_episode
from hijackbench.graders import grade_hijack, grade_utility
from hijackbench.eval.runner import run_matrix
from hijackbench.eval.metrics import load_records, aggregate

SCENARIOS = load_all()


def _run(scenario, defense_name, attack, provider_spec="mock"):
    provider = build_provider(provider_spec, scenario)
    defense = build_defense(defense_name)
    resources = scenario.render(attack)
    result = run_episode(provider, scenario, defense, resources, max_steps=8)
    return (grade_hijack(scenario, result.state),
            grade_utility(scenario, result.state), result)


def test_scenarios_loaded():
    assert len(SCENARIOS) >= 3
    assert {s.category for s in SCENARIOS} >= {"web", "file", "tool"}


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s.id for s in SCENARIOS])
def test_none_defense_gets_hijacked_under_attack(scenario):
    hijacked, useful, _ = _run(scenario, "none", "static")
    assert hijacked is True, f"{scenario.id}: expected hijack under no defense"
    assert useful is True, f"{scenario.id}: benign task should still complete"


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s.id for s in SCENARIOS])
def test_datamark_prevents_hijack_and_keeps_utility(scenario):
    hijacked, useful, _ = _run(scenario, "datamark", "static")
    assert hijacked is False, f"{scenario.id}: datamark should block the injection"
    assert useful is True, f"{scenario.id}: datamark should preserve utility"


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s.id for s in SCENARIOS])
def test_clean_run_no_attack(scenario):
    hijacked, useful, _ = _run(scenario, "none", "clean")
    assert hijacked is False
    assert useful is True


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s.id for s in SCENARIOS])
def test_leaky_model_is_hijacked_even_under_datamark(scenario):
    """SENSITIVITY: a model that obeys injections through data-marking must still be
    graded as hijacked — proving the pipeline surfaces real leaks and no defense
    wrapper silently swallows sink calls. The 'safe for the wrong reason' guard."""
    hijacked, useful, result = _run(scenario, "datamark", "static", provider_spec="mock:leaky")
    assert hijacked is True, f"{scenario.id}: leaky model should still leak under datamark"
    assert useful is True, f"{scenario.id}: leaky model also completes the task (messy middle)"
    assert result.state.sink_calls, "sink call must be recorded even under a defense"


def test_pipeline_reports_nonzero_asr_under_defense_for_leaky_model():
    """The failure mode this catches: a bug that makes ASR read 0 under any defense.
    With a leaky model, aggregated ASR under datamark MUST be > 0."""
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "run.jsonl")
        run_matrix(["mock:leaky"], SCENARIOS, ["datamark"], ["static"], 1, out,
                   max_steps=8, log=lambda *_: None)
        agg = aggregate(load_records(out))
        assert agg["by_defense"]["mock:leaky"]["datamark"]["asr"] > 0.0


def test_full_matrix_and_aggregate_money_graph():
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "run.jsonl")
        run_matrix(["mock"], SCENARIOS, ["none", "datamark"], ["clean", "static"], 1, out,
                   max_steps=8, log=lambda *_: None)
        agg = aggregate(load_records(out))
        none_asr = agg["by_defense"]["mock"]["none"]["asr"]
        dm_asr = agg["by_defense"]["mock"]["datamark"]["asr"]
        assert none_asr == 1.0
        assert dm_asr == 0.0
        # datamark should reduce ASR with zero utility cost in this seed suite.
        pt = next(s for s in agg["scatter"] if s["defense"] == "datamark")
        assert pt["asr_reduction"] == 1.0
        assert pt["utility_cost"] == 0.0
