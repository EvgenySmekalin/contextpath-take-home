"""Rules: what ``rules.json`` looks like and how its patterns match."""

import json
import re
from functools import cached_property, lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, model_validator

# One pattern, or several of which any may match.
Pattern = str | list[str]


class Conditions(BaseModel):
    # A misspelt condition name is an error. Ignoring it would leave a rule
    # with one condition fewer, firing far too often.
    model_config = ConfigDict(extra="forbid")

    click: Pattern | None = None
    process: Pattern | None = None
    window_title: Pattern | None = None
    clipboard: Pattern | None = None
    ocr: Pattern | None = None


class PopupText(BaseModel):
    title: str = ""
    body: str = ""


class Rule(BaseModel):
    id: str
    when: Conditions
    popup: PopupText

    @cached_property
    def conditions(self) -> dict[str, Pattern]:
        """Only the conditions the rule actually sets."""
        return self.when.model_dump(exclude_none=True)

    @model_validator(mode="after")
    def _has_a_condition(self) -> "Rule":
        if not self.conditions:
            raise ValueError(f"rule {self.id!r} has no conditions")
        return self


def load_rules(path: str) -> list[Rule]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Rule.model_validate(rule) for rule in document["rules"]]


def matches(pattern: Pattern, text: str) -> bool:
    """``*`` stands for any characters; everything else is literal, case ignored.

    The pattern has to cover the whole text: "Delete" does not match "Delete Case".
    """
    patterns = [pattern] if isinstance(pattern, str) else pattern
    return any(_regex(p).fullmatch(text) for p in patterns)


@lru_cache
def _regex(pattern: str) -> re.Pattern:
    literal_parts = (re.escape(part) for part in pattern.strip().split("*"))
    return re.compile(".*".join(literal_parts), re.IGNORECASE | re.DOTALL)


def fill(template: str, matched: dict[str, str]) -> str:
    """Replace ``{click}``, ``{window_title}``... with the text each condition matched."""
    return re.sub(r"\{(\w+)\}", lambda m: matched.get(m.group(1), m.group(0)), template)
