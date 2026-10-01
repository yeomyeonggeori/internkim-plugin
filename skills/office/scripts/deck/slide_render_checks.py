from __future__ import annotations

import pathlib
import typing

from deck_definitions import EDGE_CLIPPING, FRAME_FIT_RISK, SAFE_MARGIN_INTRUSION, SLIDE_BLANK, SLIDE_TOO_CROWDED, SLIDE_TOO_SPARSE, VERTICAL_DEAD_ZONE
from design_warnings import LABEL_ONLY_SLIDE_ROLES, slide_design_warnings
from geometry_checks import content_extent, geometry_warnings, slide_geometry
from office_result import Issue


CONTENT_DENSITY_MINIMUM = 0.006
CONTENT_DENSITY_MAXIMUM = 0.42
VERTICAL_DEAD_ZONE_HEIGHT_RATIO = 0.27
UNFILLED_BOTTOM_HEIGHT_RATIO = 0.2
CENTERED_BODY_GAP_RATIO = 1.6
CENTERED_KIT_LAYOUTS = {"statement", "quote", "closing"}
UNMEASURED_PAGE = {"width": 0, "height": 0, "bounds": None, "density": 0.0, "verticalGapRatio": 0.0}


def review_slides(image_paths: list[pathlib.Path], page_pixels: list[dict[str, object]], design: dict[str, str], slide_texts: list[dict[str, object]], geometry: list[dict[str, object]] | None) -> list[dict[str, object]]:
    return [
        review_slide(
            image_paths[index] if index < len(image_paths) else None,
            page_pixels[index] if index < len(page_pixels) else None,
            design,
            index + 1,
            slide_text,
            slide_geometry(geometry, index + 1),
        )
        for index, slide_text in enumerate(slide_texts)
    ]


