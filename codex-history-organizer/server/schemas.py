from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SessionCard:
    record_id: str
    name: str
    project: str
    topic: str
    started_at: str
    last_event_at: str
    confidence: str
    value: str
    source_state: str
    action: str
    summary: str
    open_tasks: str

    def as_dict(self) -> dict[str, str]:
        return self.__dict__.copy()
