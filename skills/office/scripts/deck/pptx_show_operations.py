from __future__ import annotations

from lxml import etree
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn

from core.office_operations import Change
from deck.pptx_animation import remove_animations_of
from deck.pptx_shape_kinds import NON_VISUAL_TAGS, shape_identifier
from deck.pptx_targets import PptxEditing, live_slides, resolve_shape, resolve_slide


MARKUP_COMPATIBILITY = "http://schemas.openxmlformats.org/markup-compatibility/2006"
TRANSITION_SPEEDS = {"fast": "fast", "medium": "med", "slow": "slow"}
SLIDE_PARTS_AFTER_TRANSITION = (qn("p:timing"), qn("p:extLst"))
MILLISECONDS_PER_SECOND = 1000
DEFAULT_DURATION_SECONDS = 0.5
ENTRANCE_PRESETS = {"appear": 1, "fly_in": 2, "fade": 10, "wipe": 22, "zoom": 53}
DIRECTION_SUBTYPES = {"from_top": 1, "from_right": 2, "from_bottom": 4, "from_left": 8}
WIPE_FILTERS = {"from_top": "wipe(down)", "from_right": "wipe(left)", "from_bottom": "wipe(up)", "from_left": "wipe(right)"}
FLY_IN_STARTS = {
    "from_top": ("#ppt_x", "0-#ppt_h/2"),
    "from_right": ("1+#ppt_w/2", "#ppt_y"),
    "from_bottom": ("#ppt_x", "1+#ppt_h/2"),
    "from_left": ("0-#ppt_w/2", "#ppt_y"),
}
NODE_TYPES = {"on_click": "clickEffect", "with_previous": "withEffect", "after_previous": "afterEffect"}
ZOOM_SUBTYPE = 16


def plan_set_transition(editing: PptxEditing, operation: dict, location: str) -> Change:
    slides = [resolve_slide(editing, operation["slide"], f"{location}.slide")] if operation.get("slide") is not None else live_slides(editing)

    def change() -> str:
        for slide in slides:
            write_transition(slide._element, operation)
        scope = f"slide {operation['slide']}" if operation.get("slide") is not None else "every slide"
        return f"set the {operation['kind']} transition on {scope}"
    return change


def write_transition(slide_element, operation: dict) -> None:
    for existing in transitions_of(slide_element):
        slide_element.remove(existing)
    if operation["kind"] == "none" and operation.get("advanceAfter") is None:
        return
    transition = etree.Element(qn("p:transition"), spd=TRANSITION_SPEEDS[operation.get("speed", "medium")])
    if operation.get("advanceAfter") is not None:
        transition.set("advTm", str(round(operation["advanceAfter"] * MILLISECONDS_PER_SECOND)))
    if operation["kind"] != "none":
        etree.SubElement(transition, qn(f"p:{operation['kind']}"))
    following = next((child for child in slide_element if child.tag in SLIDE_PARTS_AFTER_TRANSITION), None)
    if following is None:
        slide_element.append(transition)
    else:
        following.addprevious(transition)


def transitions_of(slide_element) -> list:
    direct = slide_element.findall(qn("p:transition"))
    alternates = [child for child in slide_element.findall(f"{{{MARKUP_COMPATIBILITY}}}AlternateContent") if any(child.iter(qn("p:transition")))]
    return direct + alternates


def plan_add_animation(editing: PptxEditing, operation: dict, location: str) -> Change:
    target = resolve_shape(editing, operation, location)

    def change() -> str:
        timing = timing_of(target.slide._element)
        identifiers = TimeNodeIdentifiers(timing)
        main_sequence = timing.find(f".//{qn('p:cTn')}[@nodeType='mainSeq']/{qn('p:childTnLst')}")
        append_effect(main_sequence, effect_xml(operation, str(shape_identifier(target.element)), identifiers), operation.get("start", "on_click"), identifiers)
        if target.element.find(qn("p:txBody")) is not None:
            add_build_entry(timing, str(shape_identifier(target.element)))
        editing.mark_edited(target.slide)
        return f"added a {operation['effect']} entrance to {target.label}, {operation.get('start', 'on_click').replace('_', ' ')}"
    return change


