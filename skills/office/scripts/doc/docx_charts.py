from __future__ import annotations

import copy
from dataclasses import dataclass

from docx.opc.constants import CONTENT_TYPE, RELATIONSHIP_TYPE
from docx.opc.part import Part
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn
from lxml import etree
from pptx.chart.chart import Chart
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.oxml import parse_xml as parse_chart_xml

from chart_svg import ChartModel, ChartSeries


CHART_NAMESPACE = "http://schemas.openxmlformats.org/drawingml/2006/chart"
RELATIONSHIP_NAMESPACE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CHART_KINDS = ("column", "stacked_column", "bar", "stacked_bar", "line", "area", "pie", "doughnut", "combo")
NATIVE_TYPES = {
    "column": XL_CHART_TYPE.COLUMN_CLUSTERED,
    "stacked_column": XL_CHART_TYPE.COLUMN_STACKED,
    "bar": XL_CHART_TYPE.BAR_CLUSTERED,
    "stacked_bar": XL_CHART_TYPE.BAR_STACKED,
    "line": XL_CHART_TYPE.LINE_MARKERS,
    "area": XL_CHART_TYPE.AREA,
    "pie": XL_CHART_TYPE.PIE,
    "doughnut": XL_CHART_TYPE.DOUGHNUT,
}
SERIES_KINDS = {"column": "column", "stacked_column": "column", "bar": "bar", "stacked_bar": "bar", "line": "line", "area": "area", "pie": "pie", "doughnut": "doughnut"}
ROUND_KINDS = ("pie", "doughnut")
PLOT_TAGS = {"barChart", "bar3DChart", "lineChart", "line3DChart", "pieChart", "pie3DChart", "doughnutChart", "areaChart", "area3DChart"}
SECONDARY_AXIS_RATIO = 0.1
SECONDARY_AXIS_IDENTIFIERS = ("50010", "50020")
CHART_TEXT_SIZE = "1000"


@dataclass(frozen=True)
class ChartSpecification:
    kind: str
    categories: tuple[str, ...]
    series: tuple[tuple[str, tuple[float, ...], bool], ...]
    title: str = ""
    legend: bool | None = None
    secondary_axis: bool | None = None

    @property
    def uses_secondary_axis(self) -> bool:
        if self.kind != "combo":
            return False
        if self.secondary_axis is not None:
            return self.secondary_axis
        lines = [abs(value) for _, values, is_line in self.series if is_line for value in values]
        columns = [abs(value) for _, values, is_line in self.series if not is_line for value in values]
        if not lines or not columns or max(lines) == 0 or max(columns) == 0:
            return False
        ratio = max(lines) / max(columns)
        return ratio < SECONDARY_AXIS_RATIO or ratio > 1 / SECONDARY_AXIS_RATIO

    def to_dictionary(self) -> dict:
        dictionary = {
            "type": self.kind,
            "categories": list(self.categories),
            "series": [{"name": name, "values": [plain_number(value) for value in values], **({"line": True} if is_line and self.kind == "combo" else {})} for name, values, is_line in self.series],
        }
        if self.title:
            dictionary["title"] = self.title
        return dictionary

    @property
    def shows_legend(self) -> bool:
        return self.legend if self.legend is not None else len(self.series) > 1 or self.kind in ROUND_KINDS

    def model(self) -> ChartModel:
        return ChartModel(
            categories=self.categories,
            series=tuple(ChartSeries(name, values, series_kind(self.kind, is_line)) for name, values, is_line in self.series),
            title=self.title,
            stacked=self.kind.startswith("stacked"),
            legend=self.shows_legend,
            secondary_axis=self.uses_secondary_axis,
        )


@dataclass
class DocumentChart:
    index: int
    drawing: object
    part: object
    block: int | None


def series_kind(kind: str, is_line: bool) -> str:
    if kind == "combo":
        return "line" if is_line else "column"
    return SERIES_KINDS[kind]


def specification(operation: dict) -> ChartSpecification:
    return ChartSpecification(
        kind=operation["type"],
        categories=tuple(str(category) for category in operation["categories"]),
        series=tuple((entry["name"], tuple(float(value) for value in entry["values"]), bool(entry.get("line"))) for entry in operation["series"]),
        title=operation.get("title") or "",
        legend=operation.get("legend"),
        secondary_axis=operation.get("secondaryAxis"),
    )


def chart_data(categories: tuple[str, ...], series: list[tuple[str, tuple[float, ...], bool]]) -> CategoryChartData:
    data = CategoryChartData()
    data.categories = list(categories)
    for name, values, _ in series:
        data.add_series(name, list(values))
    return data


def chart_space(specification: ChartSpecification):
    if specification.kind != "combo":
        root = parse_chart_xml(chart_data(specification.categories, list(specification.series)).xml_bytes(NATIVE_TYPES[specification.kind]))
    else:
        root = combo_chart_space(specification)
    chart = Chart(root, None)
    chart.has_title = bool(specification.title)
    if specification.title:
        chart.chart_title.text_frame.text = specification.title
    chart.has_legend = specification.shows_legend
    if chart.has_legend:
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
    for size in root.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}defRPr"):
        size.set("sz", CHART_TEXT_SIZE)
    return root


