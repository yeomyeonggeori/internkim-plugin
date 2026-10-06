from __future__ import annotations

from dataclasses import dataclass
import base64
import io
import json
import pathlib
import urllib.request

from deck.deck_decisions import decided, read_state, request_wordings, write_state
from deck.deck_kit import KIT_MARKER
from deck.deck_logo import Logo, cropped_logo_bytes, read_logo
from deck.design_system import DesignSystem, design_style
from deck.typeface import TYPEFACE, decided_type
from host import script_host
from host.task_context import state_directory
from schemas.known_values import RuntimeContext, load_runtime_context


PREPARATION_FILE = "deck-preparation.json"
IMAGES_DIRECTORY = "deck-images"
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")
DATA_ROOM_IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png")
DATA_ROOM_IMAGE_LIMIT = 24
DOWNLOAD_TIMEOUT_SECONDS = 30
DOWNLOAD_LIMIT_BYTES = 25 << 20
HOST_ERRORS = (script_host.HostFailure, script_host.HostUnavailable)


@dataclass(frozen=True)
class DeckPreparation:
    type_option: str
    logo: Logo | None
    images: tuple[dict, ...]
    unreadable_images: tuple[str, ...]

    def to_json(self) -> dict:
        record = {"type": self.type_option, "images": [image["path"] for image in self.images]}
        return record | ({"logo": str(self.logo.path)} if self.logo else {})


def prepare_deck(context: RuntimeContext | None = None) -> DeckPreparation:
    context = context or load_runtime_context() or RuntimeContext()
    prepared = read_state(PREPARATION_FILE) or {}
    logo_path = context.logo_path()
    logo = read_logo(logo_path) if logo_path else None
    images, unreadable = image_candidates(context, prepared.get("images") or [])
    return DeckPreparation(prepared_type(), logo, images, unreadable)


def prepared_type() -> str:
    return decided_type((read_state(PREPARATION_FILE) or {}).get("deckDesign"))


def ensure_prepared() -> None:
    if not script_host.is_present() or state_directory() is None or read_state(PREPARATION_FILE) is not None:
        return
    keep_company_profile()
    images = gathered_data_room_images()
    write_state(PREPARATION_FILE, {"deckDesign": decided_design(images), "images": images})


def keep_company_profile() -> None:
    try:
        script_host.call_tool("company_info_get", {})
    except HOST_ERRORS:
        return


def gathered_data_room_images() -> list[dict]:
    try:
        listing = script_host.call_tool("company_document_list", {})
    except HOST_ERRORS:
        return []
    directory = state_directory() / IMAGES_DIRECTORY
    directory.mkdir(parents=True, exist_ok=True)
    kept = (kept_data_room_image(directory, document) for document in image_documents(listing))
    return [image for image in kept if image is not None]


def image_documents(listing: dict) -> list[dict]:
    result = listing.get("result") if isinstance(listing.get("result"), dict) else {}
    documents = [document for document in result.get("documents") or () if isinstance(document, dict) and pathlib.Path(text_of(document.get("filePath"))).suffix.lower() in DATA_ROOM_IMAGE_SUFFIXES]
    documents.sort(key=lambda document: text_of(document.get("date")), reverse=True)
    return documents[:DATA_ROOM_IMAGE_LIMIT]


def kept_data_room_image(directory: pathlib.Path, document: dict) -> dict | None:
    content = downloaded_image(document)
    width, height = image_size(content) if content else (0, 0)
    if not width:
        return None
    name = pathlib.Path(text_of(document.get("filePath"))).name
    path = directory / name
    path.write_bytes(content)
    image = {"path": str(path), "name": name, "source": "dataroom", "folder": text_of(document.get("domain")) or text_of(document.get("categoryCode")),
             "title": text_of(document.get("title")), "summary": text_of(document.get("summary")), "date": text_of(document.get("date")), "width": width, "height": height}
    return {key: value for key, value in image.items() if value != ""}


def downloaded_image(document: dict) -> bytes | None:
    try:
        answer = script_host.call_tool("company_document_download", {"documentHint": document.get("documentID", "")})
    except HOST_ERRORS:
        return None
    result = answer.get("result") if isinstance(answer.get("result"), dict) else {}
    if answer.get("isError") or not result.get("downloadURL"):
        return None
    return fetched(result["downloadURL"])


def fetched(address: str) -> bytes | None:
    try:
        with urllib.request.urlopen(address, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            content = response.read(DOWNLOAD_LIMIT_BYTES + 1)
    except OSError:
        return None
    return content if len(content) <= DOWNLOAD_LIMIT_BYTES else None


def image_size(content: bytes) -> tuple[int, int]:
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(content)) as image:
            return image.size
    except (UnidentifiedImageError, OSError):
        return 0, 0


def decided_design(images: list[dict]) -> dict:
    described = [{"name": image["name"], "title": image.get("title", ""), "summary": image.get("summary", ""), "folder": image.get("folder", ""), "width": image["width"], "height": image["height"]} for image in images]
    return decided({"request": request_wordings(), "images": described + attached_images_for_decision()}, TYPEFACE)


def attached_images_for_decision() -> list[dict]:
    context = load_runtime_context() or RuntimeContext()
    return [{"name": attachment["name"], "source": "attachment"} for attachment in context.attachments if pathlib.Path(attachment["name"]).suffix.lower() in IMAGE_SUFFIXES]


def text_of(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def image_candidates(context: RuntimeContext, prepared_images: list[dict]) -> tuple[tuple[dict, ...], tuple[str, ...]]:
    gathered = [image for image in prepared_images if isinstance(image, dict) and image.get("path")]
    listed = [image for image in gathered if pathlib.Path(image["path"]).is_file()]
    unreadable = tuple(image["path"] for image in gathered if not pathlib.Path(image["path"]).is_file())
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
        "src": f"data:image/png;base64,{base64.b64encode(cropped_logo_bytes(logo)).decode('ascii')}",
        "ratio": round(logo.width / logo.height, 4),
        "ink": [int(logo.ink[index:index + 2], 16) for index in (0, 2, 4)],
        "hasTransparency": logo.has_transparency,
    }
    return f"<script {KIT_MARKER}>\nwindow.deckKitLogo = {json.dumps(document)};\n</script>\n"
