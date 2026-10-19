from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.history_store import HistoryStore


SERVER_INFO = {"name": "codex-history-organizer", "version": "0.1.0"}
PROTOCOL_VERSION = "2024-11-05"

TOOLS = [
    {
        "name": "history_overview",
        "description": "Return a compact, read-only overview of the indexed Codex history.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "search_history",
        "description": "Search redacted indexed session cards by text, project, value, or limit. This tool never changes history.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "group": {"type": "string"},
                "value": {"type": "string", "enum": ["", "high", "normal", "low"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "get_project_summary",
        "description": "Return a redacted summary of one indexed project. This tool is read-only.",
        "inputSchema": {
            "type": "object",
            "properties": {"project": {"type": "string", "minLength": 1}},
            "required": ["project"],
            "additionalProperties": False,
        },
    },
]


def _result(value: Any) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}],
        "structuredContent": value,
    }


def _error(code: int, message: str, request_id: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def dispatch(request: dict[str, Any], store: HistoryStore) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    if request_id is None:
        return None

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
                "instructions": "All history tools are read-only and use only the local CodexChatAudit export.",
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = request.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            if name == "history_overview":
                value = store.overview()
            elif name == "search_history":
                value = {
                    "read_only": True,
                    "sessions": store.list_sessions(
                        query=arguments.get("query", ""),
                        group=arguments.get("group", ""),
                        value=arguments.get("value", ""),
                        limit=arguments.get("limit", 100),
                    ),
                }
            elif name == "get_project_summary":
                project = arguments.get("project", "").strip()
                if not project:
                    return _error(-32602, "project is required", request_id)
                value = store.project_summary(project)
            else:
                return _error(-32601, f"Unknown tool: {name}", request_id)
            return {"jsonrpc": "2.0", "id": request_id, "result": _result(value)}
        except (TypeError, ValueError) as exc:
            return _error(-32602, str(exc), request_id)
    return _error(-32601, f"Unknown method: {method}", request_id)


def main() -> None:
    store = HistoryStore()
    for raw_line in sys.stdin:
        if not raw_line.strip():
            continue
        try:
            request = json.loads(raw_line)
            response = dispatch(request, store)
        except json.JSONDecodeError as exc:
            response = _error(-32700, f"Invalid JSON: {exc.msg}", None)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
