from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import html
import json
import pathlib
import zipfile

from deck.pptx_export.charts import ChartPart, chart_count, chart_frames_xml, chart_relationships_xml, chart_text_styles, slide_chart_parts, write_chart_parts
from deck.pptx_export.tables import cell_blocks, table_count, table_frames_xml
from fonts.pptx_embedding import run_font
from deck.pptx_export.notes import noted_slide_numbers, notes_relationship_xml, write_notes_parts
from deck.pptx_export.package import PRESENTATION_HEIGHT_EMU, PRESENTATION_WIDTH_EMU, DeckFonts, default_theme_fonts, slide_document, write_pptx_static_files, xml_document
from deck.pptx_export.shapes import connectors_xml as slide_connectors_xml, shape_xml
from deck.pptx_export.text import SlideScale, TextContext, language_tag, text_box_xml
from fonts.truetype import TrueTypeFace


TEXT_LAYERS_DIRECTORY_NAME = "pptx-layers"
LAYOUT_FILE_NAME = "layout.json"
HYPERLINK_RELATIONSHIP_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
IMAGE_RELATIONSHIP_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
SVG_BLIP_EXTENSION_URI = "{96DAC541-7B7A-43D3-8B79-37D633B846F1}"
SVG_BLIP_NAMESPACE = "http://schemas.microsoft.com/office/drawing/2016/SVG/main"
FIRST_LINK_RELATIONSHIP_NUMBER = 4
FIRST_SHAPE_ID = 3


@dataclass(frozen=True)
class TextLayers:
    language: str
    slides: list[dict]
    background_paths: list[pathlib.Path]
    directory: pathlib.Path


@dataclass(frozen=True)
class EditablePptx:
    text_box_count: int
    shape_count: int
    connector_count: int
    chart_count: int
    table_count: int
    icon_count: int
    boxes_kept_as_picture: int
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
    return TextLayers(layout.get("language", ""), layout["slides"], background_paths, layers_path)


def write_editable_pptx(layers: TextLayers, notes: list[str], pptx_path: pathlib.Path) -> EditablePptx:
    runs = [run for slide in layers.slides for run in text_runs_of(slide)]
    styled_text = runs + chart_text_styles(layers.slides)
    faces = used_faces(styled_text)
    deck_fonts = DeckFonts(theme_fonts=theme_typefaces(runs), embedded_faces=tuple(faces))
    context_language = language_tag(layers.language)
    with zipfile.ZipFile(pptx_path, "w", zipfile.ZIP_DEFLATED) as archive:
        write_pptx_static_files(archive, len(layers.slides), noted_slide_numbers(notes), deck_fonts, chart_count(layers.slides), icon_count(layers.slides) > 0)
        write_notes_parts(archive, notes)
        first_chart_number = 1
        for number, (slide, background_path) in enumerate(zip(layers.slides, layers.background_paths), start=1):
            first_chart_number += write_slide(archive, number, slide, background_path, context_language, bool(notes[number - 1]), first_chart_number, layers.directory)
    return EditablePptx(
        text_box_count=sum(len(free_blocks(slide)) for slide in layers.slides),
        shape_count=sum(len(slide["shapes"]) for slide in layers.slides),
        connector_count=sum(len(slide.get("connectors", [])) for slide in layers.slides),
        chart_count=chart_count(layers.slides),
        table_count=table_count(layers.slides),
        icon_count=icon_count(layers.slides),
        boxes_kept_as_picture=sum(slide["boxesKeptAsPicture"] for slide in layers.slides),
        embedded_typefaces=tuple(face.family for face in faces),
        unembedded_families=unembedded_families(styled_text),
        picture_texts=tuple(text for slide in layers.slides for text in slide["pictureTexts"]),
    )


def write_slide(archive: zipfile.ZipFile, number: int, slide: dict, background_path: pathlib.Path, language: str, has_notes: bool, first_chart_number: int, layers_directory: pathlib.Path) -> int:
    links = slide_link_ids(slide)
    scale = SlideScale(slide["width"], slide["height"])
    context = TextContext(scale, language, links)
    shapes = slide["shapes"]
    connectors = slide.get("connectors", [])
    blocks = free_blocks(slide)
    tables = slide.get("tables", [])
    first_connector_id = FIRST_SHAPE_ID + len(shapes)
    first_text_box_id = first_connector_id + len(connectors)
    first_table_id = first_text_box_id + len(blocks)
    first_chart_id = first_table_id + len(tables)
    charts = slide_chart_parts(slide.get("charts", []), first_chart_number, FIRST_LINK_RELATIONSHIP_NUMBER + len(links))
    icons = slide_icon_parts(slide.get("icons", []), number, FIRST_LINK_RELATIONSHIP_NUMBER + len(links) + len(charts))
    boxes = "".join(shape_xml(shape_id, shape, scale) for shape_id, shape in enumerate(shapes, start=FIRST_SHAPE_ID))
    boxes += slide_connectors_xml(connectors, shapes, FIRST_SHAPE_ID, scale)
    text_boxes = "".join(text_box_xml(shape_id, block, context) for shape_id, block in enumerate(blocks, start=first_text_box_id))
    table_frames = table_frames_xml(tables, cell_blocks(slide["blocks"]), first_table_id, context)
    archive.write(background_path, f"ppt/media/background{number}.png")
    pictures = icon_pictures_xml(icons, first_chart_id + len(charts), scale)
    archive.writestr(f"ppt/slides/slide{number}.xml", slide_document(background_picture_xml() + boxes + text_boxes + table_frames + chart_frames_xml(charts, first_chart_id, context) + pictures))
    archive.writestr(f"ppt/slides/_rels/slide{number}.xml.rels", slide_relationships_xml(number, has_notes, links, charts, icons))
    write_chart_parts(archive, charts, context)
    write_icon_media(archive, icons, layers_directory)
    return len(charts)


