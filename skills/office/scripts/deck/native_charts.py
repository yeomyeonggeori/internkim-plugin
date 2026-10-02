from __future__ import annotations

from dataclasses import dataclass
import zipfile

from charts.kinds import is_round_kind
from charts.look import PERCENT_FORMAT
from core.excel_limits import DEFAULT_SHEET_NAME
from deck.chart_workbook import cell_reference, chart_workbook_bytes, number_text
from core.css_color import most_contrasting, parse_css_color
from deck.pptx_package import xml_document
from core.xml_text import text_content
from deck.pptx_text import SlideScale, TextContext, attribute, color_xml, run_properties_xml


CHART_NAMESPACES = (
    'xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
)
CHART_RELATIONSHIP_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart"
PACKAGE_RELATIONSHIP_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/package"
CHART_URI = "http://schemas.openxmlformats.org/drawingml/2006/chart"
BAR_DIRECTIONS = {"column": "col", "stacked": "col", "stacked100": "col", "bar": "bar"}
BAR_GROUPINGS = {"column": "clustered", "bar": "clustered", "stacked": "stacked", "stacked100": "percentStacked"}
NATIVE_CHART_TYPES = (*BAR_DIRECTIONS, "line", "area", "combo", "scatter", "donut", "pie")
LABEL_POSITIONS = {"column": "outEnd", "stacked": "ctr", "stacked100": "ctr", "bar": "outEnd", "line": "t", "area": "", "scatter": "r", "pie": "ctr"}
GRIDDED_CHART_TYPES = {"line", "area"}
GRID_INTERVALS = 2
DONUT_HOLE_PERCENT = 60
LINE_WIDTH_PIXELS = 5
MARKER_PIXELS = 16
SCATTER_MARKER_PIXELS = 22
SLICE_GAP_PIXELS = 2
AXIS_LINE_PIXELS = 2
GRID_LINE_PIXELS = 1
CATEGORY_AXIS_ID = 1001
VALUE_AXIS_ID = 1002
SECONDARY_CATEGORY_AXIS_ID = 1003
SECONDARY_VALUE_AXIS_ID = 1004
NO_FILL = "<c:spPr><a:noFill/><a:ln><a:noFill/></a:ln></c:spPr>"


@dataclass(frozen=True)
class ChartPart:
    number: int
    relationship_id: str
    layout: dict

    @property
    def part_name(self) -> str:
        return f"ppt/charts/chart{self.number}.xml"

    @property
    def workbook_name(self) -> str:
        return f"ppt/embeddings/Microsoft_Excel_Worksheet{self.number}.xlsx"


def chart_text_styles(slides: list[dict]) -> list[dict]:
    charts = [chart for slide in slides for chart in slide.get("charts", [])]
    return [style for chart in charts for style in chart["text"].values()] + [label["text"] for chart in charts for label in chart["pointLabels"]]


def chart_count(slides: list[dict]) -> int:
    return sum(len(slide.get("charts", [])) for slide in slides)


def slide_chart_parts(charts: list[dict], first_number: int, first_relationship_number: int) -> list[ChartPart]:
    return [ChartPart(first_number + index, f"rId{first_relationship_number + index}", layout) for index, layout in enumerate(charts)]


def chart_relationships_xml(parts: list[ChartPart]) -> str:
    return "".join(
        f'<Relationship Id="{part.relationship_id}" Type="{CHART_RELATIONSHIP_TYPE}" Target="../charts/chart{part.number}.xml"/>'
        for part in parts
    )


def write_chart_parts(archive: zipfile.ZipFile, parts: list[ChartPart], context: TextContext) -> None:
    for part in parts:
        archive.writestr(part.part_name, chart_space_xml(part.layout, context))
        archive.writestr(f"ppt/charts/_rels/chart{part.number}.xml.rels", xml_document(
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{PACKAGE_RELATIONSHIP_TYPE}" Target="../{part.workbook_name.removeprefix("ppt/")}"/>'
            "</Relationships>"
        ))
        archive.writestr(part.workbook_name, chart_workbook_bytes(part.layout["labels"], part.layout["series"]))


def chart_frames_xml(parts: list[ChartPart], first_shape_id: int, context: TextContext) -> str:
    return "".join(graphic_frame_xml(shape_id, part, context.scale) for shape_id, part in enumerate(parts, start=first_shape_id))


