"""No defense — the baseline against which every mitigation's ASR-reduction is measured."""
from __future__ import annotations

from .base import Defense


class NoDefense(Defense):
    name = "none"
