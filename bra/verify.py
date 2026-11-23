"""Guardrail: every number in a draft must come from the analysis.

The verifier extracts each numeric token from the draft and checks it against the registry
of numbers the analysis formatted. Any unknown number (for example one a language model
invented or rounded differently) fails the draft.
"""
import re

TOKEN = re.compile(r"[-+]?\$?\d[\d,]*(?:\.\d+)?(?:[KM%])?")


def numbers_in(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text) if any(ch.isdigit() for ch in t)]


def verify(draft: str, allowed: set[str]) -> tuple[bool, list[str]]:
    allowed_parts = set()
    for a in allowed:  # dates and similar are registered whole; accept their parts too
        allowed_parts.update(numbers_in(a))
    unknown = [t for t in numbers_in(draft) if t not in allowed and t not in allowed_parts]
    return (len(unknown) == 0, unknown)
