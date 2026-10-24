from __future__ import annotations

from dataclasses import dataclass
import html
import mimetypes
from pathlib import Path
from string import Template

from core.image_fit import sized_style
from core.skill_paths import ASSETS_PATH
from paperwork.jurisdictions import Labels
from paperwork.paperwork_design import COLOR_INK, COLOR_MUTED, COLOR_RULE, SIZE_LETTERHEAD_DETAIL, SIZE_LETTERHEAD_NAME
from render.office_preview import data_uri

STATIONERY_CSS_PATH = ASSETS_PATH / "paperwork" / "stationery.css"
PICTURE_BOXES_MILLIMETERS = {"logo": (45.0, 10.0), "stamp": (16.0, 16.0)}


@dataclass(frozen=True)
class Letterhead:
    name: str
    details: tuple[str, ...]
    logo_path: str = ""


@dataclass(frozen=True)
class Signer:
    lines: tuple[str, ...]
    seal_mark: str = ""
    stamp_path: str = ""

    @property
    def is_sealed(self) -> bool:
        return bool(self.seal_mark or self.stamp_path)


def letterhead_of(profile: dict, labels: Labels) -> Letterhead:
    return Letterhead(company_display_name(profile), tuple(letterhead_detail_lines(profile, labels)), existing_file(profile.get("logoPath")))


def company_display_name(profile: dict) -> str:
    return text_of(profile.get("name") or profile.get("companyName")) if isinstance(profile, dict) else ""


def letterhead_detail_lines(profile: dict, labels: Labels) -> list[str]:
    identity = [*legal_identity(profile, labels), *representative_identity(profile, labels)]
    numbers = [f"{label} {text_of(profile.get(field))}" for field, label in (("phone", labels.phone), ("fax", labels.fax)) if text_of(profile.get(field))]
    contact = "  ".join([*numbers, *(text_of(profile.get(field)) for field in ("email", "website") if text_of(profile.get(field)))])
    return [line for line in ("  ".join(identity), text_of(profile.get("address")), contact) if line]


def legal_identity(profile: dict, labels: Labels) -> list[str]:
    attributes = profile.get("legalAttributes")
    pairs = [(text_of(attribute.get("label")), text_of(attribute.get("value"))) for attribute in (attributes if isinstance(attributes, list) else []) if isinstance(attribute, dict)]
    labeled = [f"{label} {value}" for label, value in pairs if label and value]
    registration = text_of(profile.get("registrationNumber"))
    return labeled or ([f"{labels.registration_number} {registration}"] if registration else [])


def representative_identity(profile: dict, labels: Labels) -> list[str]:
    representative = text_of(profile.get("representative"))
    if not representative:
        return []
    return [f"{text_of(profile.get('representativeTitle')) or labels.representative_title} {representative}"]


def letterhead_html(letterhead: Letterhead, missing_name_html: str = "") -> str:
    details = "".join(f'<p class="detail">{html.escape(line)}</p>' for line in letterhead.details)
    name = html.escape(letterhead.name) if letterhead.name else missing_name_html
    company = f'<div class="company"><p class="name">{name}</p>{details}</div>'
    return f'<header class="letterhead">{image_html(letterhead.logo_path, "logo")}{company}</header>'


def seal_html(seal_mark: str, stamp_path: str) -> str:
    stamp = image_html(stamp_path, "stamp")
    return f'<span class="seal">{html.escape(seal_mark)}{stamp}</span>' if seal_mark or stamp else ""


def signer_html(signer: Signer, alignment: str = "center") -> str:
    leading = "".join(f'<p class="line">{html.escape(line)}</p>' for line in signer.lines[:-1])
    sealed = " sealed" if signer.is_sealed else ""
    last = f'<p class="signer{sealed}"><span>{html.escape(signer.lines[-1])}</span>{seal_html(signer.seal_mark, signer.stamp_path)}</p>' if signer.lines else ""
    return f'<div class="signature {alignment}">{leading}{last}</div>'


def image_html(path_value: object, css_class: str) -> str:
    path = existing_file(path_value)
    if not path:
        return ""
    style = sized_style(Path(path), *PICTURE_BOXES_MILLIMETERS[css_class], "mm")
    return f'<img class="{css_class}" src="{data_uri(mimetypes.guess_type(path)[0] or "application/octet-stream", Path(path).read_bytes())}" style="{style}">'


def existing_file(path_value: object) -> str:
    path = text_of(path_value)
    return path if path and Path(path).is_file() else ""


def stationery_css() -> str:
    return Template(STATIONERY_CSS_PATH.read_text(encoding="utf-8")).substitute(
        ink=hex_color(COLOR_INK),
        muted=hex_color(COLOR_MUTED),
        rule=hex_color(COLOR_RULE),
        letterhead_name=f"{SIZE_LETTERHEAD_NAME}pt",
        letterhead_detail=f"{SIZE_LETTERHEAD_DETAIL}pt",
    )


def hex_color(color: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{channel:02X}" for channel in color)


def text_of(value: object) -> str:
    return "" if value is None else str(value).strip()
