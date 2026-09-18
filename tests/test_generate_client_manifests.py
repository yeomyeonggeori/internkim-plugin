import json
import tempfile
import unittest
from pathlib import Path

from scripts.generate_client_manifests import ManifestError, generated_manifests, main, write_or_check


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value))


class GenerateClientManifestsTest(unittest.TestCase):
    def source(self, plugin: object | None = None, mcp: object | None = None) -> Path:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        directory = Path(temporary_directory.name)
        write_json(
            directory / "plugin.json",
            plugin
            or {
                "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
                "name": "fixture",
                "version": "1.2.3",
                "description": "Fixture plugin",
                "license": "Apache-2.0",
                "repository": "https://example.com/fixture",
                "keywords": ["fixture", "mcp"],
            },
        )
        write_json(
            directory / "mcp.json",
            mcp or {"mcpServers": {"fixture": {"type": "streamable-http", "url": "https://example.com/mcp"}}},
        )
        (directory / "adapters" / "pi").mkdir(parents=True)
        write_json(
            directory / "adapters" / "pi" / "package.json",
            {
                "type": "module",
                "private": True,
                "scripts": {"test": "bun test tests/pi"},
                "dependencies": {"fixture-runtime": "1.0.0"},
                "devDependencies": {"fixture-types": "1.0.0"},
            },
        )
        return directory

    def test_generates_identity_without_source_schema(self) -> None:
        source = self.source()
        output = generated_manifests(source)
        identity = json.loads(output[source / ".claude-plugin" / "plugin.json"])
        self.assertEqual(identity["name"], "fixture")
        self.assertNotIn("$schema", identity)

    def test_converts_only_supported_transport(self) -> None:
        source = self.source()
        output = generated_manifests(source)
        mcp = json.loads(output[source / ".mcp.json"])
        self.assertEqual(mcp["mcpServers"]["fixture"]["type"], "http")

    def test_derives_root_pi_package_from_identity_and_adapter_settings(self) -> None:
        source = self.source()
        output = generated_manifests(source)
        package = json.loads(output[source / "package.json"])
        self.assertEqual(package["name"], "fixture")
        self.assertEqual(package["version"], "1.2.3")
        self.assertTrue(package["private"])
        self.assertEqual(package["scripts"], {"test": "bun test tests/pi"})
        self.assertEqual(package["dependencies"], {"fixture-runtime": "1.0.0"})
        self.assertEqual(package["devDependencies"], {"fixture-types": "1.0.0"})
        self.assertEqual(package["pi"], {"skills": ["./skills"], "extensions": ["./adapters/pi/index.ts"]})

    def test_rejects_unsupported_transport(self) -> None:
        source = self.source(
            mcp={"mcpServers": {"fixture": {"type": "stdio", "command": "fixture"}}}
        )
        with self.assertRaisesRegex(ManifestError, "unsupported transport"):
            generated_manifests(source)

    def test_rejects_invalid_identity(self) -> None:
        source = self.source(plugin={"name": "fixture", "version": "1"})
        with self.assertRaisesRegex(ManifestError, "description"):
            generated_manifests(source)

    def test_rejects_unmapped_server_fields_instead_of_discarding_them(self) -> None:
        source = self.source(mcp={"mcpServers": {"fixture": {
            "type": "streamable-http",
            "url": "https://example.com/mcp",
            "headers": {"X-Fixture": "sample"},
        }}})
        with self.assertRaisesRegex(ManifestError, "unsupported fields: headers"):
            generated_manifests(source)

    def test_check_detects_drift_and_accepts_generated_files(self) -> None:
        source = self.source()
        self.assertTrue(write_or_check(source, False))
        self.assertTrue(write_or_check(source, True))
        (source / ".mcp.json").write_text("{}\n")
        self.assertFalse(write_or_check(source, True))

    def test_cli_check_uses_source_root(self) -> None:
        source = self.source()
        self.assertEqual(main(["--source-root", str(source), "--check"]), 1)
        self.assertEqual(main(["--source-root", str(source)]), 0)
        self.assertEqual(main(["--source-root", str(source), "--check"]), 0)


if __name__ == "__main__":
    unittest.main()
