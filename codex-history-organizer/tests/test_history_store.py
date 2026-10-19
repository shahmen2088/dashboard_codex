import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.history_store import HistoryStore, redact_text


class HistoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        inventory = [
            {
                "record_id": "one",
                "session_meta_id": "chat-one",
                "archive_status": "active",
                "index_thread_name": "Quoted, session",
                "proposed_name": "Generated alternative",
                "started_at": "2026-01-01T00:00:00Z",
                "last_event_at": "2026-01-02T00:00:00Z",
                "project": "Demo project",
                "topic": "Testing",
                "confidence": "high",
                "value": "high",
                "summary": "A useful summary",
                "open_tasks": "Review the result",
            },
            {
                "record_id": "two",
                "session_meta_id": "chat-two",
                "archive_status": "archived",
                "index_thread_name": "Other",
                "proposed_name": "Other",
                "started_at": "2026-02-01T00:00:00Z",
                "last_event_at": "2026-02-02T00:00:00Z",
                "project": "Other project",
                "topic": "Cleanup",
                "confidence": "medium",
                "value": "normal",
                "summary": "Old session",
                "open_tasks": "Не определено по локальным событиям",
            },
            {
                "record_id": "three",
                "session_meta_id": "chat-one",
                "archive_status": "active",
                "index_thread_name": "Follow-up",
                "proposed_name": "Generated follow-up",
                "started_at": "2026-01-03T00:00:00Z",
                "last_event_at": "2026-01-04T00:00:00Z",
                "project": "Demo project",
                "topic": "Follow-up",
                "confidence": "high",
                "value": "high",
                "summary": "Follow-up in the same chat",
                "open_tasks": "",
            },
        ]
        with (self.root / "inventory.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=inventory[0].keys())
            writer.writeheader()
            writer.writerows(inventory)
        with (self.root / "actions.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["record_id", "recommended_action"])
            writer.writeheader()
            writer.writerow({"record_id": "one", "recommended_action": "keep_and_tag"})
            writer.writerow({"record_id": "two", "recommended_action": "archive_candidate"})
        (self.root / "project_summaries").mkdir()
        (self.root / "project_summaries" / "demo-project.md").write_text(
            "## Demo project\n- A safe highlight\n", encoding="utf-8"
        )
        (self.root / "refresh_status.json").write_text(
            '{"state":"ok","last_success_at":"2026-01-02T00:00:00+03:00","sessions":3}',
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_overview_and_filters(self):
        store = HistoryStore(self.root)
        overview = store.overview()
        self.assertEqual(overview["sessions"], 3)
        self.assertEqual(overview["groups"], 2)
        self.assertTrue(overview["read_only"])
        self.assertTrue(overview["last_updated"])
        self.assertEqual(store.status()["state"], "ok")
        self.assertEqual(store.status()["sessions"], 3)
        self.assertEqual(len(store.list_sessions(query="quoted")), 1)
        self.assertEqual(len(store.list_sessions(query="safe highlight")), 2)
        self.assertEqual(len(store.list_sessions(value="normal")), 1)

    def test_list_chats_groups_rollouts_and_returns_locator(self):
        store = HistoryStore(self.root)
        chats = store.list_chats()
        self.assertEqual(len(chats), 2)
        demo = next(chat for chat in chats if chat["project"] == "Demo project")
        self.assertEqual(demo["sessions"], 2)
        self.assertEqual(demo["title"], "Follow-up")
        self.assertEqual(demo["chat_url"], "")
        self.assertIn("Follow-up", demo["chat_locator"])
        self.assertIn("Demo project", demo["chat_locator"])
        self.assertEqual(len(store.list_chats(query="safe highlight")), 1)

    def test_csv_quotes_unicode_and_project_summary(self):
        store = HistoryStore(self.root)
        row = next(row for row in store.list_sessions() if row["name"] == "Other")
        self.assertEqual(row["name"], "Other")
        summary = store.project_summary("Demo project")
        self.assertEqual(summary["sessions"], 2)
        self.assertIn("A safe highlight", summary["description"])
        self.assertIn("A safe highlight", " ".join(summary["highlights"]))
        self.assertNotIn("Record ID", " ".join(summary["highlights"]))

    def test_secret_and_path_redaction(self):
        text = "token=sk-abcdefghijklmnop Bearer abc C:\\Users\\name\\file.txt [LOCAL_PATH:demo.zip] chatgpt-conversation://demo"
        result = redact_text(text)
        self.assertNotIn("sk-abcdefghijklmnop", result)
        self.assertNotIn("abc", result)
        self.assertNotIn("C:\\Users", result)
        self.assertNotIn("LOCAL_PATH:", result)
        self.assertNotIn("chatgpt-conversation://", result)

    def test_missing_files_are_empty_and_safe(self):
        empty = Path(self.temp.name) / "empty"
        empty.mkdir()
        store = HistoryStore(empty)
        self.assertEqual(store.overview()["sessions"], 0)
        self.assertEqual(store.overview()["last_updated"], "")
        self.assertEqual(store.list_sessions(), [])


if __name__ == "__main__":
    unittest.main()
