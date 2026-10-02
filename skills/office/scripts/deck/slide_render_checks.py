from __future__ import annotations

import pathlib
import typing

from deck.deck_definitions import HORIZONTAL_DEAD_ZONE, SLIDE_BLANK, VERTICAL_DEAD_ZONE
from deck.design_warnings import LABEL_ONLY_SLIDE_ROLES, slide_design_warnings
from deck.geometry_checks import content_extent, geometry_warnings, slide_geometry
from deck.kit_fixes import dead_zone_fix, hollow_fix
from deck.layout_thresholds import FULL_WIDTH_RATIO, HORIZONTAL_DEAD_ZONE_BODY_HEIGHT_RATIO, HORIZONTAL_DEAD_ZONE_WIDTH_RATIO, VERTICAL_DEAD_ZONE_HEIGHT_RATIO
from core.office_result import Issue


UNFILLED_BOTTOM_HEIGHT_RATIO = 0.2
HOLLOW_BOXES_NAMED = 3
CENTERED_BODY_GAP_RATIO = 1.6
CENTERED_KIT_LAYOUTS = {"statement", "quote", "closing"}
UNMEASURED_PAGE = {"width": 0, "height": 0, "bounds": None, "density": 0.0, "verticalGapRatio": 0.0}


def review_slides(image_paths: list[pathlib.Path], page_pixels: list[dict[str, object]], slide_texts: list[dict[str, object]], geometry: list[dict[str, object]] | None) -> list[dict[str, object]]:
    return [
        review_slide(
            image_paths[index] if index < len(image_paths) else None,
            page_pixels[index] if index < len(page_pixels) else None,
            index + 1,
            slide_text,
            slide_geometry(geometry, index + 1),
        )
        for index, slide_text in enumerate(slide_texts)
    ]


def review_slide(path: typing.Optional[pathlib.Path], pixels: dict[str, object] | None, index: int, slide_text: dict[str, object], measured: dict[str, object] | None) -> dict[str, object]:
    structure = slide_text["structure"]
    if path is None:
        return review_slide_without_image(index, slide_text, structure)
    page = pixels or UNMEASURED_PAGE
    is_blank = pixels is not None and page["bounds"] is None
    warnings = slide_warnings(is_blank, structure, measured) + hollow_box_warnings(measured, structure) + vertical_dead_zone_warnings(page, measured, structure) + horizontal_dead_zone_warnings(measured, structure)
    return {
        "index": index,
        "filename": path.name,
        "hasRenderEvidence": True,
        "width": page["width"],
        "height": page["height"],
        "contentBounds": page["bounds"] or {},
        "contentDensity": page["density"],
        **slide_text_fields(slide_text),
        "passed": pixels is not None and not warnings,
        "geometry": measured,
        "warnings": warnings,
        "structure": structure,
    }


def review_slide_without_image(index: int, slide_text: dict[str, object], structure: dict[str, object]) -> dict[str, object]:
    return {
        "index": index,
        "filename": "",
        "hasRenderEvidence": False,
        "width": 0,
        "height": 0,
        "contentBounds": {},
        "contentDensity": 0.0,
        **slide_text_fields(slide_text),
        "passed": False,
        "geometry": None,
        "warnings": slide_design_warnings(structure),
        "structure": structure,
    }


def slide_text_fields(slide_text: dict[str, object]) -> dict[str, object]:
    return {
        "expectedVisibleText": slide_text["expectedVisibleText"],
        "textCharacterCount": slide_text["textCharacterCount"],
        "textLineCount": slide_text["textLineCount"],
        "textPreview": slide_text["textPreview"],
    }


def vertical_dead_zone_warnings(analysis: dict[str, object], measured: dict[str, object] | None, structure: dict[str, object]) -> list[Issue]:
    if is_composed_for_space(structure):
        return []
    extent = content_extent(measured)
    suggestion = dead_zone_fix(str(structure["kitLayout"])) if structure["kitLayout"] else None
    if extent is not None and extent.unfilled_ratio >= UNFILLED_BOTTOM_HEIGHT_RATIO and not body_is_centered(extent):
        below = "above the footer" if extent.has_footer else "below it"
        return [VERTICAL_DEAD_ZONE.issue(f"the content ends at {extent.body_bottom_ratio:.0%} of the slide height and leaves {extent.unfilled_ratio:.0%} of it empty {below}", suggestion=suggestion)]
    if analysis["verticalGapRatio"] >= VERTICAL_DEAD_ZONE_HEIGHT_RATIO:
        return [VERTICAL_DEAD_ZONE.issue(f"an empty band spans {analysis['verticalGapRatio']:.0%} of the slide height", suggestion=suggestion)]
    return []


def horizontal_dead_zone_warnings(measured: dict[str, object] | None, structure: dict[str, object]) -> list[Issue]:
    if is_composed_for_space(structure):
        return []
    region = (measured or {}).get("emptyRegion")
    if not region or not is_beside_content(region, float(measured["width"])):
        return []
    frame = region["frame"]
    width_share = (region["right"] - region["left"]) / float(measured["width"])
    height_share = (region["bottom"] - region["top"]) / (frame["bottom"] - frame["top"])
    suggestion = dead_zone_fix(str(structure["kitLayout"])) if structure["kitLayout"] else None
    return [HORIZONTAL_DEAD_ZONE.issue(f"x {region['left']:g}-{region['right']:g}, y {region['top']:g}-{region['bottom']:g} is empty beside the content: {width_share:.0%} of the slide width and {height_share:.0%} of the body height", suggestion=suggestion)]


def is_beside_content(region: dict[str, object], slide_width: float) -> bool:
    frame = region["frame"]
    width = region["right"] - region["left"]
    return (
        width >= slide_width * HORIZONTAL_DEAD_ZONE_WIDTH_RATIO
        and width < (frame["right"] - frame["left"]) * FULL_WIDTH_RATIO
        and region["bottom"] - region["top"] >= (frame["bottom"] - frame["top"]) * HORIZONTAL_DEAD_ZONE_BODY_HEIGHT_RATIO
    )


def is_composed_for_space(structure: dict[str, object]) -> bool:
    return str(structure["slideRole"]) in LABEL_ONLY_SLIDE_ROLES or structure["kitLayout"] in CENTERED_KIT_LAYOUTS


def hollow_box_warnings(measured: dict[str, object] | None, structure: dict[str, object]) -> list[Issue]:
    boxes = (measured or {}).get("hollowBoxes") or []
    if not boxes:
        return []
    named = "; ".join(f"{box['selector']} \"{box['text']}\" is {box['height']:g}px tall and {box['emptyHeight']:g}px of it holds nothing" for box in boxes[:HOLLOW_BOXES_NAMED])
    return [VERTICAL_DEAD_ZONE.issue(f"{len(boxes)} boxes are mostly empty inside: {named}", suggestion=hollow_fix() if structure["kitLayout"] else None)]


def body_is_centered(extent) -> bool:
    return extent.unfilled_ratio <= extent.gap_under_title_ratio * CENTERED_BODY_GAP_RATIO


def slide_warnings(is_blank: bool, structure: dict[str, object], measured: dict[str, object] | None) -> list[Issue]:
    warnings = [SLIDE_BLANK.issue("slide render appears blank")] if is_blank else []
    return warnings + geometry_warnings(measured, str(structure["kitLayout"] or "")) + slide_design_warnings(structure)
