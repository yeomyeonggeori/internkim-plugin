#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path
from typing import Any


IDENTITY_FIELDS = ("name", "version", "description", "license", "repository", "keywords")
SUPPORTED_MCP_TRANSPORT = "streamable-http"
CLAUDE_MCP_TRANSPORT = "http"


class ManifestError(ValueError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ManifestError(f"cannot read JSON manifest {path}: {error}") from error
    if not isinstance(value, dict):
        raise ManifestError(f"manifest {path} must be a JSON object")
    return value


def require_string(document: dict[str, Any], field: str, source: Path) -> str:
    value = document.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{source}: {field} must be a non-empty string")
    return value


def identity_manifest(source: dict[str, Any], source_path: Path) -> dict[str, Any]:
    identity = {field: source.get(field) for field in IDENTITY_FIELDS}
    for field in IDENTITY_FIELDS:
        if field == "keywords":
            if not isinstance(identity[field], list) or not all(
                isinstance(keyword, str) for keyword in identity[field]
            ):
                raise ManifestError(f"{source_path}: keywords must be an array of strings")
            continue
        require_string(source, field, source_path)
    return identity


def claude_mcp_manifest(source: dict[str, Any], source_path: Path) -> dict[str, Any]:
    servers = source.get("mcpServers")
    if not isinstance(servers, dict) or not servers:
        raise ManifestError(f"{source_path}: mcpServers must be a non-empty object")
    converted: dict[str, Any] = {}
    for name, configuration in servers.items():
        if not isinstance(name, str) or not name:
            raise ManifestError(f"{source_path}: MCP server names must be non-empty strings")
        if not isinstance(configuration, dict):
            raise ManifestError(f"{source_path}: MCP server {name} must be an object")
        transport = configuration.get("type")
        if transport != SUPPORTED_MCP_TRANSPORT:
            raise ManifestError(
                f"{source_path}: MCP server {name} uses unsupported transport {transport!r}; "
                f"only {SUPPORTED_MCP_TRANSPORT!r} converts to {CLAUDE_MCP_TRANSPORT!r}"
            )
        unsupported_fields = configuration.keys() - {"type", "url"}
        if unsupported_fields:
            raise ManifestError(
                f"{source_path}: MCP server {name} has unsupported fields: "
                f"{', '.join(sorted(unsupported_fields))}"
            )
        url = require_string(configuration, "url", source_path)
        converted[name] = {"type": CLAUDE_MCP_TRANSPORT, "url": url}
    return {"mcpServers": converted}


def pi_package_manifest(source_path: Path, identity: dict[str, Any]) -> dict[str, Any]:
    package = read_json(source_path)
    for field in ("scripts", "dependencies", "devDependencies"):
        value = package.get(field)
        if not isinstance(value, dict) or not all(
            isinstance(key, str) and isinstance(item, str) for key, item in value.items()
        ):
            raise ManifestError(f"{source_path}: {field} must be an object of strings")
    package_manifest = dict(identity)
    private = package.get("private")
    if not isinstance(private, bool):
        raise ManifestError(f"{source_path}: private must be a boolean")
    package_manifest.update(
        {
            "type": package.get("type", "module"),
            "private": private,
            "scripts": package["scripts"],
            "dependencies": package["dependencies"],
            "devDependencies": package["devDependencies"],
            "pi": {"skills": ["./skills"], "extensions": ["./adapters/pi/index.ts"]},
        }
    )
    if not isinstance(package_manifest["type"], str):
        raise ManifestError(f"{source_path}: type must be a string")
    return package_manifest


def serialized(document: dict[str, Any]) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def generated_manifests(source_root: Path) -> dict[Path, str]:
    plugin_path = source_root / "plugin.json"
    mcp_path = source_root / "mcp.json"
    pi_package_path = source_root / "adapters" / "pi" / "package.json"
    plugin = identity_manifest(read_json(plugin_path), plugin_path)
    mcp = claude_mcp_manifest(read_json(mcp_path), mcp_path)
    pi_package = pi_package_manifest(pi_package_path, plugin)
    return {
        source_root / ".claude-plugin" / "plugin.json": serialized(plugin),
        source_root / ".mcp.json": serialized(mcp),
        source_root / "package.json": serialized(pi_package),
    }


def write_or_check(source_root: Path, check: bool) -> bool:
    expected = generated_manifests(source_root)
    drifted: list[Path] = []
    for path, content in expected.items():
        if check:
            if not path.is_file() or path.read_text() != content:
                drifted.append(path)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    if drifted:
        for path in drifted:
            print(f"generated manifest is missing or out of date: {path}", file=sys.stderr)
        return False
    return True


def main(arguments: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Generate Claude and Pi client manifests from the canonical plugin manifests."
    )
    parser.add_argument(
        "--check", action="store_true", help="fail when generated files differ from canonical manifests"
    )
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    options = parser.parse_args(arguments)
    try:
        return 0 if write_or_check(options.source_root, options.check) else 1
    except ManifestError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
