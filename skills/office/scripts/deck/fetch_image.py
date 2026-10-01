#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import sys
import urllib.parse
import urllib.request

from deck_definitions import IMAGE_SEARCH_FAILED, NO_IMAGE_FOUND
from office_result import OfficeArgumentParser, OfficeFailure, Result, run_command

OPENVERSE_ENDPOINT = "https://api.openverse.org/v1/images/"
SAFE_LICENSES = "cc0,pdm"
MAXIMUM_BYTES = 3_500_000
USER_AGENT = "internkim-skill-image/1.0 (prototype image sourcing)"
STRICT_FILTERS = {"aspect_ratio": "wide", "size": "large", "extension": "jpg"}
RELAXED_FILTER_SETS = (STRICT_FILTERS, {"extension": "jpg"}, {})


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


def download(url: str, output_path: pathlib.Path) -> int:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(MAXIMUM_BYTES + 1)
    if len(data) > MAXIMUM_BYTES:
        return 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)
    return len(data)


def parse_arguments(arguments: list[str]) -> tuple[str, str]:
    parser = OfficeArgumentParser(description="Download one public-domain (CC0 or PDM) photo that matches an English search query, and report its size, ratio and source page.")
    parser.add_argument("query", help="a concrete English scene, such as \"harbor cranes at dawn\"; one or two words find more")
    parser.add_argument("output", nargs="?", help="where to save the photo, such as images/harbor.jpg")
    parser.add_argument("--output", "-o", dest="output_option", help="the same as the second argument")
    parsed = parser.parse_args(arguments)
    output = parsed.output_option or parsed.output
    if not output:
        parser.error("give the output path as the second argument or --output")
    return parsed.query, output


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
    query, output_value = parse_arguments(sys.argv[1:])
    output_path = anchor_site_output(output_value)
    try:
        results = search_openverse(query)
    except (OSError, ValueError) as error:
        raise OfficeFailure(IMAGE_SEARCH_FAILED.issue(f"image search failed: {error}")) from error
    for result in results:
        saved = try_download(result, output_path)
        if saved:
            return saved
    raise OfficeFailure(NO_IMAGE_FOUND.issue(f"no usable cc0/public-domain image found for {query!r}"))


def try_download(result: dict, output_path: pathlib.Path) -> Result | None:
    image_url = result.get("url") or ""
    if not image_url:
        return None
    try:
        written = download(image_url, output_path)
    except (OSError, ValueError):
        return None
    if not written:
        return None
    title = result.get("title") or "untitled"
    creator = result.get("creator") or "unknown"
    license_name = str(result.get("license", "?")).upper()
    width, height = result.get("width"), result.get("height")
    ratio = f"{width / height:.2f}" if width and height else "unknown"
    return Result(
        summary=f"saved {output_path} ({written // 1024}KB, ratio {ratio}), \"{title}\" by {creator}, license {license_name}; look at it before using it, and reference it as {reference_path(output_path)}",
        output_path=str(output_path),
        details={
            "title": title,
            "creator": creator,
            "license": license_name,
            "sourceUrl": result.get("foreign_landing_url"),
            "width": width,
            "height": height,
            "aspectRatio": ratio,
            "referencePath": reference_path(output_path),
            "bytes": written,
        },
    )


if __name__ == "__main__":
    raise SystemExit(run_command(main))
