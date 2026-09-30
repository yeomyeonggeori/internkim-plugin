from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import html
import json
import pathlib
import zipfile

from pptx_fonts import run_font
from pptx_notes import noted_slide_numbers, notes_relationship_xml, write_notes_parts
from pptx_package import PRESENTATION_HEIGHT_EMU, PRESENTATION_WIDTH_EMU, DeckFonts, slide_document, write_pptx_static_files, xml_document
from pptx_text import SlideScale, TextContext, language_tag, text_box_xml
from truetype_font import TrueTypeFace


TEXT_LAYERS_DIRECTORY_NAME = "pptx-layers"
LAYOUT_FILE_NAME = "layout.json"
HYPERLINK_RELATIONSHIP_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
FIRST_LINK_RELATIONSHIP_NUMBER = 4


@dataclass(frozen=True)
class TextLayers:
    language: str
    slides: list[dict]
    background_paths: list[pathlib.Path]


@dataclass(frozen=True)
class EditablePptx:
    text_box_count: int
    embedded_typefaces: tuple[str, ...]
    unembedded_families: tuple[str, ...]
    picture_texts: tuple[str, ...]


def text_layers_path(review_path: pathlib.Path) -> pathlib.Path:
    return review_path / TEXT_LAYERS_DIRECTORY_NAME


def read_text_layers(review_path: pathlib.Path, slide_count: int) -> TextLayers | None:
    layers_path = text_layers_path(review_path)
    layout_path = layers_path / LAYOUT_FILE_NAME
    if not layout_path.exists():
        return None
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    background_paths = [layers_path / f"background.{number:03}.png" for number in range(1, slide_count + 1)]
    if len(layout["slides"]) != slide_count or not all(path.exists() for path in background_paths):
        return None
    return TextLayers(layout.get("language", ""), layout["slides"], background_paths)


def write_editable_pptx(layers: TextLayers, notes: list[str], pptx_path: pathlib.Path) -> EditablePptx:
    runs = [run for slide in layers.slides for run in text_runs_of(slide)]
    faces = used_faces(runs)
    deck_fonts = DeckFonts(theme_fonts=theme_typefaces(runs), embedded_faces=tuple(faces))
    context_language = language_tag(layers.language)
    with zipfile.ZipFile(pptx_path, "w", zipfile.ZIP_DEFLATED) as archive:
        write_pptx_static_files(archive, len(layers.slides), noted_slide_numbers(notes), deck_fonts)
        write_notes_parts(archive, notes)
        for number, (slide, background_path) in enumerate(zip(layers.slides, layers.background_paths), start=1):
            write_slide(archive, number, slide, background_path, context_language, bool(notes[number - 1]))
    return EditablePptx(
        text_box_count=sum(len(slide["blocks"]) for slide in layers.slides),
        embedded_typefaces=tuple(face.family for face in faces),
        unembedded_families=unembedded_families(runs),
        picture_texts=tuple(text for slide in layers.slides for text in slide["pictureTexts"]),
    )


def write_slide(archive: zipfile.ZipFile, number: int, slide: dict, background_path: pathlib.Path, language: str, has_notes: bool) -> None:
    links = slide_link_ids(slide)
    context = TextContext(SlideScale(slide["width"], slide["height"]), language, links)
    text_boxes = "".join(text_box_xml(shape_id, block, context) for shape_id, block in enumerate(slide["blocks"], start=3))
    archive.write(background_path, f"ppt/media/background{number}.png")
    archive.writestr(f"ppt/slides/slide{number}.xml", slide_document(background_picture_xml() + text_boxes))
    archive.writestr(f"ppt/slides/_rels/slide{number}.xml.rels", slide_relationships_xml(number, has_notes, links))


def background_picture_xml() -> str:
    return (
        '<p:pic><p:nvPicPr><p:cNvPr id="2" name="Hybrid Background"/><p:cNvPicPr><a:picLocks noGrp="1" noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
        '<p:blipFill><a:blip r:embed="rId2"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
        f'<p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{PRESENTATION_WIDTH_EMU}" cy="{PRESENTATION_HEIGHT_EMU}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>'
    )


def slide_link_ids(slide: dict) -> dict[str, str]:
    hrefs = dict.fromkeys(run["href"] for run in text_runs_of(slide) if run.get("href"))
    return {href: f"rId{number}" for number, href in enumerate(hrefs, start=FIRST_LINK_RELATIONSHIP_NUMBER)}


def slide_relationships_xml(number: int, has_notes: bool, links: dict[str, str]) -> str:
    notes_relationship = notes_relationship_xml(number, "rId3") if has_notes else ""
    link_relationships = "".join(
        f'<Relationship Id="{relationship_id}" Type="{HYPERLINK_RELATIONSHIP_TYPE}" Target="{html.escape(href)}" TargetMode="External"/>'
        for href, relationship_id in links.items()
    )
    return xml_document(
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
        f'<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/background{number}.png"/>'
        f"{notes_relationship}{link_relationships}</Relationships>"
    )


def text_runs_of(slide: dict) -> list[dict]:
    return [run for block in slide["blocks"] for paragraph in block["paragraphs"] for run in paragraph["runs"] if not run.get("isBreak")]


def used_faces(runs: list[dict]) -> list[TrueTypeFace]:
    faces = {}
    for run in runs:
        face = run_font(run["fontFamily"], run["fontWeight"]).embedded_face
        if face is not None:
            faces[face.family] = face
    return sorted(faces.values(), key=lambda face: face.weight)


def unembedded_families(runs: list[dict]) -> tuple[str, ...]:
    return tuple(sorted({run["fontFamily"] for run in runs if run_font(run["fontFamily"], run["fontWeight"]).embedded_face is None}))


def theme_typefaces(runs: list[dict]) -> tuple[str, str]:
    character_counts = Counter()
    for run in runs:
        font = run_font(run["fontFamily"], run["fontWeight"])
        character_counts[(font.latin, font.east_asian)] += len(run["text"])
    return character_counts.most_common(1)[0][0] if character_counts else DeckFonts().theme_fonts
