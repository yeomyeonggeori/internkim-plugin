from __future__ import annotations

import re

from charts.kinds import COMBO_CHART_KIND, SCATTER_CHART_KIND
from charts.numbers import split_chart_list


TWO_AXIS_CHARTS = (COMBO_CHART_KIND, SCATTER_CHART_KIND)
WORD_UNIT_PATTERN = re.compile(r"[A-Za-zÀ-ɏ]{2,}")


def chart_series(attributes: dict[str, str]) -> list[tuple[str, list[str]]] | str:
    if attributes.get("data-series", "").strip():
        series = []
        for part in [part.strip() for part in attributes["data-series"].split(";") if part.strip()]:
            name, separator, values = part.partition(":")
            if not separator:
                return f'data-series part "{part}" has no "name:" before its numbers'
            series.append((name.strip(), split_chart_list(values)))
        return series
    if attributes.get("data-values", "").strip():
        return [("", split_chart_list(attributes["data-values"]))]
    return "the chart has neither data-values nor data-series"


def series_axes(chart_type: str, series_count: int) -> list[int]:
    if chart_type == SCATTER_CHART_KIND:
        return [min(index, 1) for index in range(series_count)]
    if chart_type == COMBO_CHART_KIND:
        return [0] * (series_count - 1) + [1]
    return [0] * series_count


def axis_unit_texts(chart_type: str, unit_text: str) -> list[str]:
    if chart_type not in TWO_AXIS_CHARTS:
        return [unit_text.strip()] * 2
    units = [unit.strip() for unit in unit_text.split(",")]
    return [units[0], units[1] if len(units) > 1 else units[0]]


def spaced_unit(unit: str) -> str:
    trimmed = unit.strip()
    return f" {trimmed}" if WORD_UNIT_PATTERN.match(trimmed) else trimmed
