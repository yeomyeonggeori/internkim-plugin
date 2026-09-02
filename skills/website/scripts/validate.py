#!/usr/bin/env python3
import hashlib
import json
import pathlib
import re
import sys

FRONT_MATTER_REQUIRED_KEY_ORDER = ["colors", "typography", "rounded", "spacing", "components"]
REBUILD_EXEMPT_DIRECTORY_NAMES = {"dist", "node_modules", ".internkim"}


def front_matter_failures(design_text: str) -> list:
    if not design_text.startswith("---\n"):
        return ["DESIGN.md must start with YAML front matter (---)"]
    front_matter_end = design_text.find("\n---", 4)
    if front_matter_end < 0:
        return ["DESIGN.md front matter must end with ---"]
    front_matter = design_text[4:front_matter_end]
    failures = []
    key_positions = []
    for key in FRONT_MATTER_REQUIRED_KEY_ORDER:
        match = re.search(rf"(?m)^{key}\s*:", front_matter)
        if match is None:
            failures.append(f"DESIGN.md front matter is missing required key: {key}")
        else:
            key_positions.append((key, match.start()))
    for (key, position), (previous_key, previous_position) in zip(key_positions[1:], key_positions):
        if position < previous_position:
            failures.append(f"DESIGN.md front matter key order is wrong: {key} must come after {previous_key}")
    return failures


def design_failures(source_root: pathlib.Path) -> list:
    design_path = source_root / "DESIGN.md"
    if not design_path.exists():
        return [f"{design_path} not found; the scaffold creates it at the project root"]
    design_text = design_path.read_text(encoding="utf-8")
    failures = front_matter_failures(design_text)
    if "TODO(design)" in design_text:
        failures.append("DESIGN.md still contains the TODO(design) marker; decide the design and delete the marker")
    return failures


def rebuild_relevant_source_files(app_directory: pathlib.Path):
    for path in app_directory.rglob("*"):
        if not path.is_file():
            continue
        relative_parts = path.relative_to(app_directory).parts
        if relative_parts[0] == "public" or REBUILD_EXEMPT_DIRECTORY_NAMES.intersection(relative_parts):
            continue
        yield path


def matches_scaffold_manifest(source_root: pathlib.Path) -> bool:
    manifest_path = source_root / ".internkim" / "scaffold-app-manifest.json"
    if not manifest_path.exists():
        return False
    try:
        recorded = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    app_directory = source_root / "app"
    current = {}
    for path in rebuild_relevant_source_files(app_directory):
        relative = path.relative_to(app_directory)
        current["app/" + "/".join(relative.parts)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return current == recorded


def content_failures(source_root: pathlib.Path) -> list:
    content_path = source_root / "app" / "public" / "site-content.json"
    if not content_path.exists():
        return [f"{content_path} not found; the scaffold creates it and all site text lives there"]
    try:
        content = json.loads(content_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [f"site-content.json is not valid JSON: {error}"]
    if not str(content.get("siteName") or "").strip():
        return ["site-content.json must keep a non-empty siteName"]
    return []


def dist_failures(source_root: pathlib.Path) -> list:
    if matches_scaffold_manifest(source_root):
        return []
    app_directory = source_root / "app"
    dist_directory = app_directory / "dist"
    if not dist_directory.is_dir() or not any(dist_directory.iterdir()):
        return [f"{dist_directory} is missing or empty; run build.sh before serving"]
    newest_dist_time = max(path.stat().st_mtime for path in dist_directory.rglob("*") if path.is_file())
    stale_sources = [
        path for path in rebuild_relevant_source_files(app_directory)
        if path.stat().st_mtime > newest_dist_time
    ]
    if stale_sources:
        newest_source = max(stale_sources, key=lambda path: path.stat().st_mtime)
        return [f"app/dist is stale: {newest_source.relative_to(source_root)} changed after the last build; run build.sh again"]
    return []


def build_quality_failures(source_root: pathlib.Path) -> list:
    quality_path = source_root / ".internkim" / "build-quality.json"
    if not quality_path.exists():
        if matches_scaffold_manifest(source_root):
            return []
        return [f"{quality_path} not found; run build.sh so the scaffold records its quality verdict"]
    try:
        quality = json.loads(quality_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [f"build-quality.json is not valid JSON: {error}"]
    blocking_issues = [issue for issue in quality.get("issues") or [] if issue.get("severity") == "blocking"]
    return [
        f"build-quality blocking issue at {issue.get('target')}: {issue.get('message')} Fix: {issue.get('suggestedFix')}"
        for issue in blocking_issues
    ]


def main() -> int:
    arguments = [value for value in sys.argv[1:] if value != "--structure-unchanged"]
    if len(arguments) != 1:
        print("usage: validate.py [--structure-unchanged] <project-root>")
        return 2
    if "--structure-unchanged" in sys.argv:
        return 0 if matches_scaffold_manifest(pathlib.Path(arguments[0])) else 1
    source_root = pathlib.Path(arguments[0])
    if not (source_root / "app").is_dir():
        print(f"Error: {source_root}/app not found; pass the site project root created by scaffold.sh.")
        return 2
    failures = design_failures(source_root) + content_failures(source_root) + dist_failures(source_root) + build_quality_failures(source_root)
    if failures:
        print(f"Pre-serve validation FAILED for {source_root}. Fix these before site_serve:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"Pre-serve validation PASSED for {source_root}: DESIGN.md contract, fresh app/dist, and build quality all check out.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
