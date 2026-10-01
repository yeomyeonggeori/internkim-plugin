from __future__ import annotations

from dataclasses import dataclass
import functools
import hashlib
import io
import os
import pathlib

from fonts.truetype import ENGLISH_UNITED_STATES, FAMILY_NAME_ID, FULL_NAME_ID, SUBFAMILY_NAME_ID, TYPOGRAPHIC_FAMILY_NAME_ID, UNICODE_BMP_ENCODING, WINDOWS_PLATFORM, has_korean_code_page, license_allows_embedding
from skill_runtime import skill_cache_path


FONT_DIRECTORY = pathlib.Path(__file__).resolve().parents[2] / "assets" / "fonts"
OPENTYPE_FLAVOR = b"OTTO"
WOFF2_FLAVOR_OFFSET = 4
REGULAR_WEIGHT = 400
BOLD_WEIGHT = 700
POSTSCRIPT_NAME_ID = 6
FACE_NAME_IDS = (FAMILY_NAME_ID, FULL_NAME_ID, POSTSCRIPT_NAME_ID)

SANS_BODY = "sans body"
SERIF_BODY = "serif body"
MONOSPACE = "monospace"
DECK = "deck"
ROLE_GENERIC_FAMILIES = {SANS_BODY: "sans-serif", SERIF_BODY: "serif", MONOSPACE: "monospace"}
CSS_GENERIC_FAMILIES = frozenset({"serif", "sans-serif", "monospace", "system-ui", "ui-serif", "ui-sans-serif", "ui-monospace", "ui-rounded", "-apple-system", "blinkmacsystemfont", "cursive", "fantasy", "emoji", "math", "fangsong"})
OFFICE_KOREAN_FAMILY = "맑은 고딕"


@dataclass(frozen=True)
class BundledFace:
    weight: int
    file_name: str


@dataclass(frozen=True)
class BundledFamily:
    name: str
    directory: str
    role: str
    faces: tuple[BundledFace, ...]
    other_names: tuple[str, ...] = ()
    web_name: str | None = None

    @property
    def names(self) -> tuple[str, ...]:
        return (self.name, *self.other_names, *((self.web_name,) if self.web_name else ()))

    @property
    def generic(self) -> str | None:
        return ROLE_GENERIC_FAMILIES.get(self.role) if default_family(self.role) is self else None

    def face(self, weight: int) -> BundledFace:
        chosen = matched_weight(weight, sorted(face.weight for face in self.faces))
        return next(face for face in self.faces if face.weight == chosen)

    def asset(self, face: BundledFace) -> pathlib.Path:
        return FONT_DIRECTORY / self.directory / face.file_name

    def path(self, face: BundledFace) -> pathlib.Path:
        return unpacked_font(self.asset(face))


@dataclass(frozen=True)
class FaceFacts:
    family_names: tuple[str, ...]
    matched_family: str
    style: str
    fs_type: int
    panose: str
    is_korean: bool
    is_fixed_pitch: bool
    has_truetype_outlines: bool

    @property
    def can_embed_in_office(self) -> bool:
        return self.has_truetype_outlines and license_allows_embedding(self.fs_type)


@dataclass(frozen=True)
class ResolvedFace:
    family: BundledFamily
    face: BundledFace
    is_substitute: bool

    @property
    def path(self) -> pathlib.Path:
        return self.family.path(self.face)

    @property
    def typeface(self) -> str:
        return typeface(self.family, self.face)

    @property
    def matched_family(self) -> str:
        return face_facts(self.family, self.face).matched_family


