from __future__ import annotations

import html
import zipfile

from deck.pptx_export.package import theme_xml, xml_document


NOTES_SLIDE_RELATIONSHIP_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide"
NOTES_MASTER_RELATIONSHIP_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesMaster"
NOTES_NAMESPACES = (
    'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
)
EMPTY_GROUP_PROPERTIES = '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>'
SLIDE_IMAGE_PLACEHOLDER = (
    '<p:sp><p:nvSpPr><p:cNvPr id="2" name="Slide Image Placeholder 1"/>'
    '<p:cNvSpPr><a:spLocks noGrp="1" noRot="1" noChangeAspect="1"/></p:cNvSpPr><p:nvPr><p:ph type="sldImg"/></p:nvPr></p:nvSpPr>'
    "{geometry}</p:sp>"
)
NOTES_BODY_PLACEHOLDER = (
    '<p:sp><p:nvSpPr><p:cNvPr id="3" name="Notes Placeholder 2"/>'
    '<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr>'
    "{geometry}{text_body}</p:sp>"
)
SLIDE_IMAGE_GEOMETRY = (
    '<p:spPr><a:xfrm><a:off x="685800" y="1143000"/><a:ext cx="5486400" cy="3086100"/></a:xfrm>'
    '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>'
)
NOTES_BODY_GEOMETRY = (
    '<p:spPr><a:xfrm><a:off x="685800" y="4400550"/><a:ext cx="5486400" cy="3600450"/></a:xfrm>'
    '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>'
)


def noted_slide_numbers(notes: list[str]) -> tuple[int, ...]:
    return tuple(number for number, text in enumerate(notes, start=1) if text)


def write_notes_parts(archive: zipfile.ZipFile, notes: list[str]) -> None:
    noted = noted_slide_numbers(notes)
    if not noted:
        return
    archive.writestr("ppt/notesMasters/notesMaster1.xml", notes_master_xml())
    archive.writestr("ppt/notesMasters/_rels/notesMaster1.xml.rels", notes_master_relationships_xml())
    archive.writestr("ppt/theme/theme2.xml", theme_xml())
    for number in noted:
        archive.writestr(f"ppt/notesSlides/notesSlide{number}.xml", notes_slide_xml(notes[number - 1]))
        archive.writestr(f"ppt/notesSlides/_rels/notesSlide{number}.xml.rels", notes_slide_relationships_xml(number))


def notes_relationship_xml(slide_number: int, relationship_id: str) -> str:
    return f'<Relationship Id="{relationship_id}" Type="{NOTES_SLIDE_RELATIONSHIP_TYPE}" Target="../notesSlides/notesSlide{slide_number}.xml"/>'


def notes_slide_xml(text: str) -> str:
    paragraphs = "".join(f'<a:p><a:r><a:rPr lang="ko-KR"/><a:t>{html.escape(line, quote=False)}</a:t></a:r></a:p>' for line in text.splitlines())
    text_body = f"<p:txBody><a:bodyPr/><a:lstStyle/>{paragraphs}</p:txBody>"
    return xml_document(
        f"<p:notes {NOTES_NAMESPACES}><p:cSld><p:spTree>{EMPTY_GROUP_PROPERTIES}"
        + SLIDE_IMAGE_PLACEHOLDER.format(geometry="<p:spPr/>")
        + NOTES_BODY_PLACEHOLDER.format(geometry="<p:spPr/>", text_body=text_body)
        + "</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:notes>"
    )


def notes_slide_relationships_xml(slide_number: int) -> str:
    return xml_document(
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="{NOTES_MASTER_RELATIONSHIP_TYPE}" Target="../notesMasters/notesMaster1.xml"/>'
        f'<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="../slides/slide{slide_number}.xml"/>'
        "</Relationships>"
    )


def notes_master_xml() -> str:
    empty_body = '<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:endParaRPr lang="ko-KR"/></a:p></p:txBody>'
    return xml_document(
        f"<p:notesMaster {NOTES_NAMESPACES}><p:cSld><p:spTree>{EMPTY_GROUP_PROPERTIES}"
        + SLIDE_IMAGE_PLACEHOLDER.format(geometry=SLIDE_IMAGE_GEOMETRY)
        + NOTES_BODY_PLACEHOLDER.format(geometry=NOTES_BODY_GEOMETRY, text_body=empty_body)
        + '</p:spTree></p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
        "</p:notesMaster>"
    )


def notes_master_relationships_xml() -> str:
    return xml_document(
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme2.xml"/>'
        "</Relationships>"
    )
