import csv
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.parse import quote
from urllib.error import HTTPError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server" / "dashboard_server.py"


class DashboardServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        audit = Path(self.temp.name)
        fields = [
            "record_id", "archive_status", "index_thread_name", "proposed_name",
            "started_at", "last_event_at", "project", "topic", "confidence",
            "value", "summary", "open_tasks",
        ]
        with (audit / "inventory.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerow({
                "record_id": "one", "archive_status": "active", "index_thread_name": "Demo",
                "proposed_name": "Generated project summary", "started_at": "2026-01-01", "last_event_at": "2026-01-02",
                "project": "Demo project", "topic": "Testing", "confidence": "high",
                "value": "high", "summary": "Safe summary", "open_tasks": "Review",
            })
        with (audit / "actions.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["record_id", "recommended_action"])
            writer.writeheader()
            writer.writerow({"record_id": "one", "recommended_action": "keep_and_tag"})

        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        env = os.environ.copy()
        env["CODEX_HISTORY_AUDIT_DIR"] = str(audit)
        env["CODEX_HISTORY_PORT"] = str(self.port)
        self.process = subprocess.Popen(
            [sys.executable, str(SERVER)],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.base = f"http://127.0.0.1:{self.port}"
        for _ in range(30):
            try:
                with urlopen(self.base + "/api/overview", timeout=1):
                    break
            except OSError:
                time.sleep(.05)
        else:
            self.fail("dashboard server did not start")

    def tearDown(self):
        self.process.terminate()
        self.process.wait(timeout=3)
        self.temp.cleanup()

    def get_json(self, path):
        with urlopen(self.base + path, timeout=2) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_static_page_and_json_endpoints(self):
        with urlopen(self.base + "/", timeout=2) as response:
            html = response.read().decode("utf-8")
        self.assertIn("Карта истории Codex", html)
        self.assertEqual(self.get_json("/api/overview")["sessions"], 1)
        self.assertEqual(self.get_json("/api/status")["audit_ready"], True)
        self.assertEqual(len(self.get_json("/api/sessions?q=demo")), 1)
        chats = self.get_json("/api/chats?q=demo")
        self.assertEqual(len(chats), 1)
        self.assertEqual(chats[0]["title"], "Demo")
        self.assertEqual(chats[0]["chat_url"], "")
        self.assertIn("Demo project", chats[0]["chat_locator"])
        project = self.get_json("/api/projects/" + quote("Demo project"))
        self.assertEqual(project["project"], "Demo project")

    def test_unknown_path_is_json_404(self):
        try:
            self.get_json("/not-found")
        except HTTPError as error:
            self.assertEqual(error.code, 404)
            error.close()
        else:
            self.fail("expected HTTP 404")


if __name__ == "__main__":
    unittest.main()
