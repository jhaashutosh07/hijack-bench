"""Shared constants for the untrusted-data envelope used by the `datamark` defense.

Kept in one place because both the defense (which wraps tool outputs) and the
`mock` provider (which models a well-behaved policy that treats enveloped text as
inert data, never as instructions) must agree on the exact delimiters.
"""

UNTRUSTED_OPEN = "<<<UNTRUSTED_TOOL_DATA>>>"
UNTRUSTED_CLOSE = "<<<END_UNTRUSTED_TOOL_DATA>>>"

# The simulated attacker's exfiltration address. A clearly non-real domain
# (RFC-2606 style) so it can never resolve to a live target.
ATTACKER_EMAIL = "attacker@evil.invalid"


def strip_untrusted(text: str) -> str:
    """Remove everything inside untrusted envelopes — i.e. what a data-marking-
    respecting model would treat as inert. Used to compute the 'instruction-
    visible' portion of tool output."""
    out = []
    i = 0
    while True:
        start = text.find(UNTRUSTED_OPEN, i)
        if start == -1:
            out.append(text[i:])
            break
        out.append(text[i:start])
        end = text.find(UNTRUSTED_CLOSE, start)
        if end == -1:
            # Unterminated envelope: treat the remainder as inert.
            break
        i = end + len(UNTRUSTED_CLOSE)
    return "".join(out)
