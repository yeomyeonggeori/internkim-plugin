from __future__ import annotations


PIXEL_TOLERANCE = 4
OVERLAP_RATIO = 0.12
DISTORTION_TOLERANCE = 0.05
TEXT_PREVIEW_LENGTH = 40
SMALLEST_TEXT_SHARE_OF_WIDTH = 0.01
TITLE_LINE_MAXIMUM = 3
BACKGROUND_SHARE_OF_SLIDE = 0.7


def renderer_thresholds() -> dict[str, float]:
    return {
        "pixelTolerance": PIXEL_TOLERANCE,
        "overlapRatioMinimum": OVERLAP_RATIO,
        "aspectRatioTolerance": DISTORTION_TOLERANCE,
        "textPreviewLength": TEXT_PREVIEW_LENGTH,
        "smallestTextShareOfWidth": SMALLEST_TEXT_SHARE_OF_WIDTH,
        "titleLineMaximum": TITLE_LINE_MAXIMUM,
        "backgroundShareOfSlide": BACKGROUND_SHARE_OF_SLIDE,
    }
