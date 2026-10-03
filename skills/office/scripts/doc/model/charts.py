from __future__ import annotations

from dataclasses import dataclass, replace

from docx.opc.constants import CONTENT_TYPE, RELATIONSHIP_TYPE
from docx.opc.part import Part
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn
from lxml import etree
from pptx.chart.chart import Chart
from pptx.enum.chart import XL_LEGEND_POSITION
from pptx.oxml import parse_xml as parse_chart_xml

from charts.combo import CHART_NAMESPACE, category_chart_data, combo_axis_ranges, combo_chart_space, lines_need_own_axis
from charts.kinds import COMBO_CHART_KIND, OFFICE_CHART_KINDS, ROUND_CHART_KINDS, document_kind, drawn_kind, is_stacked_kind, office_chart_type, plot_kind
from charts.look import ChartLook, document_look
from charts.svg import ChartModel, ChartSeries


RELATIONSHIP_NAMESPACE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
DRAWN_KINDS = {drawn_kind(kind) for kind in OFFICE_CHART_KINDS}
AxisLimits = tuple[float | None, float | None, float | None]
AUTOMATIC_AXIS: AxisLimits = (None, None, None)
CHART_TEXT_SIZE = "1000"


@dataclass(frozen=True)
class ChartSpecification:
    kind: str
    categories: tuple[str, ...]
    series: tuple[tuple[str, tuple[float, ...], bool], ...]
    title: str = ""
    legend: bool | None = None
    secondary_axis: bool | None = None
    value_axes: tuple[AxisLimits, ...] | None = None

    @property
    def uses_secondary_axis(self) -> bool:
        if self.kind != COMBO_CHART_KIND:
            return False
        if self.secondary_axis is not None:
            return self.secondary_axis
        return lines_need_own_axis(list(self.series))

    def to_dictionary(self) -> dict:
        dictionary = {
            "type": self.kind,
            "categories": list(self.categories),
            "series": [{"name": name, "values": [plain_number(value) for value in values], **({"line": True} if is_line and self.kind == COMBO_CHART_KIND else {})} for name, values, is_line in self.series],
        }
        if self.title:
            dictionary["title"] = self.title
        return dictionary

    @property
    def shows_legend(self) -> bool:
        return self.legend if self.legend is not None else len(self.series) > 1 or self.kind in ROUND_CHART_KINDS

    def model(self) -> ChartModel:
        return ChartModel(
            categories=self.categories,
            series=tuple(ChartSeries(name, values, series_kind(self.kind, is_line)) for name, values, is_line in self.series),
            title=self.title,
            stacked=is_stacked_kind(self.kind),
            secondary_axis=self.uses_secondary_axis,
        )

    def look(self, colors: tuple[str, ...]) -> ChartLook:
        look = document_look(colors, len(self.series), self.kind in ROUND_CHART_KINDS, is_stacked_kind(self.kind), self.shows_legend, None)
        primary, secondary = (*self.axis_limits(), AUTOMATIC_AXIS, AUTOMATIC_AXIS)[:2]
        return replace(look, value_limits=primary[:2], major_unit=primary[2], secondary_limits=secondary[:2])

    def axis_limits(self) -> tuple[AxisLimits, ...]:
        if self.value_axes is not None:
            return self.value_axes
        if not self.uses_secondary_axis:
            return ()
        return tuple((axis.minimum, axis.maximum, axis.step) for axis in combo_axis_ranges(list(self.series)))


@dataclass
class DocumentChart:
    index: int
    drawing: object
    part: object
    block: int | None


def series_kind(kind: str, is_line: bool) -> str:
    if kind == COMBO_CHART_KIND:
        return "line" if is_line else "column"
    return drawn_kind(kind)


def specification(operation: dict) -> ChartSpecification:
    return ChartSpecification(
        kind=operation["type"],
        categories=tuple(str(category) for category in operation["categories"]),
        series=tuple((entry["name"], tuple(float(value) for value in entry["values"]), bool(entry.get("line"))) for entry in operation["series"]),
        title=operation.get("title") or "",
        legend=operation.get("legend"),
        secondary_axis=operation.get("secondaryAxis"),
    )