def graphic_frame_xml(shape_id: int, part: ChartPart, scale: SlideScale) -> str:
    box = part.layout["box"]
    return (
        f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{shape_id}" name="Chart {shape_id}"/>'
        '<p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr>'
        f'<p:xfrm><a:off x="{scale.x(box["left"])}" y="{scale.y(box["top"])}"/>'
        f'<a:ext cx="{scale.x(box["right"] - box["left"])}" cy="{scale.y(box["bottom"] - box["top"])}"/></p:xfrm>'
        f'<a:graphic><a:graphicData uri="{CHART_URI}"><c:chart xmlns:c="{CHART_URI}" r:id="{part.relationship_id}"/></a:graphicData></a:graphic>'
        "</p:graphicFrame>"
    )


def chart_space_xml(layout: dict, context: TextContext) -> str:
    is_round = is_round_kind(layout["type"])
    plot_layout = manual_layout_xml(0, 0, 1, 1, inner=True) if is_round else ""
    return xml_document(
        f'<c:chartSpace {CHART_NAMESPACES}><c:date1904 val="0"/><c:lang val="{context.language}"/><c:roundedCorners val="0"/>'
        f'<c:chart><c:autoTitleDeleted val="1"/><c:plotArea>{plot_layout}{plot_xml(layout, context)}{axes_xml(layout, context)}{NO_FILL}</c:plotArea>'
        f'{legend_xml(layout, context)}<c:plotVisOnly val="1"/><c:dispBlanksAs val="gap"/></c:chart>'
        f'{NO_FILL}{text_properties_xml(text_style(layout, "category"), context)}'
        '<c:externalData r:id="rId1"><c:autoUpdate val="0"/></c:externalData></c:chartSpace>'
    )


def plot_xml(layout: dict, context: TextContext) -> str:
    kind = layout["type"]
    indexes = list(range(len(layout["series"])))
    primary_axes = (CATEGORY_AXIS_ID, VALUE_AXIS_ID)
    if kind in BAR_DIRECTIONS:
        return bar_plot_xml(layout, kind, indexes, primary_axes, context)
    if kind == "line":
        return line_plot_xml(layout, indexes, primary_axes, context)
    if kind == "combo":
        return bar_plot_xml(layout, "column", indexes[:-1], primary_axes, context) + line_plot_xml(layout, indexes[-1:], (SECONDARY_CATEGORY_AXIS_ID, SECONDARY_VALUE_AXIS_ID), context)
    if kind == "area":
        series = "".join(series_xml(layout, index, "area", context) for index in indexes)
        return f'<c:areaChart><c:grouping val="stacked"/><c:varyColors val="0"/>{series}{axis_ids_xml(primary_axes)}</c:areaChart>'
    if kind == "scatter":
        return f'<c:scatterChart><c:scatterStyle val="lineMarker"/><c:varyColors val="0"/>{scatter_series_xml(layout, context)}{axis_ids_xml(primary_axes)}</c:scatterChart>'
    series = series_xml(layout, 0, kind, context)
    if kind == "donut":
        return f'<c:doughnutChart><c:varyColors val="1"/>{series}<c:firstSliceAng val="0"/><c:holeSize val="{DONUT_HOLE_PERCENT}"/></c:doughnutChart>'
    return f'<c:pieChart><c:varyColors val="1"/>{series}<c:firstSliceAng val="0"/></c:pieChart>'


def axis_ids_xml(axes: tuple[int, int]) -> str:
    return "".join(f'<c:axId val="{axis}"/>' for axis in axes)


def bar_plot_xml(layout: dict, kind: str, indexes: list[int], axes: tuple[int, int], context: TextContext) -> str:
    series = "".join(series_xml(layout, index, kind, context) for index in indexes)
    overlap = f'<c:overlap val="{bar_overlap(layout, kind)}"/>'
    return (
        f'<c:barChart><c:barDir val="{BAR_DIRECTIONS[kind]}"/><c:grouping val="{BAR_GROUPINGS[kind]}"/><c:varyColors val="0"/>{series}'
        f'<c:gapWidth val="{layout["gapWidth"]}"/>{overlap}{axis_ids_xml(axes)}</c:barChart>'
    )


def bar_overlap(layout: dict, kind: str) -> int:
    return 100 if BAR_GROUPINGS[kind] != "clustered" else int(layout.get("overlap", 0))


