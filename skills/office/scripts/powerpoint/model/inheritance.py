from __future__ import annotations

from dataclasses import dataclass
import functools

from lxml import etree
from pptx.opc.constants import RELATIONSHIP_TYPE
from pptx.oxml.ns import qn

from powerpoint.model.shape_kinds import placeholder_of


MASTER_PLACEHOLDER_TYPES = {"ctrTitle": "title", "subTitle": "body", "obj": "body"}
TITLE_TYPES = {"title", "ctrTitle"}
BODY_STYLE_TYPES = {"body", "subTitle", "obj"}
DEFAULT_COLOR_MAP = {"bg1": "lt1", "tx1": "dk1", "bg2": "lt2", "tx2": "dk2"}


@dataclass(frozen=True)
class SlideContext:
    slide: object
    layout_element: object
    master_element: object
    presentation_element: object
    theme_element: object

    def placeholder_chain(self, element) -> list[tuple[str, object]]:
        placeholder = placeholder_of(element)
        if placeholder is None:
            return []
        chain = []
        layout_match = matching_layout_placeholder(self.layout_element, placeholder)
        if layout_match is not None:
            chain.append(("layout", layout_match))
        master_match = matching_master_placeholder(self.master_element, placeholder_of(layout_match) if layout_match is not None else placeholder)
        if master_match is not None:
            chain.append(("master", master_match))
        return chain

    def color_map(self) -> dict[str, str]:
        mapping = dict(DEFAULT_COLOR_MAP)
        master_map = self.master_element.find(qn("p:clrMap"))
        if master_map is not None:
            mapping.update(master_map.attrib)
        for element in (self.layout_element, self.slide._element):
            override = element.find(f"{qn('p:clrMapOvr')}/{qn('a:overrideClrMapping')}")
            if override is not None:
                mapping.update(override.attrib)
        return mapping


def slide_context(presentation, slide) -> SlideContext:
    layout = slide.slide_layout
    master = layout.slide_master
    return SlideContext(slide, layout._element, master._element, presentation.part._element, theme_element(master.part))


def theme_element(master_part):
    theme_part = master_part.part_related_by(RELATIONSHIP_TYPE.THEME)
    return parsed_theme(theme_part.partname, theme_part.blob)


@functools.lru_cache(maxsize=8)
def parsed_theme(partname: str, blob: bytes):
    return etree.fromstring(blob)


def matching_layout_placeholder(layout_element, placeholder):
    candidates = list(layout_element.iter(qn("p:ph")))
    index = placeholder.get("idx")
    if index is not None:
        by_index = next((candidate for candidate in candidates if candidate.get("idx", "0") == index), None)
        if by_index is not None:
            return owning_shape(by_index)
    wanted = placeholder.get("type", "obj")
    by_type = next((candidate for candidate in candidates if candidate.get("type", "obj") == wanted), None)
    return owning_shape(by_type) if by_type is not None else None


def matching_master_placeholder(master_element, placeholder):
    if placeholder is None:
        return None
    wanted = master_type(placeholder.get("type", "obj"))
    match = next((candidate for candidate in master_element.iter(qn("p:ph")) if master_type(candidate.get("type", "obj")) == wanted), None)
    return owning_shape(match) if match is not None else None


def master_type(placeholder_type: str) -> str:
    return MASTER_PLACEHOLDER_TYPES.get(placeholder_type, placeholder_type)


def owning_shape(placeholder):
    return placeholder.getparent().getparent().getparent()


def master_text_style(context: SlideContext, element):
    placeholder = placeholder_of(element)
    if placeholder is None:
        return None
    placeholder_kind = placeholder.get("type", "obj")
    style_name = "p:titleStyle" if placeholder_kind in TITLE_TYPES else "p:bodyStyle" if placeholder_kind in BODY_STYLE_TYPES else "p:otherStyle"
    return context.master_element.find(f"{qn('p:txStyles')}/{qn(style_name)}")
