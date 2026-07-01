"""hijack-bench CLI.

    python -m hijackbench list
    python -m hijackbench run  --provider mock --defenses none,datamark [--dry-run]
    python -m hijackbench report --in results/run.jsonl
"""
from __future__ import annotations

import argparse
import os
import sys

from .scenarios import load_all, ATTACK_TYPES
from .defenses import DEFENSES
from .eval.runner import run_matrix, build_cells, estimate_requests
from .eval.report import write_report

DEFAULT_OUT = os.path.join("results", "run.jsonl")


def _split(csv: str) -> list[str]:
    return [x.strip() for x in csv.split(",") if x.strip()]


def _select_scenarios(ids: str | None):
    scenarios = load_all()
    if ids:
        wanted = set(_split(ids))
        scenarios = [s for s in scenarios if s.id in wanted or s.category in wanted]
    return scenarios


def cmd_list(args) -> int:
    scenarios = load_all()
    print(f"Scenarios ({len(scenarios)}):")
    for s in scenarios:
        print(f"  - {s.id:28s} [{s.category:5s}]  {s.user_task}")
    print(f"\nDefenses: {', '.join(DEFENSES)}")
    print(f"Attack types: {', '.join(ATTACK_TYPES)}")
    return 0


def cmd_run(args) -> int:
    specs = _split(args.provider)
    defenses = _split(args.defenses)
    attacks = _split(args.attacks)
    scenarios = _select_scenarios(args.scenarios)
    if not scenarios:
        print("No scenarios selected.")
        return 1

    cells = build_cells(specs, scenarios, defenses, attacks, args.trials)
    if args.dry_run:
        est = estimate_requests(cells, args.max_steps)
        print(f"Dry run: {len(cells)} cells "
              f"({len(specs)} providers × {len(scenarios)} scenarios × {len(defenses)} defenses "
              f"× {len(attacks)} attacks × {args.trials} trials)\n")
        for provider, e in est.items():
            cap = e["rpd_cap"]
            days = e["days_at_cap_typical"]
            cap_str = "unlimited" if cap is None else f"{cap}/day"
            days_str = "" if days is None else f"  (~{days} day(s) at cap)"
            print(f"  {provider}: {e['cells']} cells → "
                  f"~{e['typical_requests']} typical / {e['worst_case_requests']} worst-case requests "
                  f"| free-tier cap: {cap_str}{days_str}")
        print("\nNo requests were made. Re-run without --dry-run to execute.")
        return 0

    summary = run_matrix(specs, scenarios, defenses, attacks, args.trials, args.out,
                         max_steps=args.max_steps, max_requests=args.max_requests,
                         resume=not args.no_resume)
    print(f"\nDone: ran {summary['n_run']} cells, skipped {summary['n_skipped']} "
          f"(already done), used {summary['requests_used']} requests.")
    if summary["stopped_early"]:
        print("Stopped early: hit --max-requests budget. Re-run to resume.")
    print(f"Results: {summary['out_path']}")
    if args.report:
        print()
        write_report(args.out, os.path.dirname(args.out) or "results")
    return 0


def _build_attacker(spec: str):
    from .attacker import ScriptedAttacker, LLMAttacker
    if spec == "scripted":
        return ScriptedAttacker()
    if spec.startswith("llm:"):
        from .providers.registry import build_provider
        return LLMAttacker(build_provider(spec[len("llm:"):]))
    raise ValueError(f"unknown attacker {spec!r}; use 'scripted' or 'llm:<provider-spec>'")


def cmd_attack(args) -> int:
    from .attacker import run_adaptive
    scenarios = _select_scenarios(args.scenarios)
    defenses = _split(args.defenses)
    attacker = _build_attacker(args.attacker)

    print(f"Adaptive attack — target={args.target} attacker={args.attacker} "
          f"rounds={args.rounds}\n")
    held, fell = 0, 0
    rows = []
    for sc in scenarios:
        for d in defenses:
            res = run_adaptive(args.target, sc, d, attacker,
                               max_rounds=args.rounds, log=(print if args.verbose else None))
            status = f"BROKEN in {res.rounds_used} round(s)" if res.broken else "held"
            fell += res.broken
            held += (not res.broken)
            rows.append((sc.id, d, status))
            print(f"  {sc.id:26s} | {d:22s} | {status}")
    print(f"\nSummary: {fell} defense-cells broken, {held} held "
          f"(across {len(scenarios)} scenarios × {len(defenses)} defenses).")
    print("Interpretation: content/prompt defenses tend to fall to an adaptive attacker; "
          "structural gating tends to hold.")
    return 0


def cmd_report(args) -> int:
    if not os.path.exists(args.infile):
        print(f"No results file at {args.infile}. Run `hijackbench run` first.")
        return 1
    out = write_report(args.infile, args.out_dir)
    print(f"\nWrote {out['markdown']}")
    if out["asr_plot"]:
        print(f"Wrote {out['asr_plot']}")
    if out["tradeoff_plot"]:
        print(f"Wrote {out['tradeoff_plot']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="hijackbench", description="Agent security red-team benchmark.")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="list scenarios and defenses")
    p_list.set_defaults(func=cmd_list)

    p_run = sub.add_parser("run", help="run the benchmark matrix")
    p_run.add_argument("--provider", default="mock", help="comma-separated provider specs (default: mock)")
    p_run.add_argument("--defenses", default="none,datamark", help="comma-separated defenses")
    p_run.add_argument("--attacks", default=",".join(ATTACK_TYPES), help="comma-separated attack types")
    p_run.add_argument("--scenarios", default=None, help="comma-separated scenario ids or categories")
    p_run.add_argument("--trials", type=int, default=1)
    p_run.add_argument("--max-steps", type=int, default=8)
    p_run.add_argument("--max-requests", type=int, default=None, help="hard budget cap for this run")
    p_run.add_argument("--out", default=DEFAULT_OUT)
    p_run.add_argument("--no-resume", action="store_true", help="do not skip already-completed cells")
    p_run.add_argument("--dry-run", action="store_true", help="estimate request budget without running")
    p_run.add_argument("--report", action="store_true", help="write report artifacts after the run")
    p_run.set_defaults(func=cmd_run)

    p_atk = sub.add_parser("attack", help="run the adaptive attacker against defended targets")
    p_atk.add_argument("--target", default="mock", help="target provider spec (default: mock)")
    p_atk.add_argument("--attacker", default="scripted",
                       help="'scripted' (offline) or 'llm:<provider-spec>'")
    p_atk.add_argument("--defenses", default="datamark,sanitizer,privilege_gate",
                       help="comma-separated defenses to attack")
    p_atk.add_argument("--scenarios", default=None)
    p_atk.add_argument("--rounds", type=int, default=5)
    p_atk.add_argument("--verbose", action="store_true", help="log each attack round")
    p_atk.set_defaults(func=cmd_attack)

    p_rep = sub.add_parser("report", help="aggregate results into a leaderboard + plots")
    p_rep.add_argument("--in", dest="infile", default=DEFAULT_OUT)
    p_rep.add_argument("--out-dir", default="results")
    p_rep.set_defaults(func=cmd_report)
    return p


def _force_utf8_stdout() -> None:
    # Windows consoles default to cp1252 and choke on →, ×, ↓ etc. Make output UTF-8.
    for stream in ("stdout", "stderr"):
        s = getattr(sys, stream, None)
        try:
            s.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass


def main(argv=None) -> int:
    _force_utf8_stdout()
    args = build_parser().parse_args(argv)
    return args.func(args)