def line_plot_xml(layout: dict, indexes: list[int], axes: tuple[int, int], context: TextContext) -> str:
    series = "".join(series_xml(layout, index, "line", context) for index in indexes)
    return f'<c:lineChart><c:grouping val="standard"/><c:varyColors val="0"/>{series}<c:marker val="1"/>{axis_ids_xml(axes)}</c:lineChart>'


def series_xml(layout: dict, index: int, kind: str, context: TextContext) -> str:
    color = layout["colors"]["series"][index]
    if is_round_kind(kind):
        body = f"{round_points_xml(layout, context)}{round_labels_xml(layout, context)}"
    elif kind == "line":
        body = f"{line_properties_xml(color, context.scale)}{marker_xml(layout['colors']['background'], color, MARKER_PIXELS, context.scale)}{last_point_xml(layout, color, context.scale)}{point_labels_xml(layout, index, kind, context)}"
    elif kind == "area":
        body = f'<c:spPr>{solid_fill_xml(color)}<a:ln><a:noFill/></a:ln></c:spPr>{point_labels_xml(layout, index, kind, context)}'
    else:
        body = f'<c:spPr>{solid_fill_xml(color)}</c:spPr><c:invertIfNegative val="0"/>{recolored_points_xml(layout, index)}{point_labels_xml(layout, index, kind, context)}'
    smooth = '<c:smooth val="0"/>' if kind == "line" else ""
    return (
        f'<c:ser><c:idx val="{index}"/><c:order val="{index}"/>{series_name_xml(layout, index)}{body}'
        f"{categories_xml(layout)}{values_xml(layout, index, 'c:val')}{smooth}</c:ser>"
    )


def scatter_series_xml(layout: dict, context: TextContext) -> str:
    fill = layout["colors"]["series"][0]
    points = "".join(
        f'<c:dPt><c:idx val="{point}"/>{marker_xml(color, color, SCATTER_MARKER_PIXELS, context.scale)}<c:bubble3D val="0"/></c:dPt>'
        for point, color in enumerate(layout["colors"]["points"][0])
        if color != fill
    )
    return (
        f'<c:ser><c:idx val="0"/><c:order val="0"/>{series_name_xml(layout, 1)}<c:spPr><a:ln><a:noFill/></a:ln></c:spPr>'
        f"{marker_xml(fill, fill, SCATTER_MARKER_PIXELS, context.scale)}{points}{named_point_labels_xml(layout, context)}"
        f'{values_xml(layout, 0, "c:xVal")}{values_xml(layout, 1, "c:yVal")}<c:smooth val="0"/></c:ser>'
    )


def series_name_xml(layout: dict, index: int) -> str:
    name = layout["series"][index]["name"]
    return (
        f'<c:tx><c:strRef><c:f>{DEFAULT_SHEET_NAME}!{cell_reference(index + 1, 0, absolute=True)}</c:f>'
        f'<c:strCache><c:ptCount val="1"/><c:pt idx="0"><c:v>{text_content(name)}</c:v></c:pt></c:strCache></c:strRef></c:tx>'
    )


def categories_xml(layout: dict) -> str:
    labels = layout["labels"]
    points = "".join(f'<c:pt idx="{index}"><c:v>{text_content(label)}</c:v></c:pt>' for index, label in enumerate(labels))
    return (
        f'<c:cat><c:strRef><c:f>{DEFAULT_SHEET_NAME}!{cell_reference(0, 1, absolute=True)}:{cell_reference(0, len(labels), absolute=True)}</c:f>'
        f'<c:strCache><c:ptCount val="{len(labels)}"/>{points}</c:strCache></c:strRef></c:cat>'
    )


def values_xml(layout: dict, index: int, tag: str) -> str:
    values = layout["series"][index]["values"]
    points = "".join(f'<c:pt idx="{point}"><c:v>{number_text(value)}</c:v></c:pt>' for point, value in enumerate(values))
    return (
        f'<{tag}><c:numRef><c:f>{DEFAULT_SHEET_NAME}!{cell_reference(index + 1, 1, absolute=True)}:{cell_reference(index + 1, len(values), absolute=True)}</c:f>'
        f'<c:numCache><c:formatCode>{attribute(number_format(layout, index))}</c:formatCode><c:ptCount val="{len(values)}"/>{points}</c:numCache></c:numRef></{tag}>'
    )


def number_format(layout: dict, index: int) -> str:
    decimals = layout["decimals"][index]
    fraction = "." + "0" * decimals if decimals else ""
    literal = layout["units"][index].replace('"', "")
    return f'#,##0{fraction}"{literal}"' if literal else f"#,##0{fraction}"


