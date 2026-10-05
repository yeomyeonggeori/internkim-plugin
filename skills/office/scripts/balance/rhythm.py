from __future__ import annotations

from dataclasses import dataclass
import re

from balance.tokens import GROW_INSET_MILLIMETERS, GROW_SPACE_LIMIT, GROW_TYPE_LIMIT, LEADING_LIMIT, TIGHTEN_SPACE_LIMIT, TIGHTEN_TYPE_LIMIT

SPACE_FUNCTION = re.compile(r"\bspace\(([^()]+)\)")
TYPE_FUNCTION = re.compile(r"\btype\(([^()]+)\)")
LEADING_FUNCTION = re.compile(r"\bleading\(([^()]+)\)")


@dataclass(frozen=True)
class Rhythm:
    airiness: float = 0.0
    lift_points: float = 0.0

    @property
    def space(self) -> float:
        return 1 + (GROW_SPACE_LIMIT if self.airiness > 0 else TIGHTEN_SPACE_LIMIT) * self.airiness

    @property
    def type(self) -> float:
        return 1 + (GROW_TYPE_LIMIT if self.airiness > 0 else TIGHTEN_TYPE_LIMIT) * self.airiness

    @property
    def leading(self) -> float:
        return 1 + LEADING_LIMIT * self.airiness

    @property
    def inset_millimeters(self) -> float:
        return GROW_INSET_MILLIMETERS * max(self.airiness, 0.0)

    def lifted(self, html: str) -> str:
        return f'<div class="lift"></div>{html}' if self.lift_points else html

    def css(self, stylesheet: str) -> str:
        scaled = LEADING_FUNCTION.sub(r"calc(\1 * var(--leading))", TYPE_FUNCTION.sub(r"calc(\1 * var(--type))", SPACE_FUNCTION.sub(r"calc(\1 * var(--space))", stylesheet)))
        return f":root {{ --space: {self.space:.4f}; --type: {self.type:.4f}; --leading: {self.leading:.4f}; --lift: {self.lift_points:.2f}pt; --inset: {self.inset_millimeters:.2f}mm; }}\n.lift {{ height: var(--lift); }}\n{scaled}"
