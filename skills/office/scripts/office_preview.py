from __future__ import annotations

from dataclasses import dataclass, field
import html
from pathlib import Path

from office_result import WARNING, Issue, IssueKind
from render.renderer import RenderFailed, RendererUnavailable, RenderedPages, draw_preview


CSS_PIXELS_PER_INCH = 96
TWIPS_PER_INCH = 1440
EMU_PER_INCH = 914400
POINTS_PER_INCH = 72
PREVIEW_FILE_NAME = "preview.html"
PAGE_SELECTOR = "section[data-page]"

PREVIEW_APPROXIMATED = IssueKind("PREVIEW_APPROXIMATED", WARNING, "the preview leaves out or simplifies something the file has; the message names what", "check those parts in the file itself, or say they were not seen")
PAGES_NOT_RENDERED = IssueKind("PAGES_NOT_RENDERED", WARNING, "only the preview HTML was written; the renderer could not draw page images from it", "install bun or node 18 and run again, or read preview.html for structure and say the pages were not seen")

BLANK_PAGE = IssueKind("BLANK_PAGE", WARNING, "a page has nothing in its body, usually from a page break next to another break or at the end", "delete the extra page break or empty paragraphs around it, then render again")

PREVIEW_ISSUE_KINDS = (PREVIEW_APPROXIMATED, PAGES_NOT_RENDERED, BLANK_PAGE)


@dataclass(frozen=True)
class PageGeometry:
    width: float
    height: float
    margin_top: float
    margin_right: float
    margin_bottom: float
    margin_left: float
    header_distance: float = 0
    footer_distance: float = 0

    @property
    def content_width(self) -> float:
        return self.width - self.margin_left - self.margin_right


@dataclass
class Preview:
    title: str
    pages: list[str] = field(default_factory=list)
    approximations: dict[str, int] = field(default_factory=dict)
    blank_pages: list[int] = field(default_factory=list)

    def approximate(self, what: str, count: int = 1) -> None:
        self.approximations[what] = self.approximations.get(what, 0) + count


def twips_to_pixels(twips: float) -> float:
    return twips * CSS_PIXELS_PER_INCH / TWIPS_PER_INCH


def emu_to_pixels(emu: float) -> float:
    return emu * CSS_PIXELS_PER_INCH / EMU_PER_INCH


def points_to_pixels(points: float) -> float:
    return points * CSS_PIXELS_PER_INCH / POINTS_PER_INCH


def inches_to_pixels(inches: float) -> float:
    return inches * CSS_PIXELS_PER_INCH


def style_attribute(declarations: dict[str, object]) -> str:
    text = ";".join(f"{name}:{value}" for name, value in declarations.items() if value is not None and value != "")
    return f' style="{html.escape(text, quote=True)}"' if text else ""


def pixels(value: float) -> str:
    rounded = round(value, 2)
    return f"{int(rounded) if rounded == int(rounded) else rounded}px"


def escaped(text: str) -> str:
    return html.escape(text, quote=False)


def page_section(number: int, geometry: PageGeometry, inner_html: str) -> str:
    declarations = {
        "position": "relative",
        "width": pixels(geometry.width),
        "height": pixels(geometry.height),
        "overflow": "hidden",
        "background": "#ffffff",
        "color": "#000000",
    }
    return f'<section data-page="{number}"{style_attribute(declarations)}>{inner_html}</section>'


def positioned(left: float, top: float, width: float, inner_html: str, extra: dict | None = None) -> str:
    declarations = {"position": "absolute", "left": pixels(left), "top": pixels(top), "width": pixels(width), **(extra or {})}
    return f"<div{style_attribute(declarations)}>{inner_html}</div>"


def preview_html(preview: Preview) -> str:
    pages = "\n".join(preview.pages)
    return (
        "<!doctype html>\n"
        f'<html lang="ko"><head><meta charset="utf-8"><title>{escaped(preview.title)}</title></head>\n'
        f'<body style="margin:0;background:#e8eaed">\n{pages}\n</body></html>\n'
    )


def write_preview(preview: Preview, output_directory: Path) -> Path:
    output_directory.mkdir(parents=True, exist_ok=True)
    path = output_directory / PREVIEW_FILE_NAME
    path.write_text(preview_html(preview), encoding="utf-8")
    return path


def approximation_issues(preview: Preview, location: str) -> list:
    if not preview.approximations:
        return []
    listed = ", ".join(f"{count} {what}" for what, count in sorted(preview.approximations.items()))
    return [PREVIEW_APPROXIMATED.issue(f"the preview simplifies {listed}", location)]


def blank_page_issues(preview: Preview) -> list:
    return [BLANK_PAGE.issue(f"page {number} of {len(preview.pages)} has nothing in its body", f"page {number}") for number in preview.blank_pages]


def drawn_page_details(rendered: RenderedPages) -> dict:
    return {
        "pages": [str(path) for path in rendered.png_paths],
        "contactSheets": [str(path) for path in rendered.contact_sheet_paths],
        "pdf": str(rendered.pdf_path) if rendered.pdf_path else None,
        "seen": True,
    }


def draw_pages(preview_path: Path, preview_fonts: list[dict], pdf_path: Path, page_selector: str = PAGE_SELECTOR) -> tuple[dict, list[Issue]]:
    try:
        rendered = draw_preview(preview_path, page_selector, preview_fonts, pdf_path)
    except (RendererUnavailable, RenderFailed) as reason:
        return {"seen": False}, [PAGES_NOT_RENDERED.issue(f"wrote {preview_path.name}, and no page was drawn: {reason}", str(preview_path))]
    return drawn_page_details(rendered), []
