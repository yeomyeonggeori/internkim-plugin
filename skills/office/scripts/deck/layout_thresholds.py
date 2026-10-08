from __future__ import annotations

from core.design_rules import deck_rule_requests, render_rule_requests
from deck.deck_kit import slide_size
from powerpoint.definitions import BACKGROUND_SHARE_OF_SLIDE, DISTORTION_TOLERANCE, OVERLAP_RATIO


TEXT_PREVIEW_LENGTH = 40
IMAGE_UPSCALE_MAXIMUM = 1.5
# WCAG 2.2 success criterion 1.4.3: 4.5:1, or 3:1 for text of 24px, or 18.66px bold, at a 1600px-wide slide
TEXT_CONTRAST_MINIMUM = 4.5
LARGE_TEXT_CONTRAST_MINIMUM = 3.0
LARGE_TEXT_SHARE_OF_WIDTH = 24 / 1600
LARGE_BOLD_TEXT_SHARE_OF_WIDTH = 18.66 / 1600


def renderer_thresholds() -> dict[str, object]:
    return {
        "overlapRatioMinimum": OVERLAP_RATIO,
        "aspectRatioTolerance": DISTORTION_TOLERANCE,
        "textPreviewLength": TEXT_PREVIEW_LENGTH,
        "backgroundShareOfSlide": BACKGROUND_SHARE_OF_SLIDE,
        "imageUpscaleMaximum": IMAGE_UPSCALE_MAXIMUM,
        "textContrastMinimum": TEXT_CONTRAST_MINIMUM,
        "largeTextContrastMinimum": LARGE_TEXT_CONTRAST_MINIMUM,
        "largeTextShareOfWidth": LARGE_TEXT_SHARE_OF_WIDTH,
        "largeBoldTextShareOfWidth": LARGE_BOLD_TEXT_SHARE_OF_WIDTH,
    }


def gate_thresholds() -> dict[str, object]:
    return renderer_thresholds() | {"slideSize": {"width": slide_size()[0], "height": slide_size()[1]}, "designRules": render_rule_requests()} | deck_rule_requests()
