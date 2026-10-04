from __future__ import annotations

from dataclasses import dataclass
import base64
import json
import mimetypes
import os
import pathlib

from core.host_contract import HOST_CONTRACT, RUNTIME_CONTEXT_VARIABLE
from deck.deck_design import DESIGN_PATH, Design, resolve_design
from deck.deck_kit import KIT_MARKER
from deck.deck_logo import Logo, read_logo
from deck.design_system import DesignSystem, design_style
from schemas.known_values import RuntimeContext, load_runtime_context


PREPARATION_REQUEST_FILE = HOST_CONTRACT["deckPreparation"]["requestFile"]
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


@dataclass(frozen=True)
class DeckPreparation:
    design: Design
    logo: Logo | None
    images: tuple[dict, ...]
    unreadable_images: tuple[str, ...]
    is_requested: bool

    def to_json(self) -> dict:
        record = {"design": self.design.to_json(), "images": [image["path"] for image in self.images]}
        return record | ({"logo": str(self.logo.path)} if self.logo else {})


def prepare_deck(context: RuntimeContext | None = None) -> DeckPreparation:
    context = context or load_runtime_context() or RuntimeContext()
    logo_path = context.logo_path()
    logo = read_logo(logo_path) if logo_path else None
    images, unreadable = image_candidates(context)
    design = resolve_design(context.deck_design, logo.brand_color if logo else None)
    return DeckPreparation(design, logo, images, unreadable, context.prepares_decks and context.deck_design is None)


def image_candidates(context: RuntimeContext) -> tuple[tuple[dict, ...], tuple[str, ...]]:
    listed = [image for image in context.images if pathlib.Path(image["path"]).is_file()]
    unreadable = tuple(image["path"] for image in context.images if not pathlib.Path(image["path"]).is_file())
    known = {image["path"] for image in listed}
    attached = [attached_image(attachment) for attachment in context.attachments if is_attached_image(attachment, known)]
    return tuple(listed + attached), unreadable


def is_attached_image(attachment: dict, known: set[str]) -> bool:
    path = str(attachment.get("path") or "")
    return path not in known and pathlib.Path(path).suffix.casefold() in IMAGE_SUFFIXES and pathlib.Path(path).is_file()


def attached_image(attachment: dict) -> dict:
    from PIL import Image

    path = pathlib.Path(attachment["path"])
    with Image.open(path) as image:
        width, height = image.size
    return {"path": str(path), "name": attachment.get("name") or path.name, "source": "attachment", "width": width, "height": height}


def kit_additions(preparation: DeckPreparation, system: DesignSystem | None) -> str:
    style = f"<style {KIT_MARKER}>\n{design_style(system)}\n</style>\n" if system else ""
    return style + logo_script(preparation)


def logo_script(preparation: DeckPreparation) -> str:
    logo = preparation.logo
    if logo is None:
        return ""
    document = {
        "src": data_uri(logo.path),
        "ratio": round(logo.width / logo.height, 4),
        "ink": [int(logo.ink[index:index + 2], 16) for index in (0, 2, 4)],
        "hasTransparency": logo.has_transparency,
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
