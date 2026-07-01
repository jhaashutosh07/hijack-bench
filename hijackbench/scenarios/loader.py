"""Load scenario packs from YAML files in scenarios/packs/."""
from __future__ import annotations

import glob
import os

import yaml

from .base import Scenario

# "clean" is always available (no injection) for measuring utility-without-attack.
ATTACK_TYPES = ["clean", "static"]

_PACKS_DIR = os.path.join(os.path.dirname(__file__), "packs")


def _scenario_from_dict(d: dict) -> Scenario:
    return Scenario(
        id=d["id"],
        category=d.get("category", "uncategorized"),
        user_task=d["user_task"],
        attack_goal=d.get("attack_goal", ""),
        tools=d["tools"],
        resources=d.get("resources", {}),
        injections=d.get("injections", {}),
        secret=d.get("secret", {}),
        hijack_check=d.get("hijack_check", {}),
        utility_check=d.get("utility_check", {}),
        mock_script=d.get("mock_script", {}),
    )


def load_pack(path: str) -> list[Scenario]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    scenarios = data.get("scenarios", data) if isinstance(data, dict) else data
    return [_scenario_from_dict(s) for s in scenarios]


def load_all(packs_dir: str | None = None) -> list[Scenario]:
    packs_dir = packs_dir or _PACKS_DIR
    out: list[Scenario] = []
    for path in sorted(glob.glob(os.path.join(packs_dir, "*.yaml"))):
        out.extend(load_pack(path))
    return out