def chart_space(specification: ChartSpecification):
    if specification.kind != COMBO_CHART_KIND:
        root = parse_chart_xml(category_chart_data(specification.categories, list(specification.series)).xml_bytes(office_chart_type(specification.kind)))
    else:
        root = combo_chart_space(specification.categories, list(specification.series), specification.uses_secondary_axis)
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


def chart_blob(root, workbook_relationship: str) -> bytes:
    for existing in root.findall(f"{{{CHART_NAMESPACE}}}externalData"):
        root.remove(existing)
    external = etree.SubElement(root, f"{{{CHART_NAMESPACE}}}externalData")
    external.set(f"{{{RELATIONSHIP_NAMESPACE}}}id", workbook_relationship)
    etree.SubElement(external, f"{{{CHART_NAMESPACE}}}autoUpdate").set("val", "0")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def workbook_blob(specification: ChartSpecification) -> bytes:
    return category_chart_data(specification.categories, list(specification.series)).xlsx_blob


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
    plot_charts = [child for child in root.iter() if etree.QName(child).namespace == CHART_NAMESPACE and plot_kind(etree.QName(child).localname) in DRAWN_KINDS]
    series, categories, kinds = [], (), []
    for plot_chart in plot_charts:
        kind = plot_chart_kind(plot_chart)
        kinds.append(kind)
        for element in plot_chart.findall(f"{{{CHART_NAMESPACE}}}ser"):
            labels, values = cached_points(element, "cat"), cached_points(element, "val")
            categories = categories or tuple(labels)
            series.append((series_name(element), tuple(float(value) if is_number(value) else 0.0 for value in values), kind == "line"))
    combined = COMBO_CHART_KIND if len(set(kinds)) > 1 else (kinds[0] if kinds else "column")
    title = "".join(text.text or "" for text in root.iterfind(f".//{{{CHART_NAMESPACE}}}title//{{http://schemas.openxmlformats.org/drawingml/2006/main}}t"))
    legend = root.find(f".//{{{CHART_NAMESPACE}}}legend") is not None
    secondary = len(root.findall(f".//{{{CHART_NAMESPACE}}}valAx")) > 1
    return ChartSpecification(combined, categories, tuple(series), title, legend, secondary if combined == COMBO_CHART_KIND else None, plotted_axis_limits(root, plot_charts))


def plotted_axis_limits(root, plot_charts: list) -> tuple[AxisLimits, ...]:
    value_axes = {child_value(axis, "axId"): axis for axis in root.iter(f"{{{CHART_NAMESPACE}}}valAx")}
    plotted = []
    for plot_chart in plot_charts:
        identifiers = [identifier.get("val") for identifier in plot_chart.findall(f"{{{CHART_NAMESPACE}}}axId")]
        axis = next((value_axes[identifier] for identifier in identifiers if identifier in value_axes), None)
        if axis is not None and all(axis is not seen for seen in plotted):
            plotted.append(axis)
    return tuple(axis_limits_of(axis) for axis in plotted)


def axis_limits_of(axis) -> AxisLimits:
    scaling = axis.find(f"{{{CHART_NAMESPACE}}}scaling")
    return (number_value(scaling, "min"), number_value(scaling, "max"), number_value(axis, "majorUnit"))


def number_value(parent, tag: str) -> float | None:
    value = child_value(parent, tag) if parent is not None else None
    return float(value) if value is not None and is_number(value) else None


def plot_chart_kind(plot_chart) -> str:
    drawn = plot_kind(etree.QName(plot_chart).localname, child_value(plot_chart, "barDir"))
    return document_kind(drawn, child_value(plot_chart, "grouping"))


def child_value(element, tag: str) -> str | None:
    child = element.find(f"{{{CHART_NAMESPACE}}}{tag}")
    return child.get("val") if child is not None else None


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
