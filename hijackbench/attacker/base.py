"""Attacker interface + result types for the adaptive attack loop.

An `Attacker` proposes an injection payload given the target defense and the history of
what has failed so far. This is the honest definition of "adaptive": the payload is a
function of the defense being attacked and prior failures — not a fixed string an author
imagined would work.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class AttackRound:
    payload: str
    hijacked: bool
    note: str = ""


@dataclass
class AdaptiveResult:
    scenario_id: str
    defense: str
    target: str
    broken: bool            # did any round succeed?
    rounds_used: int
    winning_payload: str | None
    history: list[AttackRound] = field(default_factory=list)

    @property
    def asr(self) -> float:
        if not self.history:
            return 0.0
        return sum(1 for r in self.history if r.hijacked) / len(self.history)


class Attacker(ABC):
    name: str = "base"

    @abstractmethod
    def propose(self, defense: str, scenario, history: list[AttackRound]) -> str:
        """Return the next injection payload to try."""
        ...
