from .base import Defense
from .none import NoDefense
from .datamark import DataMarkDefense

# Registry of defenses available in M1. M2/M3 add: instruction_hierarchy, sanitizer,
# privilege_gate (+ the automated adaptive attacker).
DEFENSES: dict[str, type[Defense]] = {
    "none": NoDefense,
    "datamark": DataMarkDefense,
}


def build_defense(name: str) -> Defense:
    if name not in DEFENSES:
        raise ValueError(f"unknown defense {name!r}; known: {list(DEFENSES)}")
    return DEFENSES[name]()


__all__ = ["Defense", "NoDefense", "DataMarkDefense", "DEFENSES", "build_defense"]
