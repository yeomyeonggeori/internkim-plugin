from __future__ import annotations

from openpyxl.utils import range_boundaries

from sheet.preview.colors import css_color


COMPARISONS = {
    "greaterThan": lambda value, low, high: value > low,
    "greaterThanOrEqual": lambda value, low, high: value >= low,
    "lessThan": lambda value, low, high: value < low,
    "lessThanOrEqual": lambda value, low, high: value <= low,
    "equal": lambda value, low, high: value == low,
    "notEqual": lambda value, low, high: value != low,
    "between": lambda value, low, high: min(low, high) <= value <= max(low, high),
    "notBetween": lambda value, low, high: not min(low, high) <= value <= max(low, high),
}


TEXT_TESTS = {
    "containsText": lambda text, sought: sought in text,
    "notContainsText": lambda text, sought: sought not in text,
    "beginsWith": lambda text, sought: text.startswith(sought),
    "endsWith": lambda text, sought: text.endswith(sought),
}
BLANK_TESTS = {"containsBlanks": True, "notContainsBlanks": False}


class ConditionalStyles:
    def __init__(self, worksheet, values, palette: tuple):
        self.values = values
        self.palette = palette
        self.entries = []
        for formatting in worksheet.conditional_formatting:
            cells = [cell for bounds in formatting.sqref.ranges for cell in range_cells(str(bounds))]
            for rule in formatting.rules:
                self.entries.append((set(cells), rule, self.numbers(cells)))

    def numbers(self, cells: list[tuple[int, int]]) -> list[float]:
        found = []
        for row, column in cells:
            value = self.values.cell(row=row, column=column).value
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                found.append(float(value))
        return found

    def style_for(self, row: int, column: int, value) -> dict:
        style: dict = {}
        for cells, rule, numbers in sorted(self.entries, key=lambda entry: entry[1].priority or 0, reverse=True):
            if (row, column) in cells:
                style.update(self.rule_style(rule, value, numbers))
        return style

    def rule_style(self, rule, value, numbers: list[float]) -> dict:
        if rule.type in TEXT_TESTS:
            matches = value is not None and TEXT_TESTS[rule.type](str(value).casefold(), (rule.text or "").casefold())
            return differential_style(rule.dxf, self.palette) if matches else {}
        if rule.type in BLANK_TESTS:
            is_blank = value is None or str(value).strip() == ""
            return differential_style(rule.dxf, self.palette) if is_blank == BLANK_TESTS[rule.type] else {}
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return {}
        return self.number_style(rule, float(value), numbers)

    def number_style(self, rule, value: float, numbers: list[float]) -> dict:
        if rule.type == "cellIs":
            return self.cell_is_style(rule, value)
        if rule.type == "colorScale" and rule.colorScale is not None:
            return {"background": scale_color(rule.colorScale, value, numbers, self.palette)}
        if rule.type == "dataBar" and rule.dataBar is not None and numbers:
            low, high = min(min(numbers), 0), max(numbers)
            share = 100 * (value - low) / (high - low) if high > low else 100
            return {"bar": (max(0.0, min(100.0, share)), css_color(rule.dataBar.color, self.palette) or "#638ec6")}
        return {}

    def cell_is_style(self, rule, value: float) -> dict:
        operands = [self.operand(formula) for formula in rule.formula or []]
        if not operands or any(operand is None for operand in operands):
            return {}
        test = COMPARISONS.get(rule.operator)
        if test is None or not test(value, operands[0], operands[-1]):
            return {}
        return differential_style(rule.dxf, self.palette)

    def operand(self, formula: str) -> float | None:
        text = formula.strip().lstrip("=")
        try:
            return float(text)
        except ValueError:
            pass
        try:
            column, row, _, _ = range_boundaries(text.replace("$", ""))
        except (ValueError, TypeError):
            return None
        value = self.values.cell(row=row, column=column).value
        return float(value) if isinstance(value, (int, float)) else None


def range_cells(text: str) -> list[tuple[int, int]]:
    min_column, min_row, max_column, max_row = range_boundaries(text)
    return [(row, column) for row in range(min_row, max_row + 1) for column in range(min_column, max_column + 1)]


def differential_style(dxf, palette: tuple) -> dict:
    if dxf is None:
        return {}
    style = {}
    if dxf.font is not None and dxf.font.color is not None:
        style["color"] = css_color(dxf.font.color, palette)
    if dxf.fill is not None:
        fill_color = css_color(getattr(dxf.fill, "bgColor", None), palette) or css_color(getattr(dxf.fill, "fgColor", None), palette)
        if fill_color:
            style["background"] = fill_color
    return {name: value for name, value in style.items() if value}


def scale_color(color_scale, value: float, numbers: list[float], palette: tuple) -> str | None:
    colors = [css_color(color, palette) for color in color_scale.color]
    points = [threshold(cfvo, numbers) for cfvo in color_scale.cfvo]
    if not numbers or None in colors or None in points or len(colors) != len(points):
        return None
    for (low, low_color), (high, high_color) in zip(zip(points, colors), list(zip(points, colors))[1:]):
        if value <= high or high == points[-1]:
            share = 0.0 if high == low else max(0.0, min(1.0, (value - low) / (high - low)))
            return mixed(low_color, high_color, share)
    return colors[-1]


def threshold(cfvo, numbers: list[float]) -> float | None:
    if not numbers:
        return None
    ordered = sorted(numbers)
    if cfvo.type == "min":
        return ordered[0]
    if cfvo.type == "max":
        return ordered[-1]
    if cfvo.type == "num":
        return float(cfvo.val)
    if cfvo.type in ("percent", "percentile"):
        share = float(cfvo.val) / 100
        if cfvo.type == "percent":
            return ordered[0] + (ordered[-1] - ordered[0]) * share
        return ordered[min(len(ordered) - 1, int(round(share * (len(ordered) - 1))))]
    return None


def mixed(low: str, high: str, share: float) -> str:
    channels = [round(int(low[index:index + 2], 16) * (1 - share) + int(high[index:index + 2], 16) * share) for index in (1, 3, 5)]
    return "#" + "".join(f"{channel:02x}" for channel in channels)
