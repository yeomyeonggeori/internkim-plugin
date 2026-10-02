from __future__ import annotations

from deck.deck_kit import kit_length, kit_number, slide_size


PIXEL_TOLERANCE = 4
OVERLAP_RATIO = 0.12
DISTORTION_TOLERANCE = 0.05
TEXT_PREVIEW_LENGTH = 40
SMALLEST_TEXT_SHARE_OF_WIDTH = kit_length("size-floor") / slide_size()[0]
VERTICAL_DEAD_ZONE_HEIGHT_RATIO = 0.27
EMPTY_REGION_SHARE_MAXIMUM = 0.14
TITLE_LINE_MAXIMUM = kit_number("titleLineMaximum")
LABEL_LINE_MAXIMUM = 2
REPEATED_FIGURE_MINIMUM = 3
MARK_BREADTH_MINIMUM = 0.45
ROUND_SLOT_MINIMUM = 0.85
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
        "labelLineMaximum": LABEL_LINE_MAXIMUM,
        "repeatedFigureMinimum": REPEATED_FIGURE_MINIMUM,
        "backgroundShareOfSlide": BACKGROUND_SHARE_OF_SLIDE,
        "markBreadthMinimum": MARK_BREADTH_MINIMUM,
        "roundSlotMinimum": ROUND_SLOT_MINIMUM,
    }
