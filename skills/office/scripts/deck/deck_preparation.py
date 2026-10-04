from __future__ import annotations

from dataclasses import dataclass
import base64
import json
import mimetypes
import os
import pathlib

from core.host_contract import HOST_CONTRACT, RUNTIME_CONTEXT_VARIABLE
from deck.deck_design import DESIGN_PATH, Design, design_colors, design_style, resolve_design
from deck.deck_kit import KIT_MARKER, theme_palettes
from deck.deck_logo import Logo, read_logo
from deck.deck_source import Element, find_all
from schemas.known_values import RuntimeContext, load_runtime_context


PREPARATION_REQUEST_FILE = HOST_CONTRACT["deckPreparation"]["requestFile"]
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")
PLATED_CLASS = "kit-logo kit-plated"
PLAIN_CLASS = "kit-logo"


@dataclass(frozen=True)
class DeckPreparation:
    design: Design
    logo: Logo | None
    images: tuple[dict, ...]
    is_requested: bool

    def to_json(self) -> dict:
        record = {"design": self.design.to_json(), "images": [image["path"] for image in self.images]}
        return record | ({"logo": str(self.logo.path)} if self.logo else {})


def body_attributes(root: Element) -> dict[str, str]:
    bodies = find_all(root, "body")
    return dict(bodies[0].attributes) if bodies else {}


def prepare_deck(root: Element, context: RuntimeContext | None = None) -> DeckPreparation:
    context = context or load_runtime_context() or RuntimeContext()
    logo_path = context.logo_path()
    logo = read_logo(logo_path) if logo_path else None
    attributes = body_attributes(root)
    brand_color = None if attributes.get("data-accent") else (logo.brand_color if logo else None)
    design = resolve_design(attributes, context.deck_design, brand_color)
    return DeckPreparation(design, logo, image_candidates(context), context.prepares_decks and context.deck_design is None)


def image_candidates(context: RuntimeContext) -> tuple[dict, ...]:
    listed = [image for image in context.images if pathlib.Path(image["path"]).is_file()]
    known = {image["path"] for image in listed}
    attached = [attached_image(attachment) for attachment in context.attachments if is_attached_image(attachment, known)]
    return tuple(listed + attached)


def is_attached_image(attachment: dict, known: set[str]) -> bool:
    path = str(attachment.get("path") or "")
    return path not in known and pathlib.Path(path).suffix.casefold() in IMAGE_SUFFIXES and pathlib.Path(path).is_file()


def attached_image(attachment: dict) -> dict:
    from PIL import Image

    path = pathlib.Path(attachment["path"])
    with Image.open(path) as image:
        width, height = image.size
    return {"path": str(path), "name": attachment.get("name") or path.name, "source": "attachment", "width": width, "height": height}


def deck_palette(preparation: DeckPreparation) -> dict[str, str]:
    if preparation.design.theme:
        return {name: value.lstrip("#") for name, value in theme_palettes().get(preparation.design.theme, {}).items()}
    return design_colors(preparation.design)


def kit_additions(preparation: DeckPreparation) -> str:
    style = f"<style {KIT_MARKER}>\n{design_style(preparation.design)}\n</style>\n"
    return style + logo_script(preparation)


def logo_script(preparation: DeckPreparation) -> str:
    logo = preparation.logo
    if logo is None:
        return ""
    palette = deck_palette(preparation)
    document = {
        "src": data_uri(logo.path),
        "ratio": round(logo.width / logo.height, 4),
        "pageClass": PLATED_CLASS if logo.needs_plate(palette.get("bg", "FFFFFF")) else PLAIN_CLASS,
        "featureClass": PLATED_CLASS if logo.needs_plate(palette.get("feature-bg", "000000")) else PLAIN_CLASS,
    }
    return f"<script {KIT_MARKER}>\nwindow.deckKitLogo = {json.dumps(document)};\n</script>\n"


def data_uri(path: pathlib.Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime_type};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def request_preparation(preparation: DeckPreparation) -> pathlib.Path | None:
    context_path = os.environ.get(RUNTIME_CONTEXT_VARIABLE, "").strip()
    if not preparation.is_requested or not context_path:
        return None
    request_path = pathlib.Path(context_path).parent / PREPARATION_REQUEST_FILE
    request_path.write_text(json.dumps({"design": str(DESIGN_PATH)}), encoding="utf-8")
    return request_path