def combo_chart_space(specification: ChartSpecification):
    all_series = list(specification.series)
    root = parse_chart_xml(chart_data(specification.categories, all_series).xml_bytes(XL_CHART_TYPE.COLUMN_CLUSTERED))
    bar_chart = root.find(f".//{{{CHART_NAMESPACE}}}barChart")
    line_source = parse_chart_xml(chart_data(specification.categories, all_series).xml_bytes(XL_CHART_TYPE.LINE_MARKERS))
    line_chart = line_source.find(f".//{{{CHART_NAMESPACE}}}lineChart")
    for bar_series_element, line_series_element, (_, _, is_line) in zip(bar_chart.findall(f"{{{CHART_NAMESPACE}}}ser"), line_chart.findall(f"{{{CHART_NAMESPACE}}}ser"), all_series):
        (bar_chart if is_line else line_chart).remove(bar_series_element if is_line else line_series_element)
    for axis_identifier in line_chart.findall(f"{{{CHART_NAMESPACE}}}axId"):
        line_chart.remove(axis_identifier)
    for axis_identifier in bar_chart.findall(f"{{{CHART_NAMESPACE}}}axId"):
        line_chart.append(copy.deepcopy(axis_identifier))
    bar_chart.addnext(line_chart)
    if specification.uses_secondary_axis:
        add_secondary_axes(root, line_chart)
    return root


def add_secondary_axes(root, line_chart) -> None:
    category_axis = root.find(f".//{{{CHART_NAMESPACE}}}catAx")
    value_axis = root.find(f".//{{{CHART_NAMESPACE}}}valAx")
    category_identifier, value_identifier = SECONDARY_AXIS_IDENTIFIERS
    for axis_identifier, new_identifier in zip(line_chart.findall(f"{{{CHART_NAMESPACE}}}axId"), SECONDARY_AXIS_IDENTIFIERS):
        axis_identifier.set("val", new_identifier)
    hidden_category = copy.deepcopy(category_axis)
    set_child(hidden_category, "axId", category_identifier)
    set_child(hidden_category, "delete", "1")
    set_child(hidden_category, "crossAx", value_identifier)
    right_values = copy.deepcopy(value_axis)
    set_child(right_values, "axId", value_identifier)
    set_child(right_values, "axPos", "r")
    set_child(right_values, "crossAx", category_identifier)
    set_child(right_values, "crosses", "max")
    gridlines = right_values.find(f"{{{CHART_NAMESPACE}}}majorGridlines")
    if gridlines is not None:
        right_values.remove(gridlines)
    value_axis.addnext(right_values)
    value_axis.addnext(hidden_category)


def set_child(element, tag: str, value: str) -> None:
    element.find(f"{{{CHART_NAMESPACE}}}{tag}").set("val", value)


def chart_blob(root, workbook_relationship: str) -> bytes:
    for existing in root.findall(f"{{{CHART_NAMESPACE}}}externalData"):
        root.remove(existing)
    external = etree.SubElement(root, f"{{{CHART_NAMESPACE}}}externalData")
    external.set(f"{{{RELATIONSHIP_NAMESPACE}}}id", workbook_relationship)
    etree.SubElement(external, f"{{{CHART_NAMESPACE}}}autoUpdate").set("val", "0")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def workbook_blob(specification: ChartSpecification) -> bytes:
    return chart_data(specification.categories, list(specification.series)).xlsx_blob


def add_chart_part(document, specification: ChartSpecification) -> str:
    package = document.part.package
    chart_part = Part(package.next_partname("/word/charts/chart%d.xml"), CONTENT_TYPE.DML_CHART, b"", package)
    workbook_part = Part(package.next_partname("/word/embeddings/Microsoft_Excel_Worksheet%d.xlsx"), CONTENT_TYPE.SML_SHEET, workbook_blob(specification), package)
    workbook_relationship = chart_part.relate_to(workbook_part, RELATIONSHIP_TYPE.PACKAGE)
    chart_part._blob = chart_blob(chart_space(specification), workbook_relationship)
    return document.part.relate_to(chart_part, RELATIONSHIP_TYPE.CHART)


def rewrite_chart_part(chart_part, specification: ChartSpecification) -> None:
    workbook_relationship = next((identifier for identifier, relationship in chart_part.rels.items() if relationship.reltype == RELATIONSHIP_TYPE.PACKAGE), None)
    if workbook_relationship is None:
        package = chart_part.package
        workbook_part = Part(package.next_partname("/word/embeddings/Microsoft_Excel_Worksheet%d.xlsx"), CONTENT_TYPE.SML_SHEET, b"", package)
        workbook_relationship = chart_part.relate_to(workbook_part, RELATIONSHIP_TYPE.PACKAGE)
    chart_part.rels[workbook_relationship].target_part._blob = workbook_blob(specification)
    chart_part._blob = chart_blob(chart_space(specification), workbook_relationship)


