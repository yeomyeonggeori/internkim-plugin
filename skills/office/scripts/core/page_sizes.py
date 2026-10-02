from __future__ import annotations

from dataclasses import dataclass

from core.units import MILLIMETRES_PER_INCH, TWIPS_PER_INCH, millimetres_to_pixels


@dataclass(frozen=True)
class Paper:
    name: str
    width_millimetres: float
    height_millimetres: float
    spreadsheet_code: int

    @property
    def millimetres(self) -> tuple[float, float]:
        return self.width_millimetres, self.height_millimetres

    @property
    def inches(self) -> tuple[float, float]:
        return self.width_millimetres / MILLIMETRES_PER_INCH, self.height_millimetres / MILLIMETRES_PER_INCH

    @property
    def twips(self) -> tuple[int, int]:
        width, height = self.inches
        return round(width * TWIPS_PER_INCH), round(height * TWIPS_PER_INCH)

    @property
    def pixels(self) -> tuple[int, int]:
        return round(millimetres_to_pixels(self.width_millimetres)), round(millimetres_to_pixels(self.height_millimetres))

    @property
    def exact_pixels(self) -> dict[str, float]:
        return {"width": millimetres_to_pixels(self.width_millimetres), "height": millimetres_to_pixels(self.height_millimetres)}


# ECMA-376 Part 1, 18.3.1.63 pageSetup paperSize: 1 Letter, 5 Legal, 8 A3, 9 A4, 11 A5, 13 B5 (JIS)
PAPERS = (
    Paper("A3", 297, 420, 8),
    Paper("A4", 210, 297, 9),
    Paper("A5", 148, 210, 11),
    Paper("B5", 182, 257, 13),
    Paper("Letter", 215.9, 279.4, 1),
    Paper("Legal", 215.9, 355.6, 5),
)
PAPER_NAMES = tuple(paper.name for paper in PAPERS)
PAPER_BY_NAME = {paper.name: paper for paper in PAPERS}
PAPER_BY_SPREADSHEET_CODE = {paper.spreadsheet_code: paper for paper in PAPERS}
DEFAULT_PAPER = PAPER_BY_NAME["A4"]
