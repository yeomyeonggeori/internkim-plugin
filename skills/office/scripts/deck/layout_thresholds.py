from __future__ import annotations

from deck.deck_kit import kit_length, kit_number, slide_size
from powerpoint.definitions import BACKGROUND_SHARE_OF_SLIDE, DISTORTION_TOLERANCE, OVERLAP_RATIO


PIXEL_TOLERANCE = 4
TEXT_PREVIEW_LENGTH = 40
SMALLEST_TEXT_SHARE_OF_WIDTH = kit_length("size-floor") / slide_size()[0]
VERTICAL_DEAD_ZONE_HEIGHT_RATIO = 0.27
EMPTY_REGION_SHARE_MAXIMUM = 0.14
TITLE_LINE_MAXIMUM = kit_number("titleLineMaximum")
LABEL_LINE_MAXIMUM = 2
REPEATED_FIGURE_MINIMUM = 3
MARK_BREADTH_MINIMUM = 0.45
ROUND_SLOT_MINIMUM = 0.85
IMAGE_UPSCALE_MAXIMUM = 1.5
# WCAG 2.2 success criterion 1.4.3: 4.5:1, or 3:1 for text of 24px, or 18.66px bold, at a 1600px-wide slide
TEXT_CONTRAST_MINIMUM = 4.5
LARGE_TEXT_CONTRAST_MINIMUM = 3.0
LARGE_TEXT_SHARE_OF_WIDTH = 24 / 1600
LARGE_BOLD_TEXT_SHARE_OF_WIDTH = 18.66 / 1600


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
        "imageUpscaleMaximum": IMAGE_UPSCALE_MAXIMUM,
        "textContrastMinimum": TEXT_CONTRAST_MINIMUM,
        "largeTextContrastMinimum": LARGE_TEXT_CONTRAST_MINIMUM,
        "largeTextShareOfWidth": LARGE_TEXT_SHARE_OF_WIDTH,
        "largeBoldTextShareOfWidth": LARGE_BOLD_TEXT_SHARE_OF_WIDTH,
    }
