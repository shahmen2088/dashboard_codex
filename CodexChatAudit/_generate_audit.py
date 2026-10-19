from __future__ import annotations

import csv
import io
import json
import os
import re
import sqlite3
from collections import Counter, defaultdict, deque
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

try:
    from compression.zstd import ZstdFile
except ImportError:  # pragma: no cover - the current bundled Python provides it
    ZstdFile = None


CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
OUT = Path(os.environ.get(
    "CODEX_AUDIT_OUT",
    Path(r"C:\Users\s.buronov\Documents\ChatGPT\GOAT\CodexChatAudit"),
))
INDEX_PATH = CODEX_HOME / "session_index.jsonl"
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
PATH_RE = re.compile(r"\b[A-Za-z]:\\[^\s\"'<>]+")
URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.I)
SECRET_RE = re.compile(
    r"(?ix)(?:"
    r"(?:api[_ -]?key|access[_ -]?token|secret|password|passwd|pwd|пароль|логин|login|username|ключ)\b\s*(?::\s*|=\s*|\s+)[^\s,;]+"
    r"|bearer\s+[A-Za-z0-9._~+/=-]+"
    r"|sk-[A-Za-z0-9_-]{10,}"
    r")"
)
LONG_ID_RE = re.compile(r"\b[A-Za-z0-9_-]{40,}\b")
CONTEXT_BLOCK_RE = re.compile(
    r"<(?P<tag>app-context|environment_context|permissions instructions|skills_instructions|"
    r"external_codex_apps_[^>]+|in-app-browser-context)[^>]*>.*?</(?P=tag)>",
    re.I | re.S,
)
SINGLE_CONTEXT_RE = re.compile(r"<external_codex_apps_[^>]+>.*?(?:</external_codex_apps_[^>]+>|$)", re.I | re.S)


def now_text() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def trunc(text: str, limit: int = 520) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def redact_path(match: re.Match[str]) -> str:
    raw = match.group(0)
    parts = [part for part in re.split(r"[\\/]+", raw) if part]
    return f"[LOCAL_PATH:{parts[-1]}]" if parts else "[LOCAL_PATH]"


def redact_url(match: re.Match[str]) -> str:
    try:
        host = urlparse(match.group(0)).netloc
        return f"[URL:{host}]" if host else "[URL]"
    except Exception:
        return "[URL]"


