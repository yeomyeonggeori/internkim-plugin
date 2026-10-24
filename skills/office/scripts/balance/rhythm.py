from __future__ import annotations

from dataclasses import dataclass
import re

from balance.tokens import TIGHTEN_LEADING_LIMIT, TIGHTEN_SPACE_LIMIT, TIGHTEN_TYPE_LIMIT

SPACE_FUNCTION = re.compile(r"\bspace\(([^()]+)\)")
TYPE_FUNCTION = re.compile(r"\btype\(([^()]+)\)")
LEADING_FUNCTION = re.compile(r"\bleading\(([^()]+)\)")


@dataclass(frozen=True)
class Rhythm:
    tightness: float = 0.0

    @property
    def space(self) -> float:
        return 1 - TIGHTEN_SPACE_LIMIT * self.tightness

    @property
    def type(self) -> float:
        return 1 - TIGHTEN_TYPE_LIMIT * self.tightness

    @property
    def leading(self) -> float:
        return 1 - TIGHTEN_LEADING_LIMIT * self.tightness

    def css(self, stylesheet: str) -> str:
        scaled = LEADING_FUNCTION.sub(r"calc(\1 * var(--leading))", TYPE_FUNCTION.sub(r"calc(\1 * var(--type))", SPACE_FUNCTION.sub(r"calc(\1 * var(--space))", stylesheet)))
        return f":root {{ --space: {self.space:.4f}; --type: {self.type:.4f}; --leading: {self.leading:.4f}; }}\n{scaled}"
