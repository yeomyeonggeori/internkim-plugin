from __future__ import annotations

import html
import pathlib
import zipfile

from native_pptx_layouts import draw_native_slide
from native_rendering import SLIDE_HEIGHT, SLIDE_WIDTH, native_colors
from fonts.registry import BOLD_WEIGHT, DECK, REGULAR_WEIGHT, default_family
from fonts.pptx_embedding import RunFont, run_font
from pptx_notes import noted_slide_numbers, notes_relationship_xml, write_notes_parts
from pptx_package import PRESENTATION_HEIGHT_EMU, PRESENTATION_WIDTH_EMU, DeckFonts, slide_document, write_pptx_static_files, xml_document
from slide_model import SlideModel
from units import EMU_PER_PIXEL


class NativeSlideCanvas:
    def __init__(self) -> None:
        self.shape_parts: list[str] = []
        self.next_shape_id = 2

    def add_rectangle(self, x: int, y: int, width: int, height: int, fill: str, line: str = "", radius: bool = False) -> None:
        self.shape_parts.append(rectangle_shape_xml(self.next_shape_id, x, y, width, height, fill, line, radius))
        self.next_shape_id += 1

    def add_text(self, x: int, y: int, width: int, height: int, lines: list[str], font_size: int, color: str, bold: bool = False, align: str = "l") -> None:
        visible_lines = [line for line in lines if line.strip()]
        if not visible_lines:
            return
        self.shape_parts.append(text_box_xml(self.next_shape_id, x, y, width, height, visible_lines, font_size, color, bold, align))
        self.next_shape_id += 1


def write_native_text_pptx(slide_models: list[SlideModel], design: dict[str, str], pptx_path: pathlib.Path) -> None:
    with zipfile.ZipFile(pptx_path, "w", zipfile.ZIP_DEFLATED) as archive:
        notes = [model.notes for model in slide_models]
        write_pptx_static_files(archive, len(slide_models), noted_slide_numbers(notes), native_deck_fonts())
        write_notes_parts(archive, notes)
        for model in slide_models:
            archive.writestr(f"ppt/slides/slide{model.index}.xml", native_slide_xml(model, design))
            archive.writestr(f"ppt/slides/_rels/slide{model.index}.xml.rels", native_slide_relationship_xml(model.index, bool(model.notes)))


def native_slide_xml(model: SlideModel, design: dict[str, str]) -> str:
    canvas = NativeSlideCanvas()
    draw_native_slide(canvas, model, native_colors(design))
    return slide_document("".join(canvas.shape_parts))


def native_slide_relationship_xml(index: int, has_notes: bool) -> str:
    notes_relationship = notes_relationship_xml(index, "rId2") if has_notes else ""
    return xml_document(
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
        f"{notes_relationship}</Relationships>"
    )


def rectangle_shape_xml(shape_id: int, x: int, y: int, width: int, height: int, fill: str, line: str = "", radius: bool = False) -> str:
    line_xml = f'<a:ln w="{EMU_PER_PIXEL}"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln>' if line else '<a:ln><a:noFill/></a:ln>'
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="Shape {shape_id}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr>{transform_xml(x, y, width, height)}'
        f'<a:prstGeom prst="{"roundRect" if radius else "rect"}"><a:avLst/></a:prstGeom>'
        f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>{line_xml}</p:spPr></p:sp>'
    )


def text_box_xml(shape_id: int, x: int, y: int, width: int, height: int, lines: list[str], font_size: int, color: str, bold: bool, align: str) -> str:
    paragraphs = "".join(text_paragraph_xml(line, font_size, color, bold, align) for line in lines)
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="Text {shape_id}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr>{transform_xml(x, y, width, height)}'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>'
        f'<p:txBody><a:bodyPr wrap="square" anchor="t"><a:spAutoFit/></a:bodyPr><a:lstStyle/>{paragraphs}</p:txBody></p:sp>'
    )


def transform_xml(x: int, y: int, width: int, height: int) -> str:
    return f'<a:xfrm><a:off x="{x_emu(x)}" y="{y_emu(y)}"/><a:ext cx="{x_emu(width)}" cy="{y_emu(height)}"/></a:xfrm>'


def native_run_font(bold: bool) -> RunFont:
    return run_font(default_family(DECK).name, BOLD_WEIGHT if bold else REGULAR_WEIGHT)


def native_deck_fonts() -> DeckFonts:
    regular = native_run_font(False)
    faces = tuple(font.embedded_face for font in (regular, native_run_font(True)) if font.embedded_face is not None)
    return DeckFonts((regular.latin, regular.east_asian), faces)


def text_paragraph_xml(value: str, font_size: int, color: str, bold: bool, align: str) -> str:
    font = native_run_font(bold)
    bold_xml = ' b="1"' if font.bold else ""
    alignment = "ctr" if align == "ctr" else "l"
    return (
        f'<a:p><a:pPr algn="{alignment}"/>'
        f'<a:r><a:rPr lang="ko-KR" sz="{font_size * 100}"{bold_xml}>'
        f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        f'<a:latin typeface="{html.escape(font.latin)}"/><a:ea typeface="{html.escape(font.east_asian)}"/></a:rPr>'
        f'<a:t>{xml_escape(value)}</a:t></a:r>'
        f'<a:endParaRPr lang="ko-KR" sz="{font_size * 100}"/></a:p>'
    )


def x_emu(value: int | float) -> int:
    return round(value * PRESENTATION_WIDTH_EMU / SLIDE_WIDTH)


def y_emu(value: int | float) -> int:
    return round(value * PRESENTATION_HEIGHT_EMU / SLIDE_HEIGHT)


def xml_escape(value: str) -> str:
    return html.escape(str(value), quote=True)