def drawing_run(relationship_id: str, width_emu: int, height_emu: int, drawing_id: int, name: str):
    return parse_xml(
        f'<w:r {nsdecls("w", "wp", "a", "c", "r")}><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
        f'<wp:extent cx="{width_emu}" cy="{height_emu}"/><wp:effectExtent l="0" t="0" r="0" b="0"/>'
        f'<wp:docPr id="{drawing_id}" name="{name}"/><wp:cNvGraphicFramePr/>'
        f'<a:graphic><a:graphicData uri="{CHART_NAMESPACE}"><c:chart r:id="{relationship_id}"/></a:graphicData></a:graphic>'
        "</wp:inline></w:drawing></w:r>"
    )


def next_drawing_id(document) -> int:
    identifiers = [int(value) for value in document.element.xpath("//wp:docPr/@id") if str(value).isdigit()]
    return max(identifiers, default=0) + 1


def chart_references(element) -> list:
    return [reference for reference in element.iter(f"{{{CHART_NAMESPACE}}}chart") if reference.get(f"{{{RELATIONSHIP_NAMESPACE}}}id")]


def document_charts(document, blocks: list) -> list[DocumentChart]:
    charts = []
    block_of = {id(element): index for index, element in enumerate(blocks)}
    for reference in chart_references(document.element.body):
        relationship_id = reference.get(f"{{{RELATIONSHIP_NAMESPACE}}}id")
        if relationship_id not in document.part.rels:
            continue
        drawing = next(reference.iterancestors(qn("w:drawing")), None)
        block = next((block_of[id(ancestor)] for ancestor in reference.iterancestors() if id(ancestor) in block_of), None)
        charts.append(DocumentChart(len(charts), drawing, document.part.rels[relationship_id].target_part, block))
    return charts


def read_specification(chart_part) -> ChartSpecification:
    root = etree.fromstring(chart_part.blob)
    plot_charts = [child for child in root.iter() if etree.QName(child).localname in PLOT_TAGS and etree.QName(child).namespace == CHART_NAMESPACE]
    series, categories, kinds = [], (), []
    for plot_chart in plot_charts:
        kind = plot_kind(plot_chart)
        kinds.append(kind)
        for element in plot_chart.findall(f"{{{CHART_NAMESPACE}}}ser"):
            labels, values = cached_points(element, "cat"), cached_points(element, "val")
            categories = categories or tuple(labels)
            series.append((series_name(element), tuple(float(value) if is_number(value) else 0.0 for value in values), kind == "line"))
    combined = "combo" if len(set(kinds)) > 1 else (kinds[0] if kinds else "column")
    title = "".join(text.text or "" for text in root.iterfind(f".//{{{CHART_NAMESPACE}}}title//{{http://schemas.openxmlformats.org/drawingml/2006/main}}t"))
    legend = root.find(f".//{{{CHART_NAMESPACE}}}legend") is not None
    secondary = len(root.findall(f".//{{{CHART_NAMESPACE}}}valAx")) > 1
    return ChartSpecification(combined, categories, tuple(series), title, legend, secondary if combined == "combo" else None)


def plot_kind(plot_chart) -> str:
    name = etree.QName(plot_chart).localname.replace("3D", "")
    if name == "barChart":
        direction = plot_chart.find(f"{{{CHART_NAMESPACE}}}barDir")
        grouping = plot_chart.find(f"{{{CHART_NAMESPACE}}}grouping")
        base = "bar" if direction is not None and direction.get("val") == "bar" else "column"
        stacked = grouping is not None and grouping.get("val") in ("stacked", "percentStacked")
        return f"stacked_{base}" if stacked else base
    return {"lineChart": "line", "pieChart": "pie", "doughnutChart": "doughnut", "areaChart": "area"}.get(name, "column")


def cached_points(series_element, tag: str) -> list[str]:
    container = series_element.find(f"{{{CHART_NAMESPACE}}}{tag}")
    if container is None:
        return []
    points = sorted(container.iter(f"{{{CHART_NAMESPACE}}}pt"), key=lambda point: int(point.get("idx", "0")))
    return [point.findtext(f"{{{CHART_NAMESPACE}}}v") or "" for point in points]


def series_name(series_element) -> str:
    text = series_element.find(f"{{{CHART_NAMESPACE}}}tx")
    if text is None:
        return ""
    return "".join(value.text or "" for value in text.iter(f"{{{CHART_NAMESPACE}}}v"))


def is_number(text: str) -> bool:
    try:
        float(text)
        return True
    except ValueError:
        return False


def describe(chart: DocumentChart) -> dict:
    return {"chart": chart.index, "block": chart.block, **read_specification(chart.part).to_dictionary()}


def plain_number(value: float) -> int | float:
    return int(value) if float(value).is_integer() else value