def review_slide(path: typing.Optional[pathlib.Path], pixels: dict[str, object] | None, design: dict[str, str], index: int, slide_text: dict[str, object], measured: dict[str, object] | None) -> dict[str, object]:
    structure = slide_text["structure"]
    if path is None:
        return review_slide_without_image(index, slide_text, structure)
    page = pixels or UNMEASURED_PAGE
    margin = margin_pixels(page, design) if pixels else 0
    checks = slide_checks(page["bounds"], page, margin, page["density"]) if pixels else {}
    risks = slide_risks(page["bounds"], page, margin) if pixels else {"frameFitRisk": False}
    warnings = slide_warnings(checks, margin, page["density"], risks, structure, measured) + vertical_dead_zone_warnings(page, measured, structure)
    return {
        "index": index,
        "filename": path.name,
        "hasRenderEvidence": True,
        "width": page["width"],
        "height": page["height"],
        "contentBounds": page["bounds"] or {},
        "contentDensity": page["density"],
        **slide_text_fields(slide_text),
        "marginPixel": margin,
        "passed": bool(checks) and all(checks.values()),
        "checks": checks,
        "risks": risks,
        "geometry": measured,
        "warnings": warnings,
        "needsDesignRevision": False,
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
        "marginPixel": 0,
        "passed": False,
        "checks": {},
        "risks": {"frameFitRisk": False},
        "geometry": None,
        "warnings": slide_design_warnings(structure),
        "needsDesignRevision": False,
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
    if str(structure["slideRole"]) in LABEL_ONLY_SLIDE_ROLES or structure["kitLayout"] in CENTERED_KIT_LAYOUTS:
        return []
    extent = content_extent(measured)
    if extent is not None and extent.unfilled_ratio >= UNFILLED_BOTTOM_HEIGHT_RATIO and not body_is_centered(extent):
        below = "above the footer" if extent.has_footer else "below it"
        return [VERTICAL_DEAD_ZONE.issue(f"the content ends at {extent.body_bottom_ratio:.0%} of the slide height and leaves {extent.unfilled_ratio:.0%} of it empty {below}; let the body fill the frame")]
    if analysis["verticalGapRatio"] >= VERTICAL_DEAD_ZONE_HEIGHT_RATIO:
        return [VERTICAL_DEAD_ZONE.issue(f"an empty band spans {analysis['verticalGapRatio']:.0%} of the slide height; distribute content to fill the frame")]
    return []


def body_is_centered(extent) -> bool:
    return extent.unfilled_ratio <= extent.gap_under_title_ratio * CENTERED_BODY_GAP_RATIO


def slide_checks(bounds: typing.Optional[dict[str, int]], page: dict[str, object], margin: int, density: float) -> dict[str, bool]:
    return {
        "nonblank": bounds is not None,
        "safeMargin": safe_margin_passed(bounds, page, margin),
        "edgeOverflow": edge_overflow_passed(bounds, page),
        "notTooEmpty": density >= CONTENT_DENSITY_MINIMUM,
        "notTooDense": density <= CONTENT_DENSITY_MAXIMUM,
    }


def slide_risks(bounds: typing.Optional[dict[str, int]], page: dict[str, object], margin: int) -> dict[str, bool]:
    return {
        "frameFitRisk": frame_fit_risk(bounds, page, margin),
    }


def margin_pixels(page: dict[str, object], design: dict[str, str]) -> int:
    margin = parse_pixel_value(design.get("layout.margin", "68px"), 68)
    scale = page["width"] / 1280
    return max(16, round(margin * scale * 0.35))


def parse_pixel_value(value: str, default_value: int) -> int:
    cleaned = value.strip().lower().removesuffix("px")
    try:
        return int(float(cleaned))
    except ValueError:
        return default_value


def safe_margin_passed(bounds: typing.Optional[dict[str, int]], page: dict[str, object], margin: int) -> bool:
    if bounds is None:
        return False
    return all([
        bounds["left"] >= margin,
        bounds["top"] >= margin,
        page["width"] - bounds["right"] >= margin,
        page["height"] - bounds["bottom"] >= margin,
    ])


def edge_overflow_passed(bounds: typing.Optional[dict[str, int]], page: dict[str, object]) -> bool:
    if bounds is None:
        return False
    edge = max(8, round(min(page["width"], page["height"]) * 0.015))
    return bounds["left"] > edge and bounds["top"] > edge and page["width"] - bounds["right"] > edge and page["height"] - bounds["bottom"] > edge


def frame_fit_risk(bounds: typing.Optional[dict[str, int]], page: dict[str, object], margin: int) -> bool:
    if bounds is None:
        return False
    clearance = max(round(margin * 1.75), 36)
    right_clearance = page["width"] - bounds["right"]
    bottom_clearance = page["height"] - bounds["bottom"]
    return right_clearance < clearance or bottom_clearance < clearance


def slide_warnings(checks: dict[str, bool], margin: int, density: float, risks: dict[str, bool], structure: dict[str, object], measured: dict[str, object] | None) -> list[Issue]:
    warnings = []
    if checks and not checks["nonblank"]:
        warnings.append(SLIDE_BLANK.issue("slide render appears blank"))
    if checks and not structure["kitLayout"]:
        warnings.extend(pixel_heuristic_warnings(checks, margin, density, risks))
    warnings.extend(geometry_warnings(measured))
    warnings.extend(slide_design_warnings(structure))
    return warnings


def pixel_heuristic_warnings(checks: dict[str, bool], margin: int, density: float, risks: dict[str, bool]) -> list[Issue]:
    warnings = []
    if not checks["safeMargin"]:
        warnings.append(SAFE_MARGIN_INTRUSION.issue(f"content extends inside the recommended safe margin of {margin}px"))
    if not checks["edgeOverflow"]:
        warnings.append(EDGE_CLIPPING.issue("content touches the slide edge and may be clipped"))
    if not checks["notTooEmpty"]:
        warnings.append(SLIDE_TOO_SPARSE.issue(f"slide appears too sparse for a finished deck (content density {density:.1%})"))
    if not checks["notTooDense"]:
        warnings.append(SLIDE_TOO_CROWDED.issue(f"slide appears visually crowded (content density {density:.1%})"))
    if risks["frameFitRisk"]:
        warnings.append(FRAME_FIT_RISK.issue("rendered content is close to the right or bottom frame edge"))
    return warnings