class TimeNodeIdentifiers:
    def __init__(self, timing) -> None:
        self.last = max((int(node.get("id")) for node in timing.iter(qn("p:cTn")) if node.get("id", "").isdigit()), default=0)

    def next(self) -> str:
        self.last += 1
        return str(self.last)


def timing_of(slide_element):
    timing = slide_element.find(qn("p:timing"))
    if timing is None:
        timing = parse_xml(f'<p:timing {nsdecls("p")}><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst/></p:cTn></p:par></p:tnLst></p:timing>')
        following = slide_element.find(qn("p:extLst"))
        if following is None:
            slide_element.append(timing)
        else:
            following.addprevious(timing)
    if timing.find(f".//{qn('p:cTn')}[@nodeType='mainSeq']") is None:
        root = timing.find(f".//{qn('p:cTn')}[@nodeType='tmRoot']/{qn('p:childTnLst')}")
        root.insert(0, main_sequence_xml(TimeNodeIdentifiers(timing).next()))
    return timing


def main_sequence_xml(identifier: str):
    return parse_xml(
        f'<p:seq {nsdecls("p")} concurrent="1" nextAc="seek"><p:cTn id="{identifier}" dur="indefinite" nodeType="mainSeq"><p:childTnLst/></p:cTn>'
        '<p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>'
        '<p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst></p:seq>'
    )


def append_effect(main_sequence, effect, start: str, identifiers: TimeNodeIdentifiers) -> None:
    click_groups = main_sequence.findall(qn("p:par"))
    if start == "on_click" or not click_groups:
        group = timed_group(identifiers, "indefinite", automatic=start != "on_click")
        main_sequence.append(group)
        step_list(group).append(timed_group(identifiers, "0"))
    else:
        group = click_groups[-1]
        if start == "after_previous":
            step_list(group).append(timed_group(identifiers, str(steps_end(group))))
    step_list(step_list(group)[-1]).append(effect)


def timed_group(identifiers: TimeNodeIdentifiers, delay: str, automatic: bool = False):
    begin = '<p:cond evt="onBegin" delay="0"><p:tn val="2"/></p:cond>' if automatic else ""
    return parse_xml(f'<p:par {nsdecls("p")}><p:cTn id="{identifiers.next()}" fill="hold"><p:stCondLst><p:cond delay="{delay}"/>{begin}</p:stCondLst><p:childTnLst/></p:cTn></p:par>')


def step_list(group):
    return group.find(f"{qn('p:cTn')}/{qn('p:childTnLst')}")


def steps_end(group) -> int:
    end = 0
    for step in step_list(group).findall(qn("p:par")):
        delay = int(step.find(f"{qn('p:cTn')}/{qn('p:stCondLst')}/{qn('p:cond')}").get("delay"))
        end = max(end, delay + max((effect_length(effect) for effect in step_list(step).findall(qn("p:par"))), default=0))
    return end


def effect_length(effect) -> int:
    delay = int(effect.find(f"{qn('p:cTn')}/{qn('p:stCondLst')}/{qn('p:cond')}").get("delay", "0"))
    durations = [int(node.get("dur")) for node in effect.iter(qn("p:cTn")) if node.get("dur", "").isdigit()]
    return delay + max(durations, default=0)


def effect_xml(operation: dict, shape_id: str, identifiers: TimeNodeIdentifiers):
    effect = operation["effect"]
    direction = operation.get("direction", "from_bottom")
    duration = round(operation.get("duration", DEFAULT_DURATION_SECONDS) * MILLISECONDS_PER_SECOND)
    delay = round(operation.get("delay", 0) * MILLISECONDS_PER_SECOND)
    subtype = DIRECTION_SUBTYPES[direction] if effect in ("fly_in", "wipe") else ZOOM_SUBTYPE if effect == "zoom" else 0
    behaviors = [visibility_xml(shape_id, identifiers)] + motion_xml(effect, direction, shape_id, duration, identifiers)
    return parse_xml(
        f'<p:par {nsdecls("p")}><p:cTn id="{identifiers.next()}" presetID="{ENTRANCE_PRESETS[effect]}" presetClass="entr" presetSubtype="{subtype}" '
        f'fill="hold" grpId="0" nodeType="{NODE_TYPES[operation.get("start", "on_click")]}"><p:stCondLst><p:cond delay="{delay}"/></p:stCondLst>'
        f'<p:childTnLst>{"".join(behaviors)}</p:childTnLst></p:cTn></p:par>'
    )


