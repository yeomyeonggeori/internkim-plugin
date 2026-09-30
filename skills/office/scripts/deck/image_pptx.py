import pathlib
import zipfile

from pptx_package import PRESENTATION_HEIGHT_EMU, PRESENTATION_WIDTH_EMU, slide_document, write_pptx_static_files, xml_document


def write_image_backed_pptx(image_paths: list[pathlib.Path], pptx_path: pathlib.Path) -> None:
    with zipfile.ZipFile(pptx_path, "w", zipfile.ZIP_DEFLATED) as archive:
        write_pptx_static_files(archive, len(image_paths))
        for index, image_path in enumerate(image_paths, start=1):
            archive.write(image_path, f"ppt/media/image{index}.png")
            archive.writestr(f"ppt/slides/slide{index}.xml", image_slide_xml())
            archive.writestr(f"ppt/slides/_rels/slide{index}.xml.rels", image_slide_relationship_xml(index))


def image_slide_xml() -> str:
    return slide_document(
        '<p:pic><p:nvPicPr><p:cNvPr id="2" name="Rendered slide"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>'
        '<p:blipFill><a:blip r:embed="rId1"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
        f'<p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{PRESENTATION_WIDTH_EMU}" cy="{PRESENTATION_HEIGHT_EMU}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>'
    )


def image_slide_relationship_xml(index: int) -> str:
    return xml_document(
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image{index}.png"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
        "</Relationships>"
    )
