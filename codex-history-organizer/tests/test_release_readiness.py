import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class ReleaseReadinessTests(unittest.TestCase):
    def test_version_file_matches_manifests(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(version, "0.1.0")
        for manifest_path in (ROOT / "plugin.json", ROOT / ".codex-plugin" / "plugin.json"):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["version"], version)

    def test_demo_store_is_ready_without_personal_export(self):
        from server.history_store import HistoryStore

        store = HistoryStore(ROOT / "demo" / "CodexChatAudit")
        overview = store.overview()
        self.assertEqual(overview["sessions"], 1)
        self.assertEqual(overview["groups"], 1)
        self.assertEqual(store.status()["read_only"], True)
        self.assertEqual(store.list_sessions()[0]["project"], "Demo project")


if __name__ == "__main__":
    unittest.main()
