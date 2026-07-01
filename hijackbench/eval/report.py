"""Turn aggregated metrics into shareable artifacts: a console table, a markdown
leaderboard, and two plots (ASR-by-defense bars + the ASR-reduction vs utility-cost
tradeoff scatter — the money graph)."""
from __future__ import annotations

import os

from .metrics import aggregate, load_records


def _fmt(x) -> str:
    return "  n/a" if x is None else f"{x:>5.2f}"


def render_markdown(agg: dict) -> str:
    lines = ["# hijack-bench leaderboard", "",
             f"_Aggregated from {agg['n_records']} run records._", "",
             "**ASR** = attack-success rate over attacked cells (lower is better). "
             "**Util(clean/atk)** = benign task completion with no attack / under attack.", "",
             "| provider | defense | ASR | Util(clean) | Util(atk) | ASR↓ vs none | Util cost |",
             "|---|---|---|---|---|---|---|"]
    scatter_lookup = {(s["provider"], s["defense"]): s for s in agg["scatter"]}
    for p in agg["providers"]:
        for d in agg["defenses"]:
            m = agg["by_defense"][p][d]
            s = scatter_lookup.get((p, d), {})
            asr_red = s.get("asr_reduction")
            util_cost = s.get("utility_cost")
            lines.append(
                f"| {p} | {d} | {_fmt(m['asr']).strip()} | {_fmt(m['utility_clean']).strip()} "
                f"| {_fmt(m['utility_attacked']).strip()} | "
                f"{'—' if asr_red is None else f'{asr_red:+.2f}'} "
                f"| {'—' if util_cost is None else f'{util_cost:+.2f}'} |"
            )

    # Defense-effectiveness by model scale (the pre-committed open question).
    scales = agg.get("scales", [])
    if len(scales) > 1 or (scales and scales[0] != "mock"):
        lines += ["", "## ASR by model scale × defense",
                  "_Does the defense ranking change with model scale? (ASR; lower is better.)_", "",
                  "| scale | " + " | ".join(agg["defenses"]) + " |",
                  "|---|" + "|".join(["---"] * len(agg["defenses"])) + "|"]
        for sc in scales:
            cells = [_fmt(agg["by_scale"][sc][d]["asr"]).strip() for d in agg["defenses"]]
            lines.append(f"| {sc} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def print_table(agg: dict) -> None:
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        print(render_markdown(agg))
        return
    table = Table(title="hijack-bench — ASR & utility by defense")
    for col in ["provider", "defense", "ASR", "Util(clean)", "Util(atk)", "ASR↓", "Util cost"]:
        table.add_column(col)
    scatter_lookup = {(s["provider"], s["defense"]): s for s in agg["scatter"]}
    for p in agg["providers"]:
        for d in agg["defenses"]:
            m = agg["by_defense"][p][d]
            s = scatter_lookup.get((p, d), {})
            asr_red = s.get("asr_reduction")
            util_cost = s.get("utility_cost")
            table.add_row(p, d, _fmt(m["asr"]), _fmt(m["utility_clean"]), _fmt(m["utility_attacked"]),
                          "—" if asr_red is None else f"{asr_red:+.2f}",
                          "—" if util_cost is None else f"{util_cost:+.2f}")
    Console().print(table)


def _plot_asr_by_defense(agg: dict, path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    providers, defenses = agg["providers"], agg["defenses"]
    x = np.arange(len(defenses))
    width = 0.8 / max(len(providers), 1)
    fig, ax = plt.subplots(figsize=(7, 4))
    for i, p in enumerate(providers):
        vals = [(agg["by_defense"][p][d]["asr"] or 0.0) for d in defenses]
        ax.bar(x + i * width, vals, width, label=p)
    ax.set_xticks(x + width * (len(providers) - 1) / 2)
    ax.set_xticklabels(defenses)
    ax.set_ylabel("Attack success rate (ASR)")
    ax.set_ylim(0, 1)
    ax.set_title("ASR by defense (lower is better)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _plot_tradeoff(agg: dict, path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    pts = [s for s in agg["scatter"] if s["asr_reduction"] is not None and s["utility_cost"] is not None]
    fig, ax = plt.subplots(figsize=(6, 5))
    for s in pts:
        ax.scatter(s["asr_reduction"], s["utility_cost"], s=80)
        ax.annotate(f"{s['defense']}\n({s['provider']})", (s["asr_reduction"], s["utility_cost"]),
                    textcoords="offset points", xytext=(6, 4), fontsize=8)
    ax.axhline(0, color="gray", lw=0.7)
    ax.set_xlabel("ASR reduction vs. none  (→ better)")
    ax.set_ylabel("Utility cost  (↑ worse)")
    ax.set_title("Defense tradeoff: attack reduction vs. utility loss")
    ax.invert_yaxis()  # good defenses (low utility cost) sit toward the top
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def write_report(records_path: str, out_dir: str) -> dict:
    records = load_records(records_path)
    agg = aggregate(records)
    os.makedirs(out_dir, exist_ok=True)

    md_path = os.path.join(out_dir, "leaderboard.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_markdown(agg))

    asr_png = os.path.join(out_dir, "asr_by_defense.png")
    scatter_png = os.path.join(out_dir, "tradeoff_scatter.png")
    plotted = True
    try:
        _plot_asr_by_defense(agg, asr_png)
        _plot_tradeoff(agg, scatter_png)
    except ImportError:
        plotted = False

    print_table(agg)
    return {"markdown": md_path,
            "asr_plot": asr_png if plotted else None,
            "tradeoff_plot": scatter_png if plotted else None,
            "agg": agg}
