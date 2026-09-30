from __future__ import annotations

import base64
import html
import mimetypes
import pathlib
import re


SKILL_ASSET_PATH = pathlib.Path(__file__).resolve().parents[2] / "assets"
SKILL_ASSET_MARKER = "office/assets/"
PAPERLOGY_FAMILY = "Paperlogy"
VENDORED_PAPERLOGY_FAMILY = "PaperlogyLocal"
VENDORED_PAPERLOGY_FONTS = (
    (400, "Paperlogy-4Regular.woff2"),
    (600, "Paperlogy-6SemiBold.woff2"),
    (700, "Paperlogy-7Bold.woff2"),
    (800, "Paperlogy-8ExtraBold.woff2"),
)
PAPERLOGY_ALIASES = {
    "fonts/Paperlogy-Regular.woff2": "fonts/paperlogy/Paperlogy-4Regular.woff2",
    "fonts/Paperlogy-Medium.woff2": "fonts/paperlogy/Paperlogy-6SemiBold.woff2",
    "fonts/Paperlogy-SemiBold.woff2": "fonts/paperlogy/Paperlogy-6SemiBold.woff2",
    "fonts/Paperlogy-Bold.woff2": "fonts/paperlogy/Paperlogy-7Bold.woff2",
    "fonts/Paperlogy-ExtraBold.woff2": "fonts/paperlogy/Paperlogy-8ExtraBold.woff2",
}
IMAGE_MIME_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
    "svg": "image/svg+xml",
}
FONT_MIME_TYPES = {
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".otf": "font/otf",
    ".ttf": "font/ttf",
}
REMOTE_URL_PREFIXES = ("data:", "http:", "https:")


def inject_vendored_paperlogy_fallback(source_text: str) -> str:
    source_text = add_paperlogy_local_to_font_family_lists(source_text)
    font_style = vendored_paperlogy_fallback_style()
    if "data-internkim-vendored-fonts" in source_text:
        return re.sub(
            r"<style\b[^>]*data-internkim-vendored-fonts[^>]*>.*?</style>",
            font_style,
            source_text,
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        )
    style_match = re.search(r"<style\b[^>]*>", source_text, flags=re.IGNORECASE)
    if style_match:
        return insert_text(source_text, style_match.start(), "\n" + font_style + "\n")
    head_match = re.search(r"</head>", source_text, flags=re.IGNORECASE)
    if head_match:
        return insert_text(source_text, head_match.start(), "<style>\n" + font_style + "\n</style>\n")
    return "<style>\n" + font_style + "\n</style>\n" + source_text


def insert_text(source_text: str, insert_index: int, inserted_text: str) -> str:
    return source_text[:insert_index] + inserted_text + source_text[insert_index:]


def add_paperlogy_local_to_font_family_lists(source_text: str) -> str:
    if "PaperlogyLocal" in source_text:
        return source_text
    source_text = re.sub(
        r'(["\']Paperlogy["\']\s*,)(?!\s*["\']PaperlogyLocal["\'])',
        r'\1 "PaperlogyLocal",',
        source_text,
    )
    return re.sub(
        r'(?<![-\w])Paperlogy\s*,(?!\s*["\']?PaperlogyLocal)',
        'Paperlogy, "PaperlogyLocal",',
        source_text,
    )


def vendored_paperlogy_fallback_style() -> str:
    rules = [paperlogy_local_font_face(weight, file_name) for weight, file_name in VENDORED_PAPERLOGY_FONTS]
    return '<style data-internkim-vendored-fonts>' + "\n".join(rules) + "</style>"


def paperlogy_local_font_face(weight: int, file_name: str) -> str:
    font_path = SKILL_ASSET_PATH / "fonts" / "paperlogy" / file_name
    return (
        f'@font-face {{ font-family: "{VENDORED_PAPERLOGY_FAMILY}"; '
        f"font-weight: {weight}; font-style: normal; font-display: swap; "
        f'src: url("{base64_data_url("font/woff2", font_path)}") format("woff2"); }}'
    )


def inline_local_images(source_text: str, base_path: pathlib.Path) -> str:
    image_pattern = r'src="([^"]+\.(?:png|jpg|jpeg|gif|webp|svg))"'

    def replace_image(match: re.Match[str]) -> str:
        image_path = local_resource_path(match.group(1), base_path)
        if image_path is None:
            return match.group(0)
        return f'src="{base64_data_url(image_mime_type(image_path), image_path)}"'

    return re.sub(image_pattern, replace_image, source_text, flags=re.IGNORECASE)


def inline_local_fonts(source_text: str, base_path: pathlib.Path) -> str:
    font_pattern = r"url\((['\"]?)([^)'\"]+\.(?:woff2|woff|otf|ttf)(?:[?#][^)'\"]*)?)\1\)"

    def replace_font(match: re.Match[str]) -> str:
        font_path = local_resource_path(match.group(2), base_path)
        if font_path is None:
            return match.group(0)
        quote = match.group(1) or ""
        return f"url({quote}{base64_data_url(font_mime_type(font_path), font_path)}{quote})"

    return re.sub(font_pattern, replace_font, source_text, flags=re.IGNORECASE)


def local_resource_path(escaped_url: str, base_path: pathlib.Path) -> pathlib.Path | None:
    resource_url = html.unescape(escaped_url)
    if resource_url.startswith(REMOTE_URL_PREFIXES):
        return None
    resource_path = resolve_resource_path(resource_url, base_path)
    if resource_path is None or not resource_path.exists():
        return None
    return resource_path


def resolve_resource_path(resource_url: str, base_path: pathlib.Path) -> pathlib.Path | None:
    clean_url = resource_url.split("#", 1)[0].split("?", 1)[0]
    if clean_url.startswith("file://"):
        return pathlib.Path(clean_url.removeprefix("file://"))
    resource_path = pathlib.Path(clean_url)
    if resource_path.is_absolute():
        return resolve_skill_asset_path(resource_path) or resource_path
    resolved_path = (base_path / resource_path).resolve()
    if resolved_path.exists():
        return resolved_path
    return resolve_skill_asset_path(resource_path)


def resolve_skill_asset_path(resource_path: pathlib.Path) -> pathlib.Path | None:
    path_text = str(resource_path)
    if SKILL_ASSET_MARKER not in path_text:
        return None
    asset_relative_text = path_text.split(SKILL_ASSET_MARKER, 1)[1].lstrip("/")
    asset_path = SKILL_ASSET_PATH / asset_relative_text
    if asset_path.exists():
        return asset_path
    return resolve_paperlogy_alias(asset_relative_text)


def resolve_paperlogy_alias(asset_relative_text: str) -> pathlib.Path | None:
    aliased_path = PAPERLOGY_ALIASES.get(asset_relative_text)
    if aliased_path is None:
        return None
    resolved_path = SKILL_ASSET_PATH / aliased_path
    if resolved_path.exists():
        return resolved_path
    return None


def base64_data_url(mime_type: str, path: pathlib.Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime_type};base64,{encoded}"


def image_mime_type(path: pathlib.Path) -> str:
    extension = path.suffix.lower().removeprefix(".")
    return IMAGE_MIME_TYPES.get(extension) or guessed_mime_type(path)


def font_mime_type(path: pathlib.Path) -> str:
    return FONT_MIME_TYPES.get(path.suffix.lower()) or guessed_mime_type(path)


def guessed_mime_type(path: pathlib.Path) -> str:
    return mimetypes.guess_type(path)[0] or "application/octet-stream"