FAMILIES = (
    BundledFamily("Pretendard", "pretendard", SANS_BODY, (
        BundledFace(400, "Pretendard-Regular.woff2"),
        BundledFace(600, "Pretendard-SemiBold.woff2"),
        BundledFace(700, "Pretendard-Bold.woff2"),
    ), other_names=("프리텐다드",)),
    BundledFamily("NanumMyeongjo", "nanum-myeongjo", SERIF_BODY, (
        BundledFace(400, "NanumMyeongjo.woff2"),
        BundledFace(700, "NanumMyeongjoBold.woff2"),
    ), other_names=("Nanum Myeongjo", "나눔명조")),
    BundledFamily("MaruBuri", "maruburi", SERIF_BODY, (
        BundledFace(400, "MaruBuri-Regular.woff2"),
        BundledFace(700, "MaruBuri-Bold.woff2"),
    ), other_names=("MaruBuriOTF", "마루 부리", "마루부리")),
    BundledFamily("D2Coding", "d2coding", MONOSPACE, (
        BundledFace(400, "D2Coding-Regular.woff2"),
        BundledFace(700, "D2Coding-Bold.woff2"),
    )),
    BundledFamily("Paperlogy", "paperlogy", DECK, (
        BundledFace(400, "Paperlogy-4Regular.woff2"),
        BundledFace(600, "Paperlogy-6SemiBold.woff2"),
        BundledFace(700, "Paperlogy-7Bold.woff2"),
        BundledFace(800, "Paperlogy-8ExtraBold.woff2"),
    ), other_names=("페이퍼로지",), web_name="PaperlogyLocal"),
    BundledFamily("Freesentation", "freesentation", DECK, (
        BundledFace(400, "Freesentation-4Regular.woff2"),
        BundledFace(700, "Freesentation-7Bold.woff2"),
    ), other_names=("프리젠테이션",)),
    BundledFamily("A2Z", "a2z", DECK, (
        BundledFace(400, "A2Z-4Regular.woff2"),
        BundledFace(700, "A2Z-7Bold.woff2"),
    ), other_names=("에이투지체", "에이투지")),
)

STAND_IN_ROLES = {
    "serif": SERIF_BODY,
    "ui-serif": SERIF_BODY,
    "fangsong": SERIF_BODY,
    "monospace": MONOSPACE,
    "ui-monospace": MONOSPACE,
    "바탕": SERIF_BODY,
    "batang": SERIF_BODY,
    "바탕체": SERIF_BODY,
    "batangche": SERIF_BODY,
    "궁서": SERIF_BODY,
    "gungsuh": SERIF_BODY,
    "times new roman": SERIF_BODY,
    "times": SERIF_BODY,
    "cambria": SERIF_BODY,
    "georgia": SERIF_BODY,
    "garamond": SERIF_BODY,
    "book antiqua": SERIF_BODY,
    "noto serif kr": SERIF_BODY,
    "noto serif cjk kr": SERIF_BODY,
    "apple myungjo": SERIF_BODY,
    "applemyungjo": SERIF_BODY,
    "courier new": MONOSPACE,
    "courier": MONOSPACE,
    "consolas": MONOSPACE,
    "menlo": MONOSPACE,
    "monaco": MONOSPACE,
    "cascadia code": MONOSPACE,
    "cascadia mono": MONOSPACE,
    "굴림체": MONOSPACE,
    "gulimche": MONOSPACE,
    "돋움체": MONOSPACE,
    "dotumche": MONOSPACE,
}


def default_family(role: str) -> BundledFamily:
    return next(family for family in FAMILIES if family.role == role)


def bundled_family(name: str) -> BundledFamily | None:
    return family_names().get(name.strip().casefold())


@functools.lru_cache(maxsize=None)
def family_names() -> dict[str, BundledFamily]:
    return {name.casefold(): family for family in FAMILIES for name in family.names}


@functools.lru_cache(maxsize=None)
def face_names() -> dict[str, tuple[BundledFamily, BundledFace]]:
    names: dict[str, tuple[BundledFamily, BundledFace]] = {}
    for family in FAMILIES:
        for face in family.faces:
            for name in face_identifiers(family.path(face)):
                names.setdefault(name.casefold(), (family, face))
    return names


def face_identifiers(path: pathlib.Path) -> tuple[str, ...]:
    names = [record.toUnicode() for record in name_records(path) if record.nameID in FACE_NAME_IDS]
    return tuple(dict.fromkeys([*names, *(name.replace(" ", "") for name in names)]))


@functools.lru_cache(maxsize=None)
def name_records(path: pathlib.Path) -> tuple:
    from fontTools.ttLib import TTFont

    with TTFont(str(path), lazy=True) as font:
        return tuple(font["name"].names)