@dataclass(frozen=True)
class IconPart:
    name: str
    box: dict
    sources: dict[str, str]
    media: dict[str, str]
    relationship_ids: dict[str, str]


def icon_count(slides: list[dict]) -> int:
    return sum(len(slide.get("icons", [])) for slide in slides)


def slide_icon_parts(icons: list[dict], slide_number: int, first_relationship_number: int) -> list[IconPart]:
    return [
        IconPart(
            name=icon["name"],
            box=icon["box"],
            sources={kind: icon[kind] for kind in ("png", "svg")},
            media={kind: f"icon{slide_number}_{index}.{kind}" for kind in ("png", "svg")},
            relationship_ids={kind: f"rId{first_relationship_number + 2 * (index - 1) + offset}" for offset, kind in enumerate(("png", "svg"))},
        )
        for index, icon in enumerate(icons, start=1)
    ]


def icon_pictures_xml(icons: list[IconPart], first_shape_id: int, scale: SlideScale) -> str:
    return "".join(icon_picture_xml(shape_id, icon, scale) for shape_id, icon in enumerate(icons, start=first_shape_id))


def icon_picture_xml(shape_id: int, icon: IconPart, scale: SlideScale) -> str:
    box = icon.box
    return (
        f'<p:pic><p:nvPicPr><p:cNvPr id="{shape_id}" name="Icon {html.escape(icon.name)}" descr="{html.escape(icon.name)}"/>'
        '<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
        f'<p:blipFill><a:blip r:embed="{icon.relationship_ids["png"]}"><a:extLst><a:ext uri="{SVG_BLIP_EXTENSION_URI}">'
        f'<asvg:svgBlip xmlns:asvg="{SVG_BLIP_NAMESPACE}" r:embed="{icon.relationship_ids["svg"]}"/></a:ext></a:extLst></a:blip>'
        '<a:stretch><a:fillRect/></a:stretch></p:blipFill>'
        f'<p:spPr><a:xfrm><a:off x="{scale.x(box["left"])}" y="{scale.y(box["top"])}"/>'
        f'<a:ext cx="{scale.x(box["right"] - box["left"])}" cy="{scale.y(box["bottom"] - box["top"])}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>'
    )


def icon_relationships_xml(icons: list[IconPart]) -> str:
    return "".join(
        f'<Relationship Id="{icon.relationship_ids[kind]}" Type="{IMAGE_RELATIONSHIP_TYPE}" Target="../media/{icon.media[kind]}"/>'
        for icon in icons
        for kind in ("png", "svg")
    )


def write_icon_media(archive: zipfile.ZipFile, icons: list[IconPart], layers_directory: pathlib.Path) -> None:
    for icon in icons:
        for kind in ("png", "svg"):
            archive.write(layers_directory / icon.sources[kind], f"ppt/media/{icon.media[kind]}")


def free_blocks(slide: dict) -> list[dict]:
    return [block for block in slide["blocks"] if not block.get("cell")]


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


def slide_relationships_xml(number: int, has_notes: bool, links: dict[str, str], charts: list[ChartPart], icons: list[IconPart]) -> str:
    notes_relationship = notes_relationship_xml(number, "rId3") if has_notes else ""
    link_relationships = "".join(
        f'<Relationship Id="{relationship_id}" Type="{HYPERLINK_RELATIONSHIP_TYPE}" Target="{html.escape(href)}" TargetMode="External"/>'
        for href, relationship_id in links.items()
    )
    return xml_document(
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
        f'<Relationship Id="rId2" Type="{IMAGE_RELATIONSHIP_TYPE}" Target="../media/background{number}.png"/>'
        f"{notes_relationship}{link_relationships}{chart_relationships_xml(charts)}{icon_relationships_xml(icons)}</Relationships>"
    )


def text_runs_of(slide: dict) -> list[dict]:
    return [run for block in slide["blocks"] for paragraph in block["paragraphs"] for run in paragraph["runs"] if not run.get("isBreak")]


def used_faces(runs: list[dict]) -> list[TrueTypeFace]:
    faces = {}
    for run in runs:
        face = run_font(run["fontFamily"], run["fontWeight"]).embedded_face
        if face is not None:
            faces[(face.family, face.subfamily)] = face
    return sorted(faces.values(), key=lambda face: face.weight)


def unembedded_families(runs: list[dict]) -> tuple[str, ...]:
    return tuple(sorted({run["fontFamily"] for run in runs if run_font(run["fontFamily"], run["fontWeight"]).embedded_face is None}))


def theme_typefaces(runs: list[dict]) -> tuple[str, str]:
    character_counts = Counter()
    for run in runs:
        font = run_font(run["fontFamily"], run["fontWeight"])
        character_counts[(font.latin, font.east_asian)] += len(run["text"])
    return character_counts.most_common(1)[0][0] if character_counts else default_theme_fonts()
