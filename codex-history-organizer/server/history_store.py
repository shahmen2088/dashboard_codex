from __future__ import annotations

import csv
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from .schemas import SessionCard


ALLOWED_FILES = frozenset({"inventory.csv", "actions.csv", "projects.md"})
MAX_TEXT = 320


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
            "groups_data": group_rows,
            "read_only": True,
            "source": "CodexChatAudit export",
        }

    def list_sessions(self, query: str = "", group: str = "", value: str = "", limit: int = 100) -> list[dict]:
        query = query.casefold().strip()
        group = group.casefold().strip()
        value = value.casefold().strip()
        cards = []
        for card in self._cards():
            haystack = " ".join((card.name, card.project, card.topic, card.summary, card.open_tasks)).casefold()
            if query and query not in haystack:
                continue
            if group and group not in card.project.casefold():
                continue
            if value and value != card.value.casefold():
                continue
            cards.append(card.as_dict())
        cards.sort(key=lambda item: (item["last_event_at"], item["name"]), reverse=True)
        return cards[: max(1, min(int(limit), 500))]

    def project_summary(self, project: str) -> dict:
        project = project.strip()
        items = [item for item in self._cards() if item.project.casefold() == project.casefold()]
        summary_path = self.audit_dir / "project_summaries" / f"{_slug(project)}.md"
        highlights: list[str] = []
        if summary_path.is_file():
            for raw_line in summary_path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = raw_line.strip()
                if line.startswith("-") or line.startswith("##"):
                    highlights.append(redact_text(line, 260))
                if len(highlights) >= 12:
                    break
        return {
            "project": redact_text(project, 100),
            "sessions": len(items),
            "high_value": sum(item.value.lower() == "high" for item in items),
            "open_tasks": [item.open_tasks for item in items if item.open_tasks][:8],
            "highlights": highlights,
            "read_only": True,
        }
