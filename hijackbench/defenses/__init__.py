from .base import Defense
from .none import NoDefense
from .datamark import DataMarkDefense
from .instruction_hierarchy import InstructionHierarchyDefense
from .sanitizer import SanitizerDefense
from .privilege_gate import PrivilegeGateDefense

DEFENSES: dict[str, type[Defense]] = {
    "none": NoDefense,
    "datamark": DataMarkDefense,
    "instruction_hierarchy": InstructionHierarchyDefense,
    "sanitizer": SanitizerDefense,
    "privilege_gate": PrivilegeGateDefense,
}


def build_defense(name: str) -> Defense:
    if name not in DEFENSES:
        raise ValueError(f"unknown defense {name!r}; known: {list(DEFENSES)}")
    return DEFENSES[name]()


__all__ = ["Defense", "NoDefense", "DataMarkDefense", "InstructionHierarchyDefense",
           "SanitizerDefense", "PrivilegeGateDefense", "DEFENSES", "build_defense"]