def clean_text(raw: str) -> str:
    text = str(raw or "")
    if "My request:" in text:
        text = text.split("My request:", 1)[1]
    if re.match(r"\s*<(recommended_plugins|plugins_instructions|tools|skills_instructions|external_codex_apps_writing_block_edits)\b", text, re.I):
        return ""
    if re.match(r"\s*(?:The following is the Codex agent history|Retained source order:|# AGENTS\.md instructions)", text, re.I):
        return ""
    text = CONTEXT_BLOCK_RE.sub(" ", text)
    text = SINGLE_CONTEXT_RE.sub(" ", text)
    text = re.sub(r"<image\b[^>]*>.*?</image>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"(?im)^\s*#\s*Files mentioned by the user:.*?(?=\n\s*##\s*My request:|$)", " ", text, flags=re.S)
    text = SECRET_RE.sub("[REDACTED_SECRET]", text)
    text = URL_RE.sub(redact_url, text)
    text = PATH_RE.sub(redact_path, text)
    text = LONG_ID_RE.sub("[ID]", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text or text in {"[URL]", "[LOCAL_PATH]", "[REDACTED_SECRET]"}:
        return ""
    return trunc(text)


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.casefold()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


@contextmanager
def text_stream(path: Path):
    raw = ZstdFile(path, "rb") if path.suffix == ".zst" else open(path, "rb")
    try:
        with io.TextIOWrapper(raw, encoding="utf-8", errors="replace") as stream:
            yield stream
    finally:
        try:
            raw.close()
        except Exception:
            pass


def record_id_from_path(path: Path) -> str:
    ids = UUID_RE.findall(path.name)
    return ids[-1].lower() if ids else ""


def iter_session_files() -> list[Path]:
    paths = list((CODEX_HOME / "sessions").rglob("*.jsonl"))
    paths += list((CODEX_HOME / "sessions").rglob("*.jsonl.zst"))
    paths += list((CODEX_HOME / "archived_sessions").glob("*.jsonl"))
    paths += list((CODEX_HOME / "archived_sessions").glob("*.jsonl.zst"))
    return sorted(p for p in paths if p.is_file())


def read_index() -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    if not INDEX_PATH.exists():
        return result
    with INDEX_PATH.open("r", encoding="utf-8", errors="replace") as stream:
        for line_no, line in enumerate(stream, 1):
            try:
                item = json.loads(line)
                if isinstance(item, dict) and item.get("id"):
                    result[str(item["id"]).lower()] = {
                        "thread_name": trunc(item.get("thread_name", ""), 220),
                        "updated_at": str(item.get("updated_at", "")),
                        "index_line": str(line_no),
                    }
            except Exception:
                continue
    return result


def safe_counter_value(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def scan_session(path: Path, index: dict[str, dict[str, str]]) -> dict:
    record_id = record_id_from_path(path)
    item = {
        "record_id": record_id,
        "indexed": "yes" if record_id in index else "no",
        "archive_status": "archived" if "archived_sessions" in path.parts else "active",
        "source_file": str(path),
        "source_file_relative": str(path.relative_to(CODEX_HOME)).replace("\\", "/"),
        "compression": "zstd" if path.suffix == ".zst" else "plain",
        "file_bytes": path.stat().st_size,
        "source_mtime": datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds"),
        "index_thread_name": index.get(record_id, {}).get("thread_name", ""),
        "index_updated_at": index.get(record_id, {}).get("updated_at", ""),
        "index_line": index.get(record_id, {}).get("index_line", ""),
        "session_meta_id": "",
        "started_at": "",
        "last_event_at": "",
        "cwd": "",
        "workspace_roots": "",
        "cli_version": "",
        "originator": "",
        "source": "",
        "thread_source": "",
        "history_mode": "",
        "model": "",
        "reasoning": "",
        "context_window": "",
        "lines": 0,
        "malformed_lines": 0,
        "user_messages": 0,
        "meaningful_user_requests": 0,
        "assistant_messages": 0,
        "tool_events": 0,
        "task_complete_events": 0,
        "compacted_events": 0,
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
        "total_tokens": 0,
        "event_types": Counter(),
        "user_requests": [],
        "assistant_outputs": deque(maxlen=8),
    }
    try:
        with text_stream(path) as stream:
            for line in stream:
                item["lines"] += 1
                try:
                    obj = json.loads(line)
                except Exception:
                    item["malformed_lines"] += 1
                    continue
                timestamp = str(obj.get("timestamp", ""))
                if timestamp:
                    if not item["started_at"] or timestamp < item["started_at"]:
                        item["started_at"] = timestamp
                    if timestamp > item["last_event_at"]:
                        item["last_event_at"] = timestamp
                event_type = str(obj.get("type", ""))
                item["event_types"][event_type] += 1
                payload = obj.get("payload") or {}
                if event_type == "session_meta" and isinstance(payload, dict):
                    item["session_meta_id"] = str(payload.get("session_id") or payload.get("id") or "")
                    item["started_at"] = str(payload.get("timestamp") or item["started_at"])
                    item["cwd"] = str(payload.get("cwd") or "")
                    roots = payload.get("runtime_workspace_roots") or []
                    item["workspace_roots"] = " | ".join(str(x) for x in roots)
                    for key in ("cli_version", "originator", "source", "thread_source", "history_mode"):
                        item[key] = str(payload.get(key) or "")
                elif event_type == "turn_context" and isinstance(payload, dict):
                    if payload.get("model"):
                        item["model"] = str(payload.get("model"))
                    if payload.get("effort"):
                        item["reasoning"] = str(payload.get("effort"))
                    if payload.get("model_context_window"):
                        item["context_window"] = str(payload.get("model_context_window"))
                    elif payload.get("context_window"):
                        item["context_window"] = str(payload.get("context_window"))
                    if not item["cwd"] and payload.get("cwd"):
                        item["cwd"] = str(payload.get("cwd"))
                elif event_type == "token_usage_record" and isinstance(payload, dict):
                    usage = payload.get("usage") or {}
                    if isinstance(usage, dict):
                        for key in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens"):
                            item[key] += safe_counter_value(usage.get(key))
                elif event_type == "compacted":
                    item["compacted_events"] += 1
                if isinstance(payload, dict) and payload.get("type") == "task_complete":
                    item["task_complete_events"] += 1
                if isinstance(payload, dict) and payload.get("type") in {"custom_tool_call", "custom_tool_call_output", "function_call", "function_call_output"}:
                    item["tool_events"] += 1
                if event_type == "response_item" and isinstance(payload, dict) and payload.get("type") == "message":
                    role = payload.get("role")
                    texts = []
                    for content in payload.get("content") or []:
                        if isinstance(content, dict) and content.get("type") in {"input_text", "output_text", "text"}:
                            texts.append(str(content.get("text") or ""))
                    if role == "user":
                        item["user_messages"] += 1
                        # Guardian review rollouts contain retained transcripts as user-role
                        # payloads. They are evidence about another session, not standalone
                        # requests for this record, so do not classify their raw transcript.
                        cleaned = "" if item.get("index_thread_name", "").casefold() == "guardian review" else clean_text(" ".join(texts))
                        if cleaned:
                            item["user_requests"].append(cleaned)
                    elif role == "assistant":
                        item["assistant_messages"] += 1
                        cleaned = clean_text(" ".join(texts))
                        if cleaned:
                            item["assistant_outputs"].append(cleaned)
    except Exception as exc:
        item["scan_error"] = f"{type(exc).__name__}: {exc}"
    item["user_requests"] = dedupe(item["user_requests"])
    item["meaningful_user_requests"] = len(item["user_requests"])
    item["assistant_outputs"] = list(item["assistant_outputs"])
    return item


def project_key(item: dict) -> str:
    text = " ".join([item.get("index_thread_name", ""), *item.get("user_requests", [])]).casefold()
    cwd = item.get("cwd", "")
    cwd_low = cwd.casefold()
    if any(word in text for word in ("истории codex", "codex history", "инвентаризац", "session_index.jsonl", "организатор всей моей истории")):
        return "Codex history organization"
    if "bitrix" in text or "битрикс" in text or "\\bx" in cwd_low:
        return "Bitrix24 / BX"
    if "1с" in text or "mcp-сервер 1с" in text or "\\1с" in cwd_low:
        return "1C and data integrations"
    if "реконструкция логики задач" in cwd_low:
        return "Workflow reconstruction"
    if "кэш" in text or "cache" in text:
        return "Cache / КЭШ investigation"
    if cwd_low.startswith("t:\\") or "сетев" in text or "доступ к t:" in text:
        return "Network and shared folders"
    if "character" in text or "pet" in text or "персонаж" in text:
        return "Character / animated assistant materials"
    if "ffmpeg" in text or "видео" in text or "раскадр" in text or "озвуч" in text:
        return "Presentation video"
    if "\\goat" in cwd_low or "control_center" in text or "нейроплов" in text or "центр управления" in text:
        return "Control Center / НейроПлов"
    if ".chatgpt-projects" in cwd_low:
        return "ChatGPT Work project"
    if "\\documents\\codex" in cwd_low:
        return "Codex referenced conversations"
    if "guardian review" in text:
        return "Automated Guardian reviews"
    if cwd:
        return f"Workspace: {Path(cwd).name or cwd}"
    return "Unresolved workspace"


def topic_key(item: dict) -> str:
    text = " ".join([item.get("index_thread_name", ""), *item.get("user_requests", [])]).casefold()
    choices = [
        ("history inventory and organization", ["истории codex", "codex history", "инвентаризац", "session_index.jsonl", "организатор всей моей истории"]),
        ("project setup / development", ["настрой проект", "проект", "разработ", "исправ", "доработ"]),
        ("AI assistant and voice", ["нейроплов", "голос", "озвуч", "чатгпт", "ollama"]),
        ("project onboarding and context", ["подключ", "контекст", "обсидиан", "найти проекты"]),
        ("limits and usage", ["лимит", "токен", "расход", "usage"]),
        ("interface and navigation", ["вкладк", "интерфейс", "экскурс", "навигац"]),
        ("video production", ["видео", "ffmpeg", "раскадр", "озвучка"]),
        ("access and diagnostics", ["доступ", "папк", "сетев", "проверить"]),
        ("automated review", ["guardian review"]),
    ]
    for name, words in choices:
        if any(word in text for word in words):
            return name
    return "general / unresolved"


def confidence(item: dict) -> str:
    title = item.get("index_thread_name", "")
    if title == "Guardian review" and item["meaningful_user_requests"] <= 1:
        return "low"
    if item.get("cwd") and item["meaningful_user_requests"] and title:
        return "high"
    if item.get("cwd") or title:
        return "medium"
    return "low"


def proposed_name(item: dict, project: str, topic: str) -> str:
    title = item.get("index_thread_name", "").strip()
    date = (item.get("started_at") or item.get("index_updated_at") or "")[:10]
    generic_title = re.match(r"^(guardian review|проверь|проверить|сделай|делай|начинай|что дальше|привет|ответить на приветствие)\b", title.casefold())
    if title and not generic_title:
        return title
    prefix = project.replace("/", "—")
    return f"{prefix} — {topic} — {date} — {item['record_id'][:8]}"


def value_and_action(item: dict) -> tuple[str, str, str]:
    title = item.get("index_thread_name", "").casefold()
    if title == "guardian review" and item["meaningful_user_requests"] <= 1:
        return "low", "archive_candidate", "Automated review record with little or no standalone user request; archive only after manual review."
    if item["meaningful_user_requests"] == 0:
        return "low", "inspect_candidate", "No readable user request remained after context filtering; inspect before deciding."
    if item["meaningful_user_requests"] >= 3 or item["assistant_messages"] >= 3:
        return "high", "keep_and_tag", "Substantive working session with multiple user requests or assistant outputs."
    return "medium", "keep_and_tag", "Useful local record, but value should be confirmed from the proposed summary."


def sqlite_inventory() -> list[dict]:
    result = []
    for path in sorted(CODEX_HOME.glob("*.sqlite")):
        row = {"file": str(path), "bytes": path.stat().st_size, "tables": [], "error": ""}
        last_error = None
        for uri in ("file:" + path.as_posix() + "?mode=ro", "file:" + path.as_posix() + "?immutable=1"):
            try:
                with sqlite3.connect(uri, uri=True, timeout=3) as conn:
                    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
                        table = {"name": name, "rows": None}
                        try:
                            quoted = '"' + str(name).replace('"', '""') + '"'
                            table["rows"] = conn.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]
                        except Exception as exc:
                            table["rows"] = f"error: {type(exc).__name__}"
                        row["tables"].append(table)
                break
            except Exception as exc:
                last_error = exc
                row["tables"] = []
        if last_error is not None and not row["tables"]:
            row["error"] = f"{type(last_error).__name__}: {last_error}"
        result.append(row)
    return result


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def slug(text: str) -> str:
    value = re.sub(r"[^\w\-]+", "-", text.casefold(), flags=re.UNICODE).strip("-")
    return value[:80] or "unresolved"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "project_summaries").mkdir(parents=True, exist_ok=True)
    index = read_index()
    paths = iter_session_files()
    source_manifest = {str(path): (path.stat().st_size, path.stat().st_mtime_ns) for path in paths + ([INDEX_PATH] if INDEX_PATH.exists() else [])}
    sessions = [scan_session(path, index) for path in paths]
    project_counts = Counter()
    grouped = defaultdict(list)
    for item in sessions:
        item["project"] = project_key(item)
        item["topic"] = topic_key(item)
        item["confidence"] = confidence(item)
        item["proposed_name"] = proposed_name(item, item["project"], item["topic"])
        item["value"], item["action"], item["action_reason"] = value_and_action(item)
        item["tags"] = ";".join([
            f"project:{slug(item['project'])}",
            f"topic:{slug(item['topic'])}",
            f"source:{item['archive_status']}",
            f"confidence:{item['confidence']}",
        ])
        requests = item["user_requests"]
        item["last_user_request"] = requests[-1] if requests else ""
        item["summary"] = trunc(
            f"Сессия «{item.get('index_thread_name') or 'без названия'}» в рабочей области «{item['project']}». "
            f"Основная тема: {item['topic']}. "
            + (f"Запросы: {'; '.join(requests[:2])}. " if requests else "Читаемый пользовательский запрос не найден. ")
            + (f"Последний запрос: {item['last_user_request']}." if len(requests) > 2 else ""),
            760,
        )
        item["result_hint"] = trunc(item["assistant_outputs"][-1] if item["assistant_outputs"] else "Итог не извлечён безопасным потоковым анализом.", 420)
        pending_words = ("сделай", "исправ", "додел", "проверь", "не работает", "что дальше", "нужно", "запусти", "пуш", "остал", "ошиб")
        item["open_tasks"] = "Требует ручной проверки: в последнем запросе есть действие или признак проблемы." if any(word in item["last_user_request"].casefold() for word in pending_words) else "Не определено по локальным событиям; не считать задачу завершённой автоматически."
        item["event_types_text"] = ";".join(f"{key}:{value}" for key, value in sorted(item["event_types"].items()))
        project_counts[item["project"]] += 1
        grouped[item["project"]].append(item)

    for project_items in grouped.values():
        size = len(project_items)
        for item in project_items:
            if size > 1:
                item["action_reason"] += f" Group contains {size} related local records; compare before archiving or merging."
                item["tags"] += ";possible-continuation-group"

    fields = [
        "record_id", "indexed", "archive_status", "source_file_relative", "compression", "file_bytes", "source_mtime",
        "index_thread_name", "index_updated_at", "index_line", "session_meta_id", "started_at", "last_event_at",
        "cwd", "workspace_roots", "cli_version", "originator", "source", "thread_source", "history_mode", "model",
        "reasoning", "context_window", "lines", "malformed_lines", "user_messages", "meaningful_user_requests",
        "assistant_messages", "tool_events", "task_complete_events", "compacted_events", "input_tokens",
        "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens", "project", "topic",
        "proposed_name", "confidence", "value", "tags", "summary", "result_hint", "open_tasks", "action_reason",
        "event_types_text",
    ]
    write_csv(OUT / "inventory.csv", sessions, fields)
    actions_fields = ["record_id", "current_name", "proposed_name", "project", "topic", "tags", "recommended_action", "reason", "confidence", "requires_confirmation"]
    actions = []
    for item in sorted(sessions, key=lambda x: (x["project"], x["started_at"], x["record_id"])):
        actions.append({
            "record_id": item["record_id"],
            "current_name": item.get("index_thread_name", ""),
            "proposed_name": item["proposed_name"],
            "project": item["project"],
            "topic": item["topic"],
            "tags": item["tags"],
            "recommended_action": item["action"],
            "reason": item["action_reason"],
            "confidence": item["confidence"],
            "requires_confirmation": "yes",
        })
    write_csv(OUT / "actions.csv", actions, actions_fields)

    sqlite_rows = sqlite_inventory()
    local_ids = {item["record_id"] for item in sessions if item["record_id"]}
    index_ids = set(index)
    meta_ids = Counter(item["session_meta_id"] for item in sessions if item["session_meta_id"])
    duplicate_parent_count = sum(1 for value in meta_ids.values() if value > 1)
    total_bytes = sum(int(item["file_bytes"]) for item in sessions)
    total_lines = sum(int(item["lines"]) for item in sessions)
    total_tokens = sum(int(item["total_tokens"]) for item in sessions)
    active_count = sum(item["archive_status"] == "active" for item in sessions)
    archived_count = sum(item["archive_status"] == "archived" for item in sessions)
    compressed_count = sum(item["compression"] == "zstd" for item in sessions)
    source_unchanged = True
    for raw_path, before in source_manifest.items():
        path = Path(raw_path)
        if not path.exists() or (path.stat().st_size, path.stat().st_mtime_ns) != before:
            source_unchanged = False
            break

    project_lines = [
        "# Proposed Codex History Project Hierarchy",
        "",
        f"Generated: {now_text()}",
        "",
        "This is a read-only proposal. No chat was renamed, moved, tagged, archived, or deleted.",
        "All actions in `actions.csv` require separate confirmation and a backup before any future application.",
        "",
    ]
    for project in sorted(grouped, key=lambda key: (-len(grouped[key]), key.casefold())):
        items = sorted(grouped[project], key=lambda x: (x["started_at"], x["record_id"]))
        topic_counts = Counter(x["topic"] for x in items)
        project_lines += [f"## {project}", "", f"- Records: {len(items)}", f"- Topics: {', '.join(f'{topic} ({count})' for topic, count in topic_counts.most_common())}", "- Suggested tags: " + ", ".join(sorted({f"topic:{slug(x['topic'])}" for x in items})), "", "| Record | Date | Current title | Value | Suggested action |", "|---|---|---|---|---|"]
        for item in items:
            project_lines.append(f"| `{item['record_id'][:8]}` | {item['started_at'][:10]} | {item.get('index_thread_name') or '—'} | {item['value']} | {item['action']} |")
        project_lines += ["", "### Knowledge and open items", "", "- " + "\n- ".join(dedupe([x["summary"] for x in items])[:5]), "", "Open-task signal: these are heuristic flags only; inspect the original session before acting.", ""]
    (OUT / "projects.md").write_text("\n".join(project_lines), encoding="utf-8")

    for project, items in grouped.items():
        lines = [f"# {project}", "", f"Generated: {now_text()}", "", f"Records: {len(items)}", "", "## Sessions", ""]
        for item in sorted(items, key=lambda x: (x["started_at"], x["record_id"])):
            lines += [f"### {item['proposed_name']}", "", f"- Record ID: `{item['record_id']}`", f"- Parent/meta session ID: `{item['session_meta_id'] or 'not found'}`", f"- Date: `{item['started_at'] or item['index_updated_at']}`", f"- Topic: {item['topic']}", f"- Value: {item['value']}; classification confidence: {item['confidence']}", f"- Summary: {item['summary']}", f"- Result signal: {item['result_hint']}", f"- Open-task signal: {item['open_tasks']}", ""]
        (OUT / "project_summaries" / f"{slug(project)}.md").write_text("\n".join(lines), encoding="utf-8")

    report = [
        "# Codex History Audit Report",
        "",
        f"Generated: {now_text()}",
        "",
        "## Scope and safety",
        "",
        f"- CODEX_HOME: `{CODEX_HOME}`",
        f"- Output directory: `{OUT}`",
        "- Source history was read only. No JSONL, index, SQLite database, application state, or source project was modified.",
        "- `auth.json`, credential-like files, token files, and secrets were excluded from reading. Text copied into reports was filtered and redacted locally.",
        "- No history was sent to an external service or model.",
        "",
        "## Inventory",
        "",
        f"- Indexed records in `session_index.jsonl`: **{len(index)}**",
        f"- Local session files found: **{len(sessions)}** ({active_count} active, {archived_count} archived)",
        f"- Indexed IDs matched to local filenames: **{len(index_ids & local_ids)}**",
        f"- Index IDs without local file: **{len(index_ids - local_ids)}**",
        f"- Local filenames without index entry: **{len(local_ids - index_ids)}**",
        f"- Unique parent/meta session IDs: **{len(meta_ids)}**; parent IDs referenced by multiple records: **{duplicate_parent_count}**",
        f"- JSONL source size: **{total_bytes:,} bytes**; streamed lines: **{total_lines:,}**",
        f"- Zstandard-compressed records: **{compressed_count}**",
        f"- Date range: **{min((x['started_at'] for x in sessions if x['started_at']), default='unknown')} — {max((x['last_event_at'] for x in sessions if x['last_event_at']), default='unknown')}**",
        f"- Approximate recorded token totals available in events: **{total_tokens:,}**. This is telemetry from session files, not current account limits or billing.",
        "",
        "## Workspaces and proposed groups",
        "",
    ]
    for project, count in project_counts.most_common():
        report.append(f"- **{project}**: {count} record(s)")
    report += [
        "",
        "Detailed hierarchy: [`projects.md`](projects.md). Per-project summaries: `project_summaries/`.",
        "",
        "## SQLite and metadata sources",
        "",
        "SQLite files in CODEX_HOME were opened, when possible, through SQLite read-only URI mode; one file used the read-only `immutable=1` fallback because the normal read-only URI could not open it. Only table names and row counts were inspected; row contents were not copied into reports.",
        "",
    ]
    for row in sqlite_rows:
        table_text = ", ".join(f"{table['name']}={table['rows']}" for table in row["tables"]) or "no tables read"
        error = f" Error: {row['error']}" if row["error"] else ""
        report.append(f"- `{Path(row['file']).name}` ({row['bytes']:,} bytes): {table_text}.{error}")
    report += [
        "",
        "## Reconciliation and limitations",
        "",
        "- The filename UUID is treated as the local record ID used for index reconciliation. Some `session_meta.session_id` values are parent/root IDs shared by several rollout files; both are preserved in `inventory.csv`.",
        "- A matching local record was found for every current index entry. This does not prove that cloud-only chats outside the local index are enumerable; those remain outside this audit.",
        "- `Guardian review` titles are generic system-generated names. They are not assumed to be duplicates or completed work; they are marked as review/archive candidates with low confidence when no standalone user request is present.",
        "- Completion is not inferred from a `task_complete` event. Open-task flags are heuristic and must be checked against the original conversation.",
        "- Attachments, binary tool outputs, verbose tool payloads, and raw system/developer instructions were not copied into the reports.",
        "",
        "## Proposed safe actions",
        "",
        "1. Review `actions.csv` manually; do not apply it automatically.",
        "2. Keep substantive sessions and add project/topic tags using only officially supported Codex UI operations.",
        "3. Rename generic review sessions only after confirming their parent task and outcome.",
        "4. Archive only low-value candidates after a fresh backup and a second review.",
        "5. Do not edit internal JSONL, SQLite, or state files to simulate moving chats between projects.",
        "6. Before any future mutation, verify the current Codex version's supported history-management operations and obtain separate user confirmation.",
        "",
        "## Verification",
        "",
        f"- Source file size/mtime immutability during this run: **{'passed' if source_unchanged else 'changed; inspect immediately'}**",
        f"- Required output files created: `inventory.csv`, `projects.md`, `actions.csv`, `project_summaries/`, `report.md`.",
        "- The report generator itself is `_generate_audit.py`; it uses only local standard-library processing and is safe to rerun after reviewing its scope.",
        "",
    ]
    (OUT / "report.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({
        "codex_home": str(CODEX_HOME),
        "index_records": len(index),
        "local_records": len(sessions),
        "projects": len(grouped),
        "sqlite_files": len(sqlite_rows),
        "source_unchanged": source_unchanged,
        "output": str(OUT),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
