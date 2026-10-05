from __future__ import annotations

from dataclasses import dataclass
import io
import json
import os
import pathlib
import re
import shutil
import urllib.error
import urllib.request
from typing import Callable

from fonts.registry import BundledFace, BundledFamily, DECK, shipped_family
from fonts.truetype import FAMILY_NAME_ID, TYPOGRAPHIC_FAMILY_NAME_ID, license_allows_embedding


FONT_SUFFIXES = (".ttf", ".otf", ".woff2")
TRUETYPE_SIGNATURES = (b"\x00\x01\x00\x00", b"true", b"OTTO", b"wOF2")
GOOGLE_FONT_DIRECTORIES = {"ofl": "OFL-1.1", "apache": "Apache-2.0", "ufl": "UFL-1.0"}
GOOGLE_LISTING_URL = "https://api.github.com/repos/google/fonts/contents/{directory}/{slug}"
WANTED_WEIGHTS = (400, 700)
DOWNLOAD_TIMEOUT_SECONDS = 20
DOWNLOAD_LIMIT_BYTES = 25 << 20
CACHE_ENVIRONMENT_VARIABLE = "OFFICE_FONT_CACHE"
META_FILE = "source.json"
DOWNLOADS_DIRECTORY = "downloads"
LOCAL_SOURCE = "local file"
CACHE_SOURCE = "cache"
BUNDLED_SOURCE = "bundled"
WEB_SOURCE = "google fonts"


@dataclass(frozen=True)
class FontSource:
    kind: str
    url: str | None = None
    license: str | None = None

    def to_json(self) -> dict:
        return {"kind": self.kind, "url": self.url, "license": self.license}


@dataclass(frozen=True)
class RequestedFont:
    family: BundledFamily
    source: FontSource


@dataclass(frozen=True)
class FontResolution:
    font: RequestedFont | None
    note: str | None
    tried: tuple[str, ...]


@dataclass(frozen=True)
class FontFile:
    path: pathlib.Path
    families: tuple[str, ...]
    weight: int
    is_italic: bool
    fs_type: int
    is_font: bool

    def is_named(self, name: str) -> bool:
        return name.strip().casefold() in {family.casefold() for family in self.families}

    @property
    def allows_embedding(self) -> bool:
        return license_allows_embedding(self.fs_type)


Fetcher = Callable[[str], bytes]


def fetch_url(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "internkim-office-font"})
    with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
        content = response.read(DOWNLOAD_LIMIT_BYTES + 1)
    if len(content) > DOWNLOAD_LIMIT_BYTES:
        raise ValueError(f"{url} is larger than {DOWNLOAD_LIMIT_BYTES} bytes")
    return content


def cache_directory() -> pathlib.Path:
    return pathlib.Path(os.environ.get(CACHE_ENVIRONMENT_VARIABLE) or pathlib.Path.home() / ".cache" / "internkim-office-fonts")


def slug_of(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.casefold())


def read_font_file(path: pathlib.Path) -> FontFile | None:
    from fontTools.ttLib import TTFont

    if path.suffix.casefold() not in FONT_SUFFIXES or not path.is_file() or path.read_bytes()[:4] not in TRUETYPE_SIGNATURES:
        return None
    try:
        with TTFont(str(path), lazy=True) as font:
            names = font["name"].names
            families = tuple(dict.fromkeys(record.toUnicode() for record in names if record.nameID in (FAMILY_NAME_ID, TYPOGRAPHIC_FAMILY_NAME_ID)))
            metrics = font["OS/2"]
            return FontFile(path, families, int(metrics.usWeightClass), bool(metrics.fsSelection & 1), int(metrics.fsType), True)
    except Exception:
        return None


def font_files_in(paths: list[pathlib.Path]) -> list[FontFile]:
    expanded = [file for path in paths for file in (sorted(path.rglob("*")) if path.is_dir() else [path])]
    return [read for read in (read_font_file(path) for path in expanded) if read is not None]


def named_faces(name: str, files: list[FontFile]) -> list[FontFile]:
    return [file for file in files if file.is_named(name) and not file.is_italic]


def resolve_requested_font(name: str, local_paths: list[pathlib.Path], cache: pathlib.Path | None = None, fetch: Fetcher = fetch_url) -> FontResolution:
    requested = name.strip()
    bundled = shipped_family(requested)
    if bundled is not None:
        return FontResolution(RequestedFont(bundled, FontSource(BUNDLED_SOURCE)), None, ())
    directory = (cache or cache_directory()) / slug_of(requested)
    tried = []
    for kind, files in ((LOCAL_SOURCE, font_files_in(local_paths)), (CACHE_SOURCE, font_files_in([directory]))):
        faces = named_faces(requested, files)
        tried.append(kind)
        if faces:
            return settled(requested, faces, directory, source_of(kind, directory), tried)
    tried.append(WEB_SOURCE)
    downloaded = download_from_google_fonts(requested, directory, fetch)
    if downloaded:
        return settled(requested, downloaded[0], directory, downloaded[1], tried)
    return FontResolution(None, unavailable_note(requested, tried), tuple(tried))


