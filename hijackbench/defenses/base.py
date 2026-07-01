"""Defense interface.

A defense is a set of three hooks applied by the ReAct loop, so the same agent and
scenarios run unchanged under every defense (clean A/B):

  system_suffix        -> extra system-prompt text (e.g. instruction hierarchy)
  transform_tool_output-> rewrite untrusted tool output (e.g. data-marking, sanitizing)
  authorize            -> allow/deny a tool call before it runs (e.g. privilege gating)

The base class is a no-op; subclasses override what they need.
"""
from __future__ import annotations


class Defense:
    name: str = "base"

    def system_suffix(self, scenario) -> str:
        return ""

    def transform_tool_output(self, tool_name: str, output: str, scenario) -> str:
        return output

    def authorize(self, tool_name: str, args: dict, scenario) -> tuple[bool, str]:
        return True, ""
