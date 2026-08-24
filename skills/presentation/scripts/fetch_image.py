#!/usr/bin/env python3
import json
import pathlib
import sys
import urllib.parse
import urllib.request

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


def main() -> int:
    query, output_value = parse_arguments(sys.argv[1:])
    if not query or not output_value:
        print("usage: fetch_image.py <search query> <output path>   (also accepts --output <path>)")
        return 2
    output_path = anchor_site_output(output_value)
    try:
        results = search_openverse(query)
    except Exception as error:
        print(f"image search failed: {error}; skip imagery or try a simpler English query")
        return 1
    for result in results:
        image_url = result.get("url") or ""
        if not image_url:
            continue
        try:
            written = download(image_url, output_path)
        except Exception:
            continue
        if written:
            title = result.get("title") or "untitled"
            creator = result.get("creator") or "unknown"
            print(f"saved {output_path} ({written // 1024}KB) — \"{title}\" by {creator}, license {result.get('license', '?').upper()} (no attribution required)")
            print(f"reference it as {reference_path(output_path)}")
            return 0
    print(f"no usable cc0/public-domain image found for {query!r}; try a simpler English query or skip imagery")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
