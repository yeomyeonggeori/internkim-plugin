from __future__ import annotations


THEME_SLOTS = ("lt1", "dk1", "lt2", "dk2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6", "hlink", "folHlink")
OFFICE_THEME = dict(zip(THEME_SLOTS, ("FFFFFF", "000000", "E7E6E6", "44546A", "4472C4", "ED7D31", "A5A5A5", "FFC000", "5B9BD5", "70AD47", "0563C1", "954F72")))
ACCENT_SLOTS = THEME_SLOTS[4:10]
OFFICE_ACCENTS = tuple(OFFICE_THEME[slot] for slot in ACCENT_SLOTS)
HYPERLINK_COLOR = OFFICE_THEME["hlink"]
