import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server" / "mcp_server.py"


class McpServerTests(unittest.TestCase):
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
                "proposed_name": "Demo", "started_at": "2026-01-01", "last_event_at": "2026-01-02",
                "project": "Demo project", "topic": "Testing", "confidence": "high",
                "value": "high", "summary": "Safe summary", "open_tasks": "Review",
            })
        with (audit / "actions.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["record_id", "recommended_action"])
            writer.writeheader()
            writer.writerow({"record_id": "one", "recommended_action": "keep_and_tag"})

    def tearDown(self):
        self.temp.cleanup()

    def run_server(self, requests):
        env = os.environ.copy()
        env["CODEX_HISTORY_AUDIT_DIR"] = self.temp.name
        payload = "\n".join(json.dumps(request) for request in requests) + "\n"
        return subprocess.run(
            [sys.executable, str(SERVER)],
            input=payload,
            text=True,
            capture_output=True,
            env=env,
            cwd=ROOT,
            check=False,
        )

    def test_initialize_and_tools_list(self):
        result = self.run_server([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        responses = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(responses[0]["result"]["serverInfo"]["name"], "codex-history-organizer")
        self.assertEqual({tool["name"] for tool in responses[1]["result"]["tools"]}, {
            "history_overview", "search_history", "get_project_summary"
        })
        self.assertEqual(result.stderr, "")

    def test_tools_are_read_only_and_return_structured_data(self):
        result = self.run_server([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "history_overview"}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
                "name": "search_history", "arguments": {"query": "demo"}
            }},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
                "name": "get_project_summary", "arguments": {"project": "Demo project"}
            }},
        ])
        responses = [json.loads(line) for line in result.stdout.splitlines()]
        overview = responses[0]["result"]["structuredContent"]
        search = responses[1]["result"]["structuredContent"]
        summary = responses[2]["result"]["structuredContent"]
        self.assertEqual(overview["sessions"], 1)
        self.assertTrue(overview["read_only"])
        self.assertEqual(len(search["sessions"]), 1)
        self.assertTrue(summary["read_only"])

    def test_unknown_tool_and_invalid_argument_return_errors(self):
        result = self.run_server([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "write_history"}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
                "name": "get_project_summary", "arguments": {}
            }},
        ])
        responses = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(responses[0]["error"]["code"], -32601)
        self.assertEqual(responses[1]["error"]["code"], -32602)


if __name__ == "__main__":
    unittest.main()
