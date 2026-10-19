import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PackageStructureTests(unittest.TestCase):
    def test_manifests_are_valid_and_point_inside_package(self):
        for manifest_path in (ROOT / "plugin.json", ROOT / ".codex-plugin" / "plugin.json"):
            with self.subTest(manifest=manifest_path.name):
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                self.assertEqual(manifest["name"], "codex-history-organizer")
                self.assertTrue(str(manifest["skills"]).startswith("./"))

        mcp = json.loads((ROOT / "mcp.json").read_text(encoding="utf-8"))
        server = mcp["mcpServers"]["codex_history"]
        self.assertEqual(server["type"], "stdio")
        self.assertIn("${PLUGIN_ROOT}", server["args"][0])
        self.assertEqual(server["cwd"], "${PLUGIN_ROOT}")

    def test_required_files_exist(self):
        required = [
            ROOT / "skills" / "codex-history-organizer" / "SKILL.md",
            ROOT / "README.md",
        ]
        for path in required:
            self.assertTrue(path.is_file(), path)

    def test_package_does_not_reference_credential_files(self):
        text_extensions = {".json", ".md", ".py", ".txt"}
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in ROOT.rglob("*")
            if path.is_file()
            and ".git" not in path.parts
            and "tests" not in path.parts
            and path.suffix.lower() in text_extensions
        ).lower()
        self.assertFalse(any(path.name.lower() == "auth.json" for path in ROOT.rglob("*")))
        self.assertNotRegex(text, r"sk-[a-z0-9]{12,}")


if __name__ == "__main__":
    unittest.main()