def source_of(kind: str, directory: pathlib.Path) -> FontSource:
    meta = directory / META_FILE
    if kind == CACHE_SOURCE and meta.is_file():
        recorded = json.loads(meta.read_text(encoding="utf-8"))
        return FontSource(recorded.get("kind", CACHE_SOURCE), recorded.get("url"), recorded.get("license"))
    return FontSource(kind)


def settled(name: str, faces: list[FontFile], directory: pathlib.Path, source: FontSource, tried: list[str]) -> FontResolution:
    embeddable = [face for face in faces if face.allows_embedding]
    if not embeddable:
        return FontResolution(None, forbidden_note(name, source), tuple(tried))
    family = stored_family(name, embeddable, directory, source)
    shutil.rmtree(directory / DOWNLOADS_DIRECTORY, ignore_errors=True)
    return FontResolution(RequestedFont(family, source), None, tuple(tried))


def stored_family(name: str, faces: list[FontFile], directory: pathlib.Path, source: FontSource) -> BundledFamily:
    directory.mkdir(parents=True, exist_ok=True)
    by_weight: dict[int, FontFile] = {}
    for face in sorted(faces, key=lambda candidate: candidate.path.name):
        by_weight.setdefault(face.weight, face)
    stored = []
    for weight, face in sorted(by_weight.items()):
        target = directory / f"{slug_of(name)}-{weight}{face.path.suffix.casefold()}"
        if face.path.resolve() != target.resolve():
            shutil.copyfile(face.path, target)
        stored.append(BundledFace(weight, target.name))
    (directory / META_FILE).write_text(json.dumps({"family": name, **source.to_json()}), encoding="utf-8")
    return BundledFamily(name, str(directory), DECK, tuple(stored))


def download_from_google_fonts(name: str, directory: pathlib.Path, fetch: Fetcher) -> tuple[list[FontFile], FontSource] | None:
    slug = slug_of(name)
    for license_directory, license_name in GOOGLE_FONT_DIRECTORIES.items():
        try:
            listing = json.loads(fetch(GOOGLE_LISTING_URL.format(directory=license_directory, slug=slug)))
        except (urllib.error.URLError, ValueError, OSError):
            continue
        entries = [entry for entry in listing if isinstance(entry, dict) and str(entry.get("name", "")).casefold().endswith(".ttf") and entry.get("download_url")]
        verified = verified_downloads(name, entries, directory, fetch)
        if verified:
            return verified, FontSource(WEB_SOURCE, entries[0]["download_url"], license_name)
    return None


def verified_downloads(name: str, entries: list[dict], directory: pathlib.Path, fetch: Fetcher) -> list[FontFile]:
    incoming = directory / DOWNLOADS_DIRECTORY
    incoming.mkdir(parents=True, exist_ok=True)
    verified = []
    for entry in entries:
        try:
            content = fetch(entry["download_url"])
        except (urllib.error.URLError, ValueError, OSError):
            continue
        for path, content in downloaded_faces(incoming, entry["name"], content):
            path.write_bytes(content)
            read = read_font_file(path)
            if read is not None and read.is_named(name) and not read.is_italic and read.weight in WANTED_WEIGHTS:
                verified.append(read)
            else:
                path.unlink(missing_ok=True)
    return verified


def downloaded_faces(incoming: pathlib.Path, file_name: str, content: bytes) -> list[tuple[pathlib.Path, bytes]]:
    if "[" not in file_name:
        return [(incoming / file_name, content)]
    return [(incoming / f"{pathlib.Path(file_name).stem.split('[')[0]}-{weight}.ttf", instance_of(content, weight)) for weight in WANTED_WEIGHTS]


def instance_of(content: bytes, weight: int) -> bytes:
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer

    font = TTFont(io.BytesIO(content))
    instanced = instancer.instantiateVariableFont(font, {"wght": weight}, updateFontNames=False)
    instanced["OS/2"].usWeightClass = weight
    buffer = io.BytesIO()
    instanced.save(buffer)
    return buffer.getvalue()


def unavailable_note(name: str, tried: list[str]) -> str:
    return (
        f"The font {name} you asked for was not available: no attached file, data-room font or bundled font is named {name}, and it is not on Google Fonts. "
        f"I tried {', '.join(tried)}. The deck is set in Paperlogy. Attach the {name} font file and I will rebuild the same deck with it."
    )


def forbidden_note(name: str, source: FontSource) -> str:
    where = f" at {source.url}" if source.url else ""
    return f"The font {name} was found{where}, but its license flags do not allow embedding it in a PowerPoint file, so the deck is set in Paperlogy. Attach a copy that allows embedding and I will rebuild the same deck with it."
