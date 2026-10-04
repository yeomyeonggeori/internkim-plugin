from __future__ import annotations

import functools
import pathlib
import re

from deck.resource_inlining import resolve_resource_path


IMAGE_TAG_PATTERN = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
SOURCE_PATTERN = re.compile(r"\bsrc\s*=\s*([\"'])(.*?)\1", re.IGNORECASE | re.DOTALL)
STYLE_PATTERN = re.compile(r"\bstyle\s*=\s*([\"'])(.*?)\1", re.IGNORECASE | re.DOTALL)
LOGO_ATTRIBUTE_PATTERN = re.compile(r"\bdata-logo\b", re.IGNORECASE)
SAMPLE_SIDE = 96
STRONGEST_SHARE = 0.2
FOCUS_RANGE = (15, 85)
FOCUS_PROPERTY = "object-position"
FOCUS_MARKER = "data-internkim-focus"
FOCUS_DECLARATION_PATTERN = re.compile(r";?\s*object-position:\s*\d+% \d+%")
EMPTY_STYLE_PATTERN = re.compile(r"\s*style\s*=\s*([\"'])\s*\1", re.IGNORECASE)


@functools.lru_cache(maxsize=None)
def focal_point(path: pathlib.Path) -> tuple[int, int]:
    from PIL import Image, ImageFilter

    with Image.open(path) as image:
        sample = image.convert("L")
    sample.thumbnail((SAMPLE_SIDE, SAMPLE_SIDE))
    energy = sample.filter(ImageFilter.FIND_EDGES)
    width, height = energy.size
    values = list(energy.tobytes())
    cutoff = sorted(values)[int(len(values) * (1 - STRONGEST_SHARE))]
    strong = [(index % width, index // width) for index, value in enumerate(values) if value >= max(cutoff, 1)]
    if not strong:
        return 50, 50
    return clamped(sum(x for x, _ in strong) / len(strong) / width), clamped(sum(y for _, y in strong) / len(strong) / height)


def clamped(share: float) -> int:
    return max(FOCUS_RANGE[0], min(FOCUS_RANGE[1], round(share * 100)))


def focused_tag(tag: str, base_path: pathlib.Path) -> str:
    source = SOURCE_PATTERN.search(tag)
    if not source or LOGO_ATTRIBUTE_PATTERN.search(tag) or source.group(2).startswith(("data:", "http:", "https:")):
        return tag
    resolved = resolve_resource_path(source.group(2), base_path)
    if resolved is None or not resolved.is_file():
        return tag
    x, y = focal_point(resolved)
    declaration = f"{FOCUS_PROPERTY}: {x}% {y}%"
    style = STYLE_PATTERN.search(tag)
    if style and FOCUS_PROPERTY in style.group(2):
        return tag
    if style:
        return marked(tag[:style.start(2)] + style.group(2).rstrip("; ") + f"; {declaration}" + tag[style.end(2):])
    return marked(tag[:source.start()] + f'style="{declaration}" ' + tag[source.start():])


def marked(tag: str) -> str:
    is_self_closed = tag.endswith("/>")
    body = tag[:-2] if is_self_closed else tag[:-1]
    return f"{body.rstrip()} {FOCUS_MARKER}{'/>' if is_self_closed else '>'}"


def unfocused_tag(tag: str) -> str:
    if FOCUS_MARKER not in tag:
        return tag
    tag = re.sub(rf"\s*{FOCUS_MARKER}", "", tag)
    tag = STYLE_PATTERN.sub(lambda style: style.group(0).replace(style.group(2), FOCUS_DECLARATION_PATTERN.sub("", style.group(2)).strip()), tag)
    return EMPTY_STYLE_PATTERN.sub("", tag)


def unfocus_photos(source_text: str) -> str:
    return IMAGE_TAG_PATTERN.sub(lambda match: unfocused_tag(match.group(0)), source_text)


def focus_photos(source_text: str, base_path: pathlib.Path) -> str:
    return IMAGE_TAG_PATTERN.sub(lambda match: focused_tag(match.group(0), base_path), source_text)