def typeface(family: BundledFamily, face: BundledFace) -> str:
    return face_facts(family, face).family_names[0]


@functools.lru_cache(maxsize=None)
def face_facts(family: BundledFamily, face: BundledFace) -> FaceFacts:
    from fontTools.ttLib import TTFont

    with TTFont(str(family.path(face)), lazy=True) as font:
        names = font["name"]
        metrics = font["OS/2"]
        return FaceFacts(
            family_names=tuple(dict.fromkeys((english_name(names, FAMILY_NAME_ID), *(record.toUnicode() for record in names.names if record.nameID == FAMILY_NAME_ID)))),
            matched_family=english_name(names, TYPOGRAPHIC_FAMILY_NAME_ID, FAMILY_NAME_ID),
            style=english_name(names, SUBFAMILY_NAME_ID),
            fs_type=metrics.fsType,
            panose=panose_hex(metrics.panose),
            is_korean=has_korean_code_page(metrics.ulCodePageRange1),
            is_fixed_pitch=bool(font["post"].isFixedPitch),
            has_truetype_outlines="glyf" in font,
        )


def english_name(names, *name_ids: int) -> str:
    for name_id in name_ids:
        record = names.getName(name_id, WINDOWS_PLATFORM, UNICODE_BMP_ENCODING, ENGLISH_UNITED_STATES) or next((record for record in names.names if record.nameID == name_id), None)
        if record is not None:
            return record.toUnicode()
    raise LookupError(f"the font names none of {name_ids}")


def panose_hex(panose) -> str:
    fields = ("bFamilyType", "bSerifStyle", "bWeight", "bProportion", "bContrast", "bStrokeVariation", "bArmStyle", "bLetterForm", "bMidline", "bXHeight")
    return bytes(getattr(panose, field) for field in fields).hex().upper()


def stand_in_family(name: str) -> BundledFamily:
    return default_family(STAND_IN_ROLES.get(name.strip().casefold(), SANS_BODY))


def font_role(name: str) -> str:
    family = bundled_family(name)
    return family.role if family is not None else stand_in_family(name).role


def resolved_face(name: str, weight: int = REGULAR_WEIGHT) -> ResolvedFace:
    family = bundled_family(name)
    if family is not None:
        return ResolvedFace(family, family.face(weight), False)
    named = face_names().get(name.strip().casefold())
    if named is not None:
        return ResolvedFace(named[0], named[1], False)
    substitute = stand_in_family(name)
    return ResolvedFace(substitute, substitute.face(weight), True)


def matched_weight(desired: int, available: list[int]) -> int:
    if desired in available:
        return desired
    lighter = [weight for weight in reversed(available) if weight < desired]
    heavier = [weight for weight in available if weight > desired]
    if 400 <= desired <= 500:
        up_to_medium = [weight for weight in heavier if weight <= 500]
        return (up_to_medium or lighter or heavier)[0]
    if desired < 400:
        return (lighter or heavier)[0]
    return (heavier or lighter)[0]


def renderer_fonts() -> list[dict]:
    return [
        {"family": family.name, "weight": face.weight, "path": str(family.path(face)), "generic": family.generic}
        for family in FAMILIES
        for face in family.faces
    ]


@functools.lru_cache(maxsize=None)
def unpacked_font(asset: pathlib.Path) -> pathlib.Path:
    data = asset.read_bytes()
    suffix = ".otf" if data[WOFF2_FLAVOR_OFFSET:WOFF2_FLAVOR_OFFSET + 4] == OPENTYPE_FLAVOR else ".ttf"
    target = skill_cache_path(os.environ) / "fonts" / "bundled" / hashlib.sha256(data).hexdigest()[:16] / f"{asset.stem}{suffix}"
    if not target.exists():
        write_unpacked_font(data, target)
    return target


def write_unpacked_font(data: bytes, target: pathlib.Path) -> None:
    from fontTools.ttLib import woff2

    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(f"{target.name}.{os.getpid()}.partial")
    with open(partial, "wb") as output:
        woff2.decompress(io.BytesIO(data), output)
    partial.replace(target)

