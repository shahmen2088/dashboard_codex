from __future__ import annotations

import csv
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from .schemas import SessionCard


ALLOWED_FILES = frozenset({"inventory.csv", "actions.csv", "projects.md"})
STATUS_FILENAME = "refresh_status.json"
MAX_TEXT = 320
ALLOWED_CHAT_HOSTS = frozenset({"chatgpt.com", "chat.openai.com"})


def default_audit_dir() -> Path:
    configured = os.environ.get("CODEX_HISTORY_AUDIT_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "CodexChatAudit"


def redact_text(value: object, limit: int = MAX_TEXT) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"(?i)bearer\s+\S+", "Bearer [скрыто]", text)
    text = re.sub(
        r"(?i)(api[_ -]?key|token|password|парол\w*|ключ\w*)\s*[:=]\s*\S+",
        r"\1: [скрыто]",
        text,
    )
    text = re.sub(r"(?i)sk-[a-z0-9_-]{12,}", "[скрыто]", text)
    text = re.sub(r"\[LOCAL_PATH:[^\]]+\]", "[локальный файл]", text, flags=re.IGNORECASE)
    text = re.sub(r"chatgpt-conversation://\S+", "[связанная сессия]", text, flags=re.IGNORECASE)
    text = re.sub(r"(?:[A-Za-z]:\\|\\\\)[^\s,;]+", "[локальный путь]", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _first_nonempty(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = row.get(key, "")
        if value:
            return value
    return ""


def _slug(value: str) -> str:
    value = value.lower().replace("ё", "е")
    value = re.sub(r"[^a-zа-я0-9]+", "-", value)
    return value.strip("-")


def _safe_chat_url(value: object) -> str:
    candidate = str(value or "").strip()
    parsed = urlparse(candidate)
    if (
        parsed.scheme == "https"
        and parsed.netloc.casefold() in ALLOWED_CHAT_HOSTS
        and parsed.path.startswith("/c/")
    ):
        return candidate[:500]
    return ""


class HistoryStore:
    """Read the audit export without opening raw Codex history."""

    def __init__(self, audit_dir: Path | str | None = None):
        self.audit_dir = Path(audit_dir or default_audit_dir()).expanduser().resolve()

    def _inventory(self) -> list[dict[str, str]]:
        return _read_csv(self.audit_dir / "inventory.csv")

    def _actions(self) -> dict[str, dict[str, str]]:
        return {row.get("record_id", ""): row for row in _read_csv(self.audit_dir / "actions.csv")}

    def _card(self, row: dict[str, str], action: dict[str, str] | None = None) -> SessionCard:
        action = action or {}
        return SessionCard(
            record_id=row.get("record_id", ""),
            name=redact_text(_first_nonempty(row, "proposed_name", "index_thread_name"), 120),
            project=redact_text(row.get("project", "") or "Без проекта", 100),
            topic=redact_text(row.get("topic", "") or "Без темы", 100),
            started_at=row.get("started_at", ""),
            last_event_at=row.get("last_event_at", ""),
            confidence=redact_text(row.get("confidence", ""), 30),
            value=redact_text(row.get("value", ""), 30),
            source_state=redact_text(row.get("archive_status", ""), 30),
            action=redact_text(action.get("recommended_action", ""), 40),
            summary=redact_text(row.get("summary", "")),
            open_tasks=redact_text(row.get("open_tasks", "")),
        )

    def _cards(self) -> list[SessionCard]:
        actions = self._actions()
        return [self._card(row, actions.get(row.get("record_id", ""))) for row in self._inventory()]

    def _project_summary_path(self, project: str) -> Path:
        return self.audit_dir / "project_summaries" / f"{_slug(project)}.md"

    def _project_search_text(self, project: str) -> str:
        path = self._project_summary_path(project)
        if not path.is_file():
            return ""
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return redact_text(text, 20_000)

    def source_updated_at(self) -> str:
        candidates = [self.audit_dir / name for name in ALLOWED_FILES]
        summaries = self.audit_dir / "project_summaries"
        if summaries.is_dir():
            candidates.extend(summaries.glob("*.md"))
        timestamps = [path.stat().st_mtime for path in candidates if path.is_file()]
        if not timestamps:
            return ""
        return datetime.fromtimestamp(max(timestamps)).astimezone().isoformat(timespec="seconds")

    def status(self) -> dict:
        path = self.audit_dir / STATUS_FILENAME
        value: dict = {}
        if path.is_file() and path.stat().st_size <= 256_000:
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    value = loaded
            except (OSError, json.JSONDecodeError):
                value = {}
        required_files = {name: (self.audit_dir / name).is_file() for name in sorted(ALLOWED_FILES)}
        last_success = redact_text(value.get("last_success_at", ""), 60)
        last_attempt = redact_text(value.get("last_attempt_at", ""), 60)
        last_error = redact_text(value.get("last_error", ""), 80)
        try:
            sessions = int(value.get("sessions", len(self._inventory())) or 0)
        except (TypeError, ValueError):
            sessions = len(self._inventory())
        try:
            interval = int(value.get("refresh_interval_minutes", 15) or 15)
        except (TypeError, ValueError):
            interval = 15
        return {
            "state": redact_text(value.get("state", "not_run"), 20),
            "audit_ready": required_files.get("inventory.csv", False),
            "required_files": required_files,
            "last_updated": self.source_updated_at(),
            "last_success_at": last_success,
            "last_attempt_at": last_attempt,
            "last_error": last_error,
            "sessions": sessions,
            "source_unchanged": value.get("source_unchanged"),
            "refresh_interval_minutes": interval,
            "read_only": True,
        }

    def overview(self) -> dict:
        cards = self._cards()
        groups: dict[str, list[SessionCard]] = defaultdict(list)
        for card in cards:
            groups[card.project].append(card)

        group_rows = []
        for name, items in sorted(groups.items(), key=lambda pair: (-len(pair[1]), pair[0])):
            group_rows.append(
                {
                    "name": name,
                    "sessions": len(items),
                    "high_value": sum(item.value.lower() == "high" for item in items),
                    "open_tasks": sum(bool(item.open_tasks) and "не определено" not in item.open_tasks.lower() for item in items),
                    "uncertain": sum(item.confidence.lower() not in {"high", ""} for item in items),
                }
            )

        starts = [item.started_at for item in cards if item.started_at]
        ends = [item.last_event_at for item in cards if item.last_event_at]
        return {
            "sessions": len(cards),
            "groups": len(group_rows),
            "high_value": sum(item.value.lower() == "high" for item in cards),
            "needs_attention": sum(item.action not in {"", "keep_and_tag"} for item in cards),
            "date_range": {"start": min(starts, default=""), "end": max(ends, default="")},
            "last_updated": self.source_updated_at(),
            "groups_data": group_rows,
            "read_only": True,
            "source": "CodexChatAudit export",
        }

    def list_sessions(self, query: str = "", group: str = "", value: str = "", limit: int = 100) -> list[dict]:
        query = query.casefold().strip()
        group = group.casefold().strip()
        value = value.casefold().strip()
        cards = []
        project_context: dict[str, str] = {}
        for card in self._cards():
            if card.project not in project_context:
                project_context[card.project] = self._project_search_text(card.project)
            haystack = " ".join((card.name, card.project, card.topic, card.summary, card.open_tasks, project_context[card.project])).casefold()
            if query and query not in haystack:
                continue
            if group and group not in card.project.casefold():
                continue
            if value and value != card.value.casefold():
                continue
            cards.append(card.as_dict())
        cards.sort(key=lambda item: (item["last_event_at"], item["name"]), reverse=True)
        return cards[: max(1, min(int(limit), 500))]

    def list_chats(self, query: str = "", group: str = "", value: str = "", limit: int = 100) -> list[dict]:
        """Return one navigable result per indexed chat and project."""
        query = query.casefold().strip()
        group = group.casefold().strip()
        value = value.casefold().strip()
        actions = self._actions()
        project_context: dict[str, str] = {}
        grouped: dict[tuple[str, str], dict] = {}

        for row in self._inventory():
            card = self._card(row, actions.get(row.get("record_id", "")))
            if card.project not in project_context:
                project_context[card.project] = self._project_search_text(card.project)
            haystack = " ".join((card.name, card.project, card.topic, card.summary, card.open_tasks, project_context[card.project])).casefold()
            matches = not query or query in haystack
            if group and group not in card.project.casefold():
                matches = False
            if value and value != card.value.casefold():
                matches = False
            chat_id = row.get("session_meta_id", "").strip() or row.get("record_id", "").strip()
            key = (card.project.casefold(), chat_id)
            entry = grouped.setdefault(key, {"project": card.project, "chat_id": chat_id, "rows": [], "cards": [], "matches": False})
            entry["rows"].append(row)
            entry["cards"].append(card)
            entry["matches"] = entry["matches"] or matches

        results = []
        value_rank = {"low": 0, "normal": 1, "high": 2}
        for entry in grouped.values():
            if not entry["matches"]:
                continue
            cards = entry["cards"]
            rows = entry["rows"]
            latest_index = max(range(len(cards)), key=lambda index: (cards[index].last_event_at, cards[index].started_at))
            latest_card = cards[latest_index]
            latest_row = rows[latest_index]
            title = redact_text(_first_nonempty(latest_row, "index_thread_name", "proposed_name") or "Без названия", 160)
            topics = []
            for card in cards:
                if card.topic and card.topic not in topics:
                    topics.append(card.topic)
            value_name = max((card.value.casefold() for card in cards), key=lambda item: value_rank.get(item, 0), default="")
            chat_url = ""
            for row in rows:
                for field in ("chat_url", "conversation_url", "thread_url", "url"):
                    chat_url = _safe_chat_url(row.get(field, ""))
                    if chat_url:
                        break
                if chat_url:
                    break
            locator = (
                f"В ChatGPT откройте проект «{entry['project']}» и найдите чат «{title}». "
                f"Если название изменено, проверьте локальный ID: {redact_text(entry['chat_id'], 80)}."
            )
            results.append({
                "chat_id": redact_text(entry["chat_id"], 80),
                "title": title,
                "project": entry["project"],
                "sessions": len(cards),
                "topics": topics,
                "last_event_at": latest_card.last_event_at or latest_card.started_at,
                "value": value_name,
                "confidence": "high" if any(card.confidence.casefold() == "high" for card in cards) else (latest_card.confidence or ""),
                "summary": latest_card.summary,
                "chat_url": chat_url,
                "chat_locator": locator if not chat_url else "",
                "read_only": True,
            })
        results.sort(key=lambda item: (item["last_event_at"], item["title"]), reverse=True)
        return results[: max(1, min(int(limit), 500))]

    def project_summary(self, project: str) -> dict:
        project = project.strip()
        items = [item for item in self._cards() if item.project.casefold() == project.casefold()]
        summary_path = self._project_summary_path(project)
        highlights: list[str] = []
        description = ""
        if summary_path.is_file():
            for raw_line in summary_path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = raw_line.strip()
                if line.startswith("###"):
                    line = re.sub(r"\s+—\s+\d{4}-\d{2}-\d{2}.*$", "", line)
                    highlights.append(redact_text(line, 180))
                elif line.startswith(("- Summary:", "- Result signal:", "- Open-task signal:")):
                    safe_line = redact_text(line, 260)
                    highlights.append(safe_line)
                    if not description and line.startswith("- Summary:"):
                        description = redact_text(line.split(":", 1)[1].strip(), 420)
                elif line.startswith("- ") and not any(
                    marker in line.casefold()
                    for marker in ("record id", "parent/meta", "date:", "topic:", "value:")
                ):
                    safe_line = redact_text(line, 220)
                    highlights.append(safe_line)
                    if not description:
                        description = redact_text(line[2:].strip(), 420)
                if len(highlights) >= 12:
                    break
        if not description:
            description = f"Локальная группа из {len(items)} сессий."
        return {
            "project": redact_text(project, 100),
            "sessions": len(items),
            "high_value": sum(item.value.lower() == "high" for item in items),
            "description": description,
            "open_tasks": [item.open_tasks for item in items if item.open_tasks][:8],
            "highlights": highlights,
            "read_only": True,
        }
