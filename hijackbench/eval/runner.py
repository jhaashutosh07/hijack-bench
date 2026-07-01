"""Matrix runner: providers × scenarios × defenses × attack_types × trials.

Budget-aware by design (free tiers are RPD-capped and each cell is a multi-step
episode, not one request):
  - `estimate_requests` powers `--dry-run` so you SEE the cost before spending it.
  - `--max-requests` hard-stops a run mid-matrix.
  - results are appended to JSONL and runs are RESUMABLE (completed cells are skipped).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass

from ..providers.registry import build_provider, parse_spec, free_tier_rpd
from ..defenses import build_defense
from ..agent import run_episode
from ..graders import grade_hijack, grade_utility

# Rough per-cell request estimate for a typical attacked episode
# (benign tool call -> optional exfil -> final answer).
TYPICAL_STEPS_PER_CELL = 3


def scenario_fingerprint(scenario) -> str:
    """Short hash of everything that defines a scenario's behavior. Included in the
    cell key so that editing a payload/check without renaming the scenario cannot
    cause the runner to skip it as 'already done'."""
    payload = json.dumps({
        "user_task": scenario.user_task,
        "tools": scenario.tools,
        "resources": scenario.resources,
        "injections": scenario.injections,
        "secret": scenario.secret,
        "hijack_check": scenario.hijack_check,
        "utility_check": scenario.utility_check,
        "mock_script": scenario.mock_script,
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8]


@dataclass(frozen=True)
class Cell:
    provider: str
    scenario_id: str
    category: str
    defense: str
    attack: str
    trial: int
    fp: str = ""  # scenario fingerprint; trials are deterministic repeats for now (seeds: M2)

    @property
    def key(self) -> str:
        return f"{self.provider}|{self.scenario_id}@{self.fp}|{self.defense}|{self.attack}|{self.trial}"


def build_cells(specs, scenarios, defenses, attack_types, trials) -> list[Cell]:
    cells = []
    for spec in specs:
        for sc in scenarios:
            fp = scenario_fingerprint(sc)
            for d in defenses:
                for atk in attack_types:
                    for t in range(trials):
                        cells.append(Cell(spec, sc.id, sc.category, d, atk, t, fp))
    return cells


def estimate_requests(cells: list[Cell], max_steps: int) -> dict:
    """Per-provider request estimate for a dry run."""
    by_provider: dict[str, int] = {}
    for c in cells:
        by_provider[c.provider] = by_provider.get(c.provider, 0) + 1
    out = {}
    for provider, n in by_provider.items():
        rpd = free_tier_rpd(provider)
        typical = n * TYPICAL_STEPS_PER_CELL
        worst = n * max_steps
        out[provider] = {
            "cells": n,
            "typical_requests": typical,
            "worst_case_requests": worst,
            "rpd_cap": rpd,
            "days_at_cap_typical": (round(typical / rpd, 2) if rpd else None),
        }
    return out


def _load_done_keys(out_path: str) -> set[str]:
    keys: set[str] = set()
    if not os.path.exists(out_path):
        return keys
    with open(out_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                keys.add(json.loads(line)["key"])
            except (json.JSONDecodeError, KeyError):
                continue
    return keys


def run_matrix(specs, scenarios, defenses, attack_types, trials, out_path,
               *, max_steps: int = 8, max_requests: int | None = None,
               resume: bool = True, log=print) -> dict:
    scenario_by_id = {s.id: s for s in scenarios}
    cells = build_cells(specs, scenarios, defenses, attack_types, trials)
    done = _load_done_keys(out_path) if resume else set()

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    requests_used = 0
    n_run = n_skipped = 0
    stopped_early = False

    with open(out_path, "a", encoding="utf-8") as f:
        for c in cells:
            if c.key in done:
                n_skipped += 1
                continue
            if max_requests is not None and requests_used >= max_requests:
                stopped_early = True
                break

            scenario = scenario_by_id[c.scenario_id]
            provider = build_provider(c.provider, scenario)
            defense = build_defense(c.defense)
            resources = scenario.render(c.attack)

            result = run_episode(provider, scenario, defense, resources, max_steps=max_steps)
            requests_used += result.n_requests

            hijacked = grade_hijack(scenario, result.state)
            useful = grade_utility(scenario, result.state)

            record = {
                "key": c.key,
                "ts": time.time(),
                "provider": c.provider,
                "scenario": c.scenario_id,
                "category": c.category,
                "defense": c.defense,
                "attack": c.attack,
                "trial": c.trial,
                "hijacked": hijacked,
                "useful": useful,
                "steps": result.steps,
                "stopped": result.stopped,
                "n_requests": result.n_requests,
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
                "n_sink_calls": len(result.state.sink_calls),
                "n_blocked": len(result.state.blocked_calls),
            }
            f.write(json.dumps(record) + "\n")
            f.flush()
            n_run += 1
            log(f"[{n_run}] {c.key}  hijacked={hijacked} useful={useful} "
                f"steps={result.steps} reqs={result.n_requests}")

    return {
        "n_run": n_run,
        "n_skipped": n_skipped,
        "requests_used": requests_used,
        "stopped_early": stopped_early,
        "out_path": out_path,
    }
