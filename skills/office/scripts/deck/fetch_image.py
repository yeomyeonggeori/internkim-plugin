#!/usr/bin/env python3
import json
import pathlib
import sys
import urllib.parse
import urllib.request

from deck_definitions import IMAGE_SEARCH_FAILED, NO_IMAGE_FOUND
from office_result import INVALID_ARGUMENTS, OfficeFailure, Result, run_command

OPENVERSE_ENDPOINT = "https://api.openverse.org/v1/images/"
SAFE_LICENSES = "cc0,pdm"
MAXIMUM_BYTES = 3_500_000
USER_AGENT = "internkim-skill-image/1.0 (prototype image sourcing)"


def search_openverse(query: str) -> list:
    parameters = urllib.parse.urlencode({
        "q": query,
        "license": SAFE_LICENSES,
        "page_size": 10,
        "aspect_ratio": "wide",
        "size": "large",
        "category": "photograph",
        "extension": "jpg",
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


def parse_arguments(argv: list) -> tuple:
    values = []
    output_from_flag = None
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument in ("--output", "-o") and index + 1 < len(argv):
            output_from_flag = argv[index + 1]
            index += 2
            continue
        if argument.startswith("--output="):
            output_from_flag = argument.split("=", 1)[1]
            index += 1
            continue
        values.append(argument)
        index += 1
    query = values[0] if values else ""
    output_value = output_from_flag or (values[1] if len(values) > 1 else "")
    return query, output_value


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
    return output_path.name


def main() -> Result:
    query, output_value = parse_arguments(sys.argv[1:])
    if not query or not output_value:
        raise OfficeFailure(INVALID_ARGUMENTS.issue("usage: office deck image <search query> <output path>   (also accepts --output <path>)"))
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
    return Result(
        summary=f"saved {output_path} ({written // 1024}KB), \"{title}\" by {creator}, license {license_name} (no attribution required); reference it as {reference_path(output_path)}",
        output_path=str(output_path),
        details={"title": title, "creator": creator, "license": license_name, "referencePath": reference_path(output_path), "bytes": written},
    )


if __name__ == "__main__":
    raise SystemExit(run_command(main))