def target_xml(shape_id: str) -> str:
    return f'<p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl>'


def visibility_xml(shape_id: str, identifiers: TimeNodeIdentifiers) -> str:
    return (
        f'<p:set><p:cBhvr><p:cTn id="{identifiers.next()}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>'
        f'{target_xml(shape_id)}<p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst></p:cBhvr><p:to><p:strVal val="visible"/></p:to></p:set>'
    )


def motion_xml(effect: str, direction: str, shape_id: str, duration: int, identifiers: TimeNodeIdentifiers) -> list[str]:
    if effect == "fade":
        return [filter_xml("fade", shape_id, duration, identifiers)]
    if effect == "wipe":
        return [filter_xml(WIPE_FILTERS[direction], shape_id, duration, identifiers)]
    if effect == "fly_in":
        start_x, start_y = FLY_IN_STARTS[direction]
        return [property_xml("ppt_x", start_x, "#ppt_x", shape_id, duration, identifiers), property_xml("ppt_y", start_y, "#ppt_y", shape_id, duration, identifiers)]
    if effect == "zoom":
        return [
            property_xml("ppt_w", "0", "#ppt_w", shape_id, duration, identifiers),
            property_xml("ppt_h", "0", "#ppt_h", shape_id, duration, identifiers),
            filter_xml("fade", shape_id, duration, identifiers),
        ]
    return []


def filter_xml(name: str, shape_id: str, duration: int, identifiers: TimeNodeIdentifiers) -> str:
    return f'<p:animEffect transition="in" filter="{name}"><p:cBhvr><p:cTn id="{identifiers.next()}" dur="{duration}"/>{target_xml(shape_id)}</p:cBhvr></p:animEffect>'


def property_xml(name: str, start: str, end: str, shape_id: str, duration: int, identifiers: TimeNodeIdentifiers) -> str:
    return (
        f'<p:anim calcmode="lin" valueType="num"><p:cBhvr additive="base"><p:cTn id="{identifiers.next()}" dur="{duration}" fill="hold"/>{target_xml(shape_id)}'
        f"<p:attrNameLst><p:attrName>{name}</p:attrName></p:attrNameLst></p:cBhvr>"
        f'<p:tavLst><p:tav tm="0"><p:val><p:strVal val="{start}"/></p:val></p:tav><p:tav tm="100000"><p:val><p:strVal val="{end}"/></p:val></p:tav></p:tavLst></p:anim>'
    )


def add_build_entry(timing, shape_id: str) -> None:
    build_list = timing.find(qn("p:bldLst"))
    if build_list is None:
        build_list = etree.SubElement(timing, qn("p:bldLst"))
    if any(entry.get("spid") == shape_id for entry in build_list):
        return
    etree.SubElement(build_list, qn("p:bldP"), spid=shape_id, grpId="0", animBg="1")


def plan_remove_animations(editing: PptxEditing, operation: dict, location: str) -> Change:
    slide = resolve_slide(editing, operation["slide"], f"{location}.slide")
    target = resolve_shape(editing, operation, location) if operation.get("shape") is not None else None

    def change() -> str:
        scope = target.element if target is not None else slide._element.find(qn("p:cSld"))
        identifiers = {str(properties[0].get("id")) for properties in scope.iter(*NON_VISUAL_TAGS)}
        removed = remove_animations_of(slide._element, identifiers)
        editing.mark_edited(slide)
        owner = target.label if target is not None else f"slide {operation['slide']}"
        return f"removed {removed} animations of {owner}"
    return change


SHOW_PLANNERS = {
    "set_transition": plan_set_transition,
    "add_animation": plan_add_animation,
    "remove_animations": plan_remove_animations,
}
