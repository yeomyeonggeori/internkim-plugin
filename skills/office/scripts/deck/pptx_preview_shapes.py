from __future__ import annotations

from pptx.oxml.ns import qn

from pptx_preview_paint import Outline, element, svg_uri


DEFAULT_CORNER = 16667
ADJUST_SCALE = 100000
LINE_GEOMETRIES = {"line", "straightConnector1", "bentConnector2", "bentConnector3", "curvedConnector3"}
POLYGONS = {
    "triangle": ((0.5, 0), (1, 1), (0, 1)),
    "rtTriangle": ((0, 0), (1, 1), (0, 1)),
    "diamond": ((0.5, 0), (1, 0.5), (0.5, 1), (0, 0.5)),
    "parallelogram": ((0.25, 0), (1, 0), (0.75, 1), (0, 1)),
    "trapezoid": ((0.25, 0), (0.75, 0), (1, 1), (0, 1)),
    "pentagon": ((0.5, 0), (1, 0.38), (0.81, 1), (0.19, 1), (0, 0.38)),
    "hexagon": ((0.25, 0), (0.75, 0), (1, 0.5), (0.75, 1), (0.25, 1), (0, 0.5)),
    "homePlate": ((0, 0), (0.8, 0), (1, 0.5), (0.8, 1), (0, 1)),
    "chevron": ((0, 0), (0.8, 0), (1, 0.5), (0.8, 1), (0, 1), (0.2, 0.5)),
    "rightArrow": ((0, 0.25), (0.6, 0.25), (0.6, 0), (1, 0.5), (0.6, 1), (0.6, 0.75), (0, 0.75)),
    "leftArrow": ((1, 0.25), (0.4, 0.25), (0.4, 0), (0, 0.5), (0.4, 1), (0.4, 0.75), (1, 0.75)),
    "upArrow": ((0.25, 1), (0.25, 0.4), (0, 0.4), (0.5, 0), (1, 0.4), (0.75, 0.4), (0.75, 1)),
    "downArrow": ((0.25, 0), (0.25, 0.6), (0, 0.6), (0.5, 1), (1, 0.6), (0.75, 0.6), (0.75, 0)),
}
ROUND_GEOMETRIES = {"roundRect", "flowChartAlternateProcess"}
ELLIPSE_GEOMETRIES = {"ellipse", "flowChartConnector"}


def geometry_name(properties) -> str:
    preset = properties.find(qn("a:prstGeom")) if properties is not None else None
    return preset.get("prst", "rect") if preset is not None else "rect"


def geometry_html(properties, fill: str | None, line: Outline | None, width: float, height: float) -> str:
    name = geometry_name(properties)
    if fill is None and line is None:
        return ""
    if name in LINE_GEOMETRIES:
        return line_html(properties, line, width, height) if line else ""
    if name in POLYGONS:
        return polygon_html(POLYGONS[name], fill, line, width, height)
    box = {
        "position": "absolute",
        "left": "0px",
        "top": "0px",
        "width": "100%",
        "height": "100%",
        "box-sizing": "border-box",
        "background-color": fill,
        "border": f"{line.width}px solid {line.color}" if line else None,
        "border-radius": corner_radius(properties, name, width, height),
    }
    return element("div", box)


def corner_radius(properties, name: str, width: float, height: float) -> str | None:
    if name in ELLIPSE_GEOMETRIES:
        return "50%"
    if name not in ROUND_GEOMETRIES:
        return None
    adjust = properties.find(f"{qn('a:prstGeom')}/{qn('a:avLst')}/{qn('a:gd')}")
    amount = int(adjust.get("fmla", f"val {DEFAULT_CORNER}").split()[-1]) if adjust is not None else DEFAULT_CORNER
    return f"{min(width, height) * amount / ADJUST_SCALE:.2f}px"


def flips(properties) -> tuple[bool, bool]:
    transform = properties.find(qn("a:xfrm")) if properties is not None else None
    if transform is None:
        return False, False
    return transform.get("flipH") in ("1", "true"), transform.get("flipV") in ("1", "true")


def line_html(properties, line: Outline, width: float, height: float) -> str:
    if not width or not height:
        return straight_line_html(line, width, height)
    flip_horizontal, flip_vertical = flips(properties)
    canvas_width, canvas_height = max(width, line.width), max(height, line.width)
    left, top = (canvas_width - width) / 2, (canvas_height - height) / 2
    start = (left + (width if flip_horizontal else 0), top + (height if flip_vertical else 0))
    end = (left + (0 if flip_horizontal else width), top + (0 if flip_vertical else height))
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_width:.2f}" height="{canvas_height:.2f}">'
        f'<line x1="{start[0]:.2f}" y1="{start[1]:.2f}" x2="{end[0]:.2f}" y2="{end[1]:.2f}" stroke="{line.color}" stroke-width="{line.width}"/></svg>'
    )
    return image_layer(svg, canvas_width, canvas_height, -left, -top)


def straight_line_html(line: Outline, width: float, height: float) -> str:
    thickness = line.width
    left, top = (-thickness / 2, 0.0) if not width else (0.0, -thickness / 2)
    return element("div", {
        "position": "absolute",
        "left": f"{left:.2f}px",
        "top": f"{top:.2f}px",
        "width": f"{max(width, thickness):.2f}px",
        "height": f"{max(height, thickness):.2f}px",
        "background": line.color,
    }, "")


def polygon_html(points: tuple, fill: str | None, line: Outline | None, width: float, height: float) -> str:
    inset = line.width / 2 if line else 0
    coordinates = " ".join(f"{inset + x * (width - 2 * inset):.2f},{inset + y * (height - 2 * inset):.2f}" for x, y in points)
    stroke = f' stroke="{line.color}" stroke-width="{line.width}"' if line else ""
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.2f}" height="{height:.2f}"><polygon points="{coordinates}" fill="{fill or "none"}"{stroke}/></svg>'
    return image_layer(svg, width, height)


def image_layer(svg: str, width: float, height: float, left: float = 0.0, top: float = 0.0) -> str:
    return f'<img src="{svg_uri(svg)}" style="position:absolute;left:{left:.2f}px;top:{top:.2f}px;width:{width:.2f}px;height:{height:.2f}px"/>'
