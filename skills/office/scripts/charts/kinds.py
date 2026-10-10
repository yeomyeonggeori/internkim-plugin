from __future__ import annotations


ROUND_CHART_KINDS = ("pie", "doughnut")
OFFICE_CHART_TYPE_NAMES = {
    "column": "COLUMN_CLUSTERED",
    "stacked_column": "COLUMN_STACKED",
    "bar": "BAR_CLUSTERED",
    "stacked_bar": "BAR_STACKED",
    "line": "LINE_MARKERS",
    "area": "AREA",
    "pie": "PIE",
    "doughnut": "DOUGHNUT",
}
OFFICE_CHART_KINDS = tuple(OFFICE_CHART_TYPE_NAMES)
COMBO_CHART_KIND = "combo"
SCATTER_CHART_KIND = "scatter"
DOCUMENT_CHART_KINDS = (*OFFICE_CHART_KINDS, COMBO_CHART_KIND)
DECK_CHART_KINDS = (*DOCUMENT_CHART_KINDS, SCATTER_CHART_KIND)
SHEET_CHART_TYPES = ("bar", "line", "pie", "area", "doughnut", SCATTER_CHART_KIND, "radar", COMBO_CHART_KIND)
KIT_CHART_NAMES = {"stacked": "stacked_column", "donut": "doughnut"}
KIT_STACKED_CHARTS = ("stacked", "stacked100", "area")
STACKED_PREFIX = "stacked_"
PLOT_KINDS = {
    "barChart": "column",
    "bar3DChart": "column",
    "lineChart": "line",
    "line3DChart": "line",
    "areaChart": "area",
    "area3DChart": "area",
    "pieChart": "pie",
    "pie3DChart": "pie",
    "ofPieChart": "pie",
    "doughnutChart": "doughnut",
    "scatterChart": "scatter",
    "radarChart": "radar",
}
HORIZONTAL_BAR_DIRECTION = "bar"
STACKED_GROUPINGS = ("stacked", "percentStacked")
PERCENT_GROUPING = "percentStacked"


def office_chart_type(kind: str):
    from pptx.enum.chart import XL_CHART_TYPE

    return getattr(XL_CHART_TYPE, OFFICE_CHART_TYPE_NAMES[kind])


def plot_kind(tag: str, bar_direction: str | None = None) -> str | None:
    kind = PLOT_KINDS.get(tag)
    return "bar" if kind == "column" and bar_direction == HORIZONTAL_BAR_DIRECTION else kind


def document_kind(drawn_kind: str, grouping: str | None) -> str:
    return f"{STACKED_PREFIX}{drawn_kind}" if drawn_kind in ("column", "bar") and grouping in STACKED_GROUPINGS else drawn_kind


def drawn_kind(document_chart_kind: str) -> str:
    return document_chart_kind.removeprefix(STACKED_PREFIX)


def is_stacked_kind(document_chart_kind: str) -> bool:
    return document_chart_kind.startswith(STACKED_PREFIX)


def kit_document_kind(kit_kind: str) -> str:
    return KIT_CHART_NAMES.get(kit_kind, kit_kind)


def is_round_kind(kind: str) -> bool:
    return kit_document_kind(kind) in ROUND_CHART_KINDS


def single_slice_problem(kind: str, slice_count: int) -> str:
    if not is_round_kind(kind) or slice_count != 1:
        return ""
    return (f"a {kind} chart shows parts of one whole, so a single slice fills the whole ring and reads as 100%; "
            "add the rest of the whole as its own slice when the figures give it, or show the share as a number instead")