def solid_fill_xml(css_color: str) -> str:
    return f"<a:solidFill>{color_xml(parse_css_color(css_color), 1.0)}</a:solidFill>"


def line_xml(css_color: str, width_pixels: float, scale: SlideScale) -> str:
    return f'<a:ln w="{scale.x(width_pixels)}" cap="rnd">{solid_fill_xml(css_color)}<a:round/></a:ln>'


def line_properties_xml(color: str, scale: SlideScale) -> str:
    return f"<c:spPr>{line_xml(color, LINE_WIDTH_PIXELS, scale)}</c:spPr>"


def marker_xml(fill: str, line: str, pixels: float, scale: SlideScale) -> str:
    size = max(2, min(72, round(scale.hundredths_of_point(pixels) / 100)))
    return f'<c:marker><c:symbol val="circle"/><c:size val="{size}"/><c:spPr>{solid_fill_xml(fill)}{line_xml(line, LINE_WIDTH_PIXELS / 2, scale)}</c:spPr></c:marker>'


def last_point_xml(layout: dict, color: str, scale: SlideScale) -> str:
    last = len(layout["labels"]) - 1
    return f'<c:dPt><c:idx val="{last}"/>{marker_xml(color, color, MARKER_PIXELS, scale)}<c:bubble3D val="0"/></c:dPt>'


def recolored_points_xml(layout: dict, index: int) -> str:
    series_color = layout["colors"]["series"][index]
    return "".join(
        f'<c:dPt><c:idx val="{point}"/><c:invertIfNegative val="0"/><c:bubble3D val="0"/><c:spPr>{solid_fill_xml(color)}</c:spPr></c:dPt>'
        for point, color in enumerate(layout["colors"]["points"][index])
        if color != series_color
    )


def label_flags_xml(show_value: bool, show_percent: bool) -> str:
    return (
        f'<c:showLegendKey val="0"/><c:showVal val="{int(show_value)}"/><c:showCatName val="0"/>'
        f'<c:showSerName val="0"/><c:showPercent val="{int(show_percent)}"/><c:showBubbleSize val="0"/>'
    )


def label_body_xml(format_code: str, style: dict, position: str, show_percent: bool, context: TextContext) -> str:
    position_xml = f'<c:dLblPos val="{position}"/>' if position else ""
    return (
        f'<c:numFmt formatCode="{attribute(format_code)}" sourceLinked="0"/><c:spPr><a:noFill/><a:ln><a:noFill/></a:ln></c:spPr>'
        f"{text_properties_xml(style, context)}{position_xml}{label_flags_xml(not show_percent, show_percent)}"
    )


def series_labels(layout: dict, index: int) -> list[dict]:
    return sorted((label for label in layout["pointLabels"] if label["series"] == index), key=lambda label: label["point"])


def point_labels_xml(layout: dict, index: int, kind: str, context: TextContext) -> str:
    labels = series_labels(layout, index)
    if not labels:
        return ""
    shown = "".join(
        f'<c:dLbl><c:idx val="{label["point"]}"/>{label_body_xml(number_format(layout, index), label["text"], label_position(kind, label), False, context)}</c:dLbl>'
        for label in labels
    )
    return f"<c:dLbls>{shown}{label_flags_xml(False, False)}</c:dLbls>"


def named_point_labels_xml(layout: dict, context: TextContext) -> str:
    labels = series_labels(layout, 0)
    if not labels:
        return ""
    shown = "".join(
        f'<c:dLbl><c:idx val="{label["point"]}"/>{rich_text_xml(layout["labels"][label["point"]], label["text"], context)}'
        f'<c:spPr><a:noFill/><a:ln><a:noFill/></a:ln></c:spPr><c:dLblPos val="{label_position("scatter", label)}"/>{label_flags_xml(True, False)}</c:dLbl>'
        for label in labels
    )
    return f"<c:dLbls>{shown}{label_flags_xml(False, False)}</c:dLbls>"


def rich_text_xml(text: str, style: dict, context: TextContext) -> str:
    run = run_properties_xml(styled_run(style), context, "a:rPr", with_link=False)
    return f"<c:tx><c:rich><a:bodyPr/><a:lstStyle/><a:p><a:r>{run}<a:t>{text_content(text)}</a:t></a:r></a:p></c:rich></c:tx>"


def label_position(kind: str, label: dict) -> str:
    return label.get("position") or LABEL_POSITIONS[kind]


