#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
import io
import json
import pathlib
import sys
import urllib.parse
import urllib.request

from PIL import Image, UnidentifiedImageError

from deck.deck_definitions import IMAGE_SEARCH_FAILED, NO_IMAGE_FOUND
from core.office_outputs import require_output_extension
from core.office_result import OfficeArgumentParser, OfficeFailure, Result, run_command
from core.text_script import has_hangul

OPENVERSE_ENDPOINT = "https://api.openverse.org/v1/images/"
SAFE_LICENSES = "cc0,pdm"
MAXIMUM_BYTES = 8_000_000
USER_AGENT = "internkim-skill-image/1.0 (prototype image sourcing)"
STRICT_FILTERS = {"aspect_ratio": "wide", "size": "large", "extension": "jpg"}
RELAXED_FILTER_SETS = (STRICT_FILTERS, {"extension": "jpg"}, {})
DEFAULT_CANDIDATE_COUNT = 3
SMALLEST_USEFUL_WIDTH = 640
SAVE_FORMATS = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}


@dataclass(frozen=True)
class Candidate:
    path: pathlib.Path
    width: int
    height: int
    written: int
    result: dict

    def to_json(self) -> dict:
        return {
            "path": str(self.path),
            "referencePath": reference_path(self.path),
            "width": self.width,
            "height": self.height,
            "aspectRatio": round(self.width / self.height, 2),
            "license": str(self.result.get("license", "")).upper(),
            "creator": self.result.get("creator"),
            "title": self.result.get("title"),
            "sourceUrl": self.result.get("foreign_landing_url"),
            "bytes": self.written,
        }


def search_openverse(query: str) -> list:
    for filters in RELAXED_FILTER_SETS:
        results = search_openverse_with(query, filters)
        if results:
            return results
    return []


def search_openverse_with(query: str, filters: dict[str, str]) -> list:
    parameters = urllib.parse.urlencode({
        "q": query,
        "license": SAFE_LICENSES,
        "page_size": 10,
        "category": "photograph",
        **filters,
    })
    request = urllib.request.Request(OPENVERSE_ENDPOINT + "?" + parameters, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response).get("results", [])


def download(url: str) -> bytes | None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(MAXIMUM_BYTES + 1)
    return data if len(data) <= MAXIMUM_BYTES else None


def save_as(data: bytes, output_path: pathlib.Path) -> tuple[int, int, int] | None:
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError):
        return None
    if image.width < SMALLEST_USEFUL_WIDTH:
        return None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_format = SAVE_FORMATS[output_path.suffix.casefold()]
    if save_format == "JPEG" and image.mode != "RGB":
        image = image.convert("RGB")
    image.save(output_path, save_format, **({"quality": 90} if save_format == "JPEG" else {}))
    return image.width, image.height, output_path.stat().st_size


def parse_arguments(arguments: list[str]) -> tuple[str, str, int]:
    parser = OfficeArgumentParser()
    parser.add_argument("query", help="a concrete English scene, such as \"harbor cranes at dawn\"; one or two words find more")
    parser.add_argument("output", nargs="?", help="where to save the photo, such as images/harbor.jpg")
    parser.add_argument("--output", "-o", dest="output_option", help="the same as the second argument")
    parser.add_argument("--count", type=int, default=DEFAULT_CANDIDATE_COUNT, help=f"how many candidates to save (default {DEFAULT_CANDIDATE_COUNT})")
    parsed = parser.parse_args(arguments)
    output = parsed.output_option or parsed.output
    if not output:
        parser.error("give the output path as the second argument or --output")
    require_output_extension(output, tuple(SAVE_FORMATS))
    return parsed.query, output, max(1, parsed.count)


def anchor_site_output(output_value: str) -> pathlib.Path:
    output_path = pathlib.Path(output_value)
    as_posix = output_path.as_posix()
    if "app/public/" not in as_posix:
        return output_path
    suffix = as_posix.split("app/public/", 1)[-1]
    probe = pathlib.Path.cwd()
    for _ in range(6):
        if probe.name == "app" and (probe / "public").is_dir():
            return probe / "public" / suffix
        if (probe / "app" / "public").is_dir():
            return probe / "app" / "public" / suffix
        probe = probe.parent
    return output_path


def reference_path(output_path: pathlib.Path) -> str:
    as_posix = output_path.as_posix()
    if "public/" in as_posix:
        return "/" + as_posix.split("public/", 1)[-1]
    return as_posix


def main() -> Result:
    query, output_value, count = parse_arguments(sys.argv[1:])
    output_path = anchor_site_output(output_value)
    try:
        results = search_openverse(query)
    except (OSError, ValueError) as error:
        raise OfficeFailure(IMAGE_SEARCH_FAILED.issue(f"image search failed: {error}")) from error
    candidates = save_candidates(results, output_path, count)
    if not candidates:
        raise OfficeFailure(no_image_issue(query))
    listed = "; ".join(f"{candidate.path.name} {candidate.width}x{candidate.height}" for candidate in candidates)
    return Result(
        summary=f"saved {len(candidates)} candidates for {query!r}: {listed}; look at each, keep the one that shows the slide's subject, delete the others, and name its source in .source",
        output_path=str(candidates[0].path),
        details={"candidates": [candidate.to_json() for candidate in candidates]},
    )


def no_image_issue(query: str):
    if has_hangul(query):
        return NO_IMAGE_FOUND.issue(f"nothing matched {query!r}; the photo index searches English titles and tags", suggestion="write the query as a concrete English scene, such as \"convenience store shelves\"")
    return NO_IMAGE_FOUND.issue(f"no usable cc0/public-domain image found for {query!r}")


def candidate_path(output_path: pathlib.Path, position: int) -> pathlib.Path:
    if position == 1:
        return output_path
    return output_path.with_name(f"{output_path.stem}-{position}{output_path.suffix}")


def save_candidates(results: list, output_path: pathlib.Path, count: int) -> list[Candidate]:
    candidates = []
    for result in results:
        if len(candidates) == count:
            break
        candidate = try_download(result, candidate_path(output_path, len(candidates) + 1))
        if candidate:
            candidates.append(candidate)
    return candidates


def try_download(result: dict, path: pathlib.Path) -> Candidate | None:
    image_url = result.get("url") or ""
    if not image_url:
        return None
    try:
        data = download(image_url)
    except (OSError, ValueError):
        return None
    saved = save_as(data, path) if data else None
    if saved is None:
        return None
    width, height, written = saved
    return Candidate(path, width, height, written, result)


if __name__ == "__main__":
    raise SystemExit(run_command(main))
