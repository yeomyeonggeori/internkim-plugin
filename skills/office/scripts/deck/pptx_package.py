from __future__ import annotations

import zipfile


PRESENTATION_WIDTH_EMU = 12192000
PRESENTATION_HEIGHT_EMU = 6858000
SLIDE_MASTER_RELATIONSHIP_ID = 2147483648


def write_pptx_static_files(archive: zipfile.ZipFile, slide_count: int, noted_slides: tuple[int, ...]) -> None:
    archive.writestr("[Content_Types].xml", content_types_xml(slide_count, noted_slides))
    archive.writestr("_rels/.rels", package_relationships_xml())
    archive.writestr("docProps/core.xml", core_properties_xml())
    archive.writestr("docProps/app.xml", app_properties_xml(slide_count))
    archive.writestr("ppt/presentation.xml", presentation_xml(slide_count, bool(noted_slides)))
    archive.writestr("ppt/_rels/presentation.xml.rels", presentation_relationships_xml(slide_count, bool(noted_slides)))
    archive.writestr("ppt/slideMasters/slideMaster1.xml", slide_master_xml())
    archive.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", slide_master_relationships_xml())
    archive.writestr("ppt/slideLayouts/slideLayout1.xml", slide_layout_xml())
    archive.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", slide_layout_relationships_xml())
    archive.writestr("ppt/theme/theme1.xml", theme_xml())


def content_types_xml(slide_count: int, noted_slides: tuple[int, ...]) -> str:
    overrides = [
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>',
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>',
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>',
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>',
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
    ]
    overrides.extend(
        f'<Override PartName="/ppt/slides/slide{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for index in range(1, slide_count + 1)
    )
    overrides.extend(notes_content_type_overrides(noted_slides))
    return xml_document(
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="png" ContentType="image/png"/>'
        + "".join(overrides)
        + "</Types>"
    )


def notes_content_type_overrides(noted_slides: tuple[int, ...]) -> list[str]:
    if not noted_slides:
        return []
    return [
        '<Override PartName="/ppt/notesMasters/notesMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.notesMaster+xml"/>',
        '<Override PartName="/ppt/theme/theme2.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>',
        *(
            f'<Override PartName="/ppt/notesSlides/notesSlide{number}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"/>'
            for number in noted_slides
        ),
    ]


def package_relationships_xml() -> str:
    return xml_document(
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        "</Relationships>"
    )


def presentation_relationships_xml(slide_count: int, has_notes: bool) -> str:
    relationships = [
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>',
    ]
    relationships.extend(
        f'<Relationship Id="rId{index + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{index}.xml"/>'
        for index in range(1, slide_count + 1)
    )
    if has_notes:
        relationships.append(f'<Relationship Id="rId{slide_count + 2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesMaster" Target="notesMasters/notesMaster1.xml"/>')
    return xml_document(f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{"".join(relationships)}</Relationships>')


def presentation_xml(slide_count: int, has_notes: bool) -> str:
    notes_master_ids = f'<p:notesMasterIdLst><p:notesMasterId r:id="rId{slide_count + 2}"/></p:notesMasterIdLst>' if has_notes else ""
    slide_ids = "".join(f'<p:sldId id="{255 + index}" r:id="rId{index + 1}"/>' for index in range(1, slide_count + 1))
    return xml_document(
        '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<p:sldMasterIdLst><p:sldMasterId id="{SLIDE_MASTER_RELATIONSHIP_ID}" r:id="rId1"/></p:sldMasterIdLst>'
        f"{notes_master_ids}<p:sldIdLst>{slide_ids}</p:sldIdLst>"
        f'<p:sldSz cx="{PRESENTATION_WIDTH_EMU}" cy="{PRESENTATION_HEIGHT_EMU}" type="wide"/>'
        '<p:notesSz cx="6858000" cy="9144000"/>'
        "</p:presentation>"
    )



def slide_master_relationships_xml() -> str:
    return xml_document(
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>'
        "</Relationships>"
    )


def slide_layout_relationships_xml() -> str:
    return xml_document(
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>'
        "</Relationships>"
    )


def slide_master_xml() -> str:
    return xml_document(
        '<p:sldMaster xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill></p:bgPr></p:bg>'
        '<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld>'
        '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
        '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>'
        '<p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles>'
        "</p:sldMaster>"
    )


def slide_layout_xml() -> str:
    return xml_document(
        '<p:sldLayout xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" type="blank" preserve="1">'
        '<p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld>'
        '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>'
        "</p:sldLayout>"
    )


def theme_xml() -> str:
    return xml_document(
        '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="internkim">'
        '<a:themeElements><a:clrScheme name="internkim">'
        '<a:dk1><a:srgbClr val="111827"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>'
        '<a:dk2><a:srgbClr val="374151"/></a:dk2><a:lt2><a:srgbClr val="F8FAFC"/></a:lt2>'
        '<a:accent1><a:srgbClr val="2563EB"/></a:accent1><a:accent2><a:srgbClr val="64748B"/></a:accent2>'
        '<a:accent3><a:srgbClr val="CBD5E1"/></a:accent3><a:accent4><a:srgbClr val="0F172A"/></a:accent4>'
        '<a:accent5><a:srgbClr val="475569"/></a:accent5><a:accent6><a:srgbClr val="E2E8F0"/></a:accent6>'
        '<a:hlink><a:srgbClr val="2563EB"/></a:hlink><a:folHlink><a:srgbClr val="7C3AED"/></a:folHlink>'
        '</a:clrScheme><a:fontScheme name="internkim"><a:majorFont><a:latin typeface="Arial"/><a:ea typeface="Apple SD Gothic Neo"/></a:majorFont><a:minorFont><a:latin typeface="Arial"/><a:ea typeface="Apple SD Gothic Neo"/></a:minorFont></a:fontScheme>'
        '<a:fmtScheme name="internkim"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>'
        '<a:lnStyleLst><a:ln w="63500"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst>'
        '<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme>'
        "</a:themeElements><a:objectDefaults/><a:extraClrSchemeLst/></a:theme>"
    )


def core_properties_xml() -> str:
    return xml_document(
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        "<dc:title>HTML-first slide deck</dc:title>"
        "<dc:creator>internkim</dc:creator>"
        "</cp:coreProperties>"
    )


def app_properties_xml(slide_count: int) -> str:
    return xml_document(
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        "<Application>internkim HTML Slides</Application>"
        f"<Slides>{slide_count}</Slides>"
        "</Properties>"
    )


def xml_document(body: str) -> str:
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + body


def slide_document(shape_tree_xml: str) -> str:
    return xml_document(
        '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<p:cSld><p:spTree>"
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>'
        + shape_tree_xml
        + "</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>"
    )