def round_points_xml(layout: dict, context: TextContext) -> str:
    gap = line_xml(layout["colors"]["background"], SLICE_GAP_PIXELS, context.scale)
    return "".join(
        f'<c:dPt><c:idx val="{index}"/><c:bubble3D val="0"/><c:spPr>{solid_fill_xml(color)}{gap}</c:spPr></c:dPt>'
        for index, color in enumerate(layout["colors"]["points"][0])
    )


def round_labels_xml(layout: dict, context: TextContext) -> str:
    position = LABEL_POSITIONS.get(layout["type"], "")
    share_style = text_style(layout, "share")
    labels = "".join(
        f'<c:dLbl><c:idx val="{index}"/>{label_body_xml(PERCENT_FORMAT, share_style | {"color": contrasting_text(color, layout)}, position, True, context)}</c:dLbl>'
        for index, color in enumerate(layout["colors"]["points"][0])
    )
    return f"<c:dLbls>{labels}{label_body_xml(PERCENT_FORMAT, share_style, position, True, context)}<c:showLeaderLines val=\"0\"/></c:dLbls>"


def contrasting_text(fill_color: str, layout: dict) -> str:
    return most_contrasting([text_style(layout, "share")["color"], layout["colors"]["background"]], fill_color)


def axes_xml(layout: dict, context: TextContext) -> str:
    kind = layout["type"]
    if is_round_kind(kind):
        return ""
    if kind == "scatter":
        return scatter_axis_xml(layout, 0, "b", context) + scatter_axis_xml(layout, 1, "l", context)
    primary = category_axis_xml(layout, context) + value_axis_xml(layout, context)
    return primary + secondary_axes_xml(layout) if kind == "combo" else primary


def category_axis_xml(layout: dict, context: TextContext) -> str:
    kind = layout["type"]
    horizontal = kind == "bar"
    orientation = "maxMin" if horizontal else "minMax"
    axis_line = layout["colors"]["grid"] if kind in GRIDDED_CHART_TYPES else text_style(layout, "base")["color"]
    return (
        f'<c:catAx><c:axId val="{CATEGORY_AXIS_ID}"/><c:scaling><c:orientation val="{orientation}"/></c:scaling><c:delete val="0"/>'
        f'<c:axPos val="{"l" if horizontal else "b"}"/><c:numFmt formatCode="General" sourceLinked="1"/>'
        '<c:majorTickMark val="none"/><c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/>'
        f"<c:spPr>{line_xml(axis_line, AXIS_LINE_PIXELS, context.scale)}</c:spPr>{text_properties_xml(text_style(layout, 'category'), context)}"
        f'<c:crossAx val="{VALUE_AXIS_ID}"/><c:crosses val="autoZero"/><c:auto val="1"/><c:lblAlgn val="ctr"/><c:lblOffset val="100"/><c:noMultiLvlLbl val="0"/></c:catAx>'
    )


def value_axis_xml(layout: dict, context: TextContext) -> str:
    horizontal = layout["type"] == "bar"
    gridded = layout["type"] in GRIDDED_CHART_TYPES
    value_range = layout.get("valueRange")
    return (
        f'<c:valAx><c:axId val="{VALUE_AXIS_ID}"/><c:scaling><c:orientation val="minMax"/>{limits_xml(value_range)}</c:scaling><c:delete val="1"/>'
        f'<c:axPos val="{"b" if horizontal else "l"}"/>{gridlines_xml(layout, context.scale) if gridded else ""}<c:numFmt formatCode="{attribute(number_format(layout, 0))}" sourceLinked="0"/>'
        '<c:majorTickMark val="none"/><c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/>'
        f'<c:crossAx val="{CATEGORY_AXIS_ID}"/><c:crosses val="autoZero"/><c:crossBetween val="between"/>{major_unit_xml(value_range) if gridded else ""}</c:valAx>'
    )


