from __future__ import annotations

from pptx.oxml.ns import qn


def remove_animations_of(slide_element, shape_identifiers: set[str]) -> int:
    timing = slide_element.find(qn("p:timing"))
    if timing is None:
        return 0
    effects = {effect_of(target) for target in timing.iter(qn("p:spTgt")) if target.get("spid") in shape_identifiers}
    effects.discard(None)
    for effect in effects:
        remove_and_prune(effect)
    for build in [build for build in timing.iter(qn("p:bldP"), qn("p:bldGraphic"), qn("p:bldOleChart"), qn("p:bldDgm")) if build.get("spid") in shape_identifiers]:
        build.getparent().remove(build)
    build_list = timing.find(qn("p:bldLst"))
    if build_list is not None and len(build_list) == 0:
        timing.remove(build_list)
    if not any(timing.iter(qn("p:spTgt"))):
        slide_element.remove(timing)
    return len(effects)


def effect_of(target):
    node = target
    while node is not None:
        time_node = node.find(qn("p:cTn")) if node.tag == qn("p:par") else None
        if time_node is not None and time_node.get("presetClass") is not None:
            return node
        node = node.getparent()
    return None


def remove_and_prune(element) -> None:
    parent = element.getparent()
    parent.remove(element)
    while parent is not None and parent.tag == qn("p:childTnLst") and len(parent) == 0:
        owner = parent.getparent().getparent()
        if owner is None or owner.tag != qn("p:par"):
            return
        grandparent = owner.getparent()
        grandparent.remove(owner)
        parent = grandparent
