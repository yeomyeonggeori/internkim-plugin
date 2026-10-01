from __future__ import annotations


CSS_PIXELS_PER_INCH = 96
POINTS_PER_INCH = 72
TWIPS_PER_INCH = 1440
EMU_PER_INCH = 914400
MILLIMETRES_PER_INCH = 25.4
EMU_PER_POINT = EMU_PER_INCH // POINTS_PER_INCH
EMU_PER_PIXEL = EMU_PER_INCH // CSS_PIXELS_PER_INCH
EMU_PER_CENTIMETRE = round(EMU_PER_INCH * 10 / MILLIMETRES_PER_INCH)
EMU_PER_MILLIMETRE = EMU_PER_CENTIMETRE // 10
PIXELS_PER_POINT = CSS_PIXELS_PER_INCH / POINTS_PER_INCH
PIXELS_PER_EMU = CSS_PIXELS_PER_INCH / EMU_PER_INCH
PIXELS_PER_CENTIMETRE = CSS_PIXELS_PER_INCH * 10 / MILLIMETRES_PER_INCH
SIDE_TEXT_INSET_EMU = EMU_PER_INCH // 10
END_TEXT_INSET_EMU = EMU_PER_INCH // 20
DEFAULT_TEXT_INSETS = {"lIns": SIDE_TEXT_INSET_EMU, "rIns": SIDE_TEXT_INSET_EMU, "tIns": END_TEXT_INSET_EMU, "bIns": END_TEXT_INSET_EMU}


def twips_to_pixels(twips: float) -> float:
    return twips * CSS_PIXELS_PER_INCH / TWIPS_PER_INCH


def emu_to_pixels(emu: float) -> float:
    return emu * PIXELS_PER_EMU


def points_to_pixels(points: float) -> float:
    return points * PIXELS_PER_POINT


def inches_to_pixels(inches: float) -> float:
    return inches * CSS_PIXELS_PER_INCH


def millimetres_to_pixels(millimetres: float) -> float:
    return millimetres * CSS_PIXELS_PER_INCH / MILLIMETRES_PER_INCH