def secondary_axes_xml(layout: dict) -> str:
    line_index = len(layout["series"]) - 1
    return (
        f'<c:catAx><c:axId val="{SECONDARY_CATEGORY_AXIS_ID}"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:delete val="1"/>'
        '<c:axPos val="b"/><c:majorTickMark val="none"/><c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/>'
        f'<c:crossAx val="{SECONDARY_VALUE_AXIS_ID}"/><c:crosses val="autoZero"/><c:auto val="1"/><c:lblAlgn val="ctr"/><c:lblOffset val="100"/><c:noMultiLvlLbl val="0"/></c:catAx>'
        f'<c:valAx><c:axId val="{SECONDARY_VALUE_AXIS_ID}"/><c:scaling><c:orientation val="minMax"/>{limits_xml(layout.get("secondaryRange"))}</c:scaling><c:delete val="1"/>'
        f'<c:axPos val="r"/><c:numFmt formatCode="{attribute(number_format(layout, line_index))}" sourceLinked="0"/>'
        '<c:majorTickMark val="none"/><c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/>'
        f'<c:crossAx val="{SECONDARY_CATEGORY_AXIS_ID}"/><c:crosses val="max"/><c:crossBetween val="between"/></c:valAx>'
    )


def scatter_axis_xml(layout: dict, index: int, position: str, context: TextContext) -> str:
    axis_id, cross_axis_id = (CATEGORY_AXIS_ID, VALUE_AXIS_ID) if index == 0 else (VALUE_AXIS_ID, CATEGORY_AXIS_ID)
    value_range = layout["valueRange"] if index == 0 else layout["secondaryRange"]
    return (
        f'<c:valAx><c:axId val="{axis_id}"/><c:scaling><c:orientation val="minMax"/>{limits_xml(value_range)}</c:scaling><c:delete val="0"/>'
        f'<c:axPos val="{position}"/>{gridlines_xml(layout, context.scale)}{axis_title_xml(layout["series"][index]["name"], text_style(layout, "axisTitle"), context)}'
        f'<c:numFmt formatCode="{attribute(number_format(layout, index))}" sourceLinked="0"/>'
        '<c:majorTickMark val="none"/><c:minorTickMark val="none"/><c:tickLblPos val="low"/>'
        f'<c:spPr><a:ln><a:noFill/></a:ln></c:spPr>{text_properties_xml(text_style(layout, "category"), context)}'
        f'<c:crossAx val="{cross_axis_id}"/><c:crosses val="min"/><c:crossBetween val="midCat"/>{major_unit_xml(value_range)}</c:valAx>'
    )


def axis_title_xml(name: str, style: dict, context: TextContext) -> str:
    if not name:
        return ""
    return f'<c:title>{rich_text_xml(name, style, context)}<c:overlay val="0"/></c:title>'


def limits_xml(value_range: dict | None) -> str:
    if not value_range:
        return ""
    return f'<c:max val="{number_text(value_range["maximum"])}"/><c:min val="{number_text(value_range["minimum"])}"/>'


def major_unit_xml(value_range: dict | None) -> str:
    if not value_range:
        return ""
    return f'<c:majorUnit val="{number_text((value_range["maximum"] - value_range["minimum"]) / GRID_INTERVALS)}"/>'


def gridlines_xml(layout: dict, scale: SlideScale) -> str:
    return f'<c:majorGridlines><c:spPr>{line_xml(layout["colors"]["grid"], GRID_LINE_PIXELS, scale)}</c:spPr></c:majorGridlines>'


def legend_xml(layout: dict, context: TextContext) -> str:
    if is_round_kind(layout["type"]) or layout["type"] == "scatter" or len(layout["series"]) < 2:
        return ""
    return f'<c:legend><c:legendPos val="t"/><c:overlay val="0"/>{text_properties_xml(text_style(layout, "legend"), context)}</c:legend>'


def manual_layout_xml(left: float, top: float, width: float, height: float, inner: bool) -> str:
    target = '<c:layoutTarget val="inner"/>' if inner else ""
    return (
        f'<c:layout><c:manualLayout>{target}<c:xMode val="edge"/><c:yMode val="edge"/>'
        f'<c:x val="{left}"/><c:y val="{top}"/><c:w val="{width}"/><c:h val="{height}"/></c:manualLayout></c:layout>'
    )


def text_style(layout: dict, role: str) -> dict:
    return layout["text"].get(role) or layout["text"]["base"]


def styled_run(style: dict, text: str = "") -> dict:
    return {**style, "text": text, "italic": False, "underline": False, "strike": False, "letterSpacingPx": 0, "baseline": "", "opacity": 1, "href": None}


def text_properties_xml(style: dict, context: TextContext) -> str:
    properties = run_properties_xml(styled_run(style), context, "a:defRPr", with_link=False)
    return f'<c:txPr><a:bodyPr/><a:lstStyle/><a:p><a:pPr>{properties}</a:pPr><a:endParaRPr lang="{context.language}"/></a:p></c:txPr>'
