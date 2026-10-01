from __future__ import annotations

from deck.deck_kit import kit_length, slide_size


PIXEL_TOLERANCE = 4
OVERLAP_RATIO = 0.12
DISTORTION_TOLERANCE = 0.05
TEXT_PREVIEW_LENGTH = 40
SMALLEST_TEXT_SHARE_OF_WIDTH = kit_length("size-floor") / slide_size()[0]
VERTICAL_DEAD_ZONE_HEIGHT_RATIO = 0.27
TITLE_LINE_MAXIMUM = 3
BACKGROUND_SHARE_OF_SLIDE = 0.7


def renderer_thresholds() -> dict[str, float]:
    return {
        "pixelTolerance": PIXEL_TOLERANCE,
        "overlapRatioMinimum": OVERLAP_RATIO,
        "aspectRatioTolerance": DISTORTION_TOLERANCE,
        "textPreviewLength": TEXT_PREVIEW_LENGTH,
        "smallestTextShareOfWidth": SMALLEST_TEXT_SHARE_OF_WIDTH,
        "deadZoneShareOfSlide": VERTICAL_DEAD_ZONE_HEIGHT_RATIO,
        "titleLineMaximum": TITLE_LINE_MAXIMUM,
        "backgroundShareOfSlide": BACKGROUND_SHARE_OF_SLIDE,
    }
