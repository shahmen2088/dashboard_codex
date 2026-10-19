from __future__ import annotations

import os
import csv
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


STATUS_FILENAME = "refresh_status.json"


@dataclass(frozen=True)
class RefreshConfig:
    project_root: Path
    generator: Path
    audit_dir: Path
    codex_home: Path


def resolve_config() -> RefreshConfig:
    project_root = Path(__file__).resolve().parents[2]
    generator = Path(os.environ.get(
        "CODEX_HISTORY_AUDIT_GENERATOR",
        project_root / "CodexChatAudit" / "_generate_audit.py",
    )).expanduser().resolve()
    audit_dir = Path(os.environ.get(
        "CODEX_HISTORY_AUDIT_DIR",
        project_root / "CodexChatAudit",
    )).expanduser().resolve()
    codex_home = Path(os.environ.get(
        "CODEX_HOME",
        Path.home() / ".codex",
    )).expanduser().resolve()
    return RefreshConfig(project_root, generator, audit_dir, codex_home)


def now_text() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _read_existing_status(audit_dir: Path) -> dict:
    path = audit_dir / STATUS_FILENAME
    if not path.is_file() or path.stat().st_size > 256_000:
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def write_status(config: RefreshConfig, value: dict) -> None:
    config.audit_dir.mkdir(parents=True, exist_ok=True)
    target = config.audit_dir / STATUS_FILENAME
    temporary = config.audit_dir / f".{STATUS_FILENAME}.tmp"
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)


def _inventory_count(audit_dir: Path) -> int:
    path = audit_dir / "inventory.csv"
    if not path.is_file():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def refresh(config: RefreshConfig | None = None) -> None:
    config = config or resolve_config()
    if not config.generator.is_file():
        raise FileNotFoundError(f"Анализатор аудита не найден: {config.generator}")
    if not config.codex_home.is_dir():
        raise FileNotFoundError(f"Локальная папка Codex не найдена: {config.codex_home}")

    # Only the generated export directory is created. The source is never written.
    config.audit_dir.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["CODEX_HOME"] = str(config.codex_home)
    environment["CODEX_AUDIT_OUT"] = str(config.audit_dir)
    result = subprocess.run(
        [sys.executable, str(config.generator)],
        cwd=str(config.generator.parent),
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    if isinstance(result.stdout, str) and result.stdout:
        print(result.stdout, end="")
    payload = {}
    output_lines = result.stdout.splitlines() if isinstance(result.stdout, str) else []
    for line in reversed(output_lines):
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            payload = candidate
            break
    timestamp = now_text()
    previous = _read_existing_status(config.audit_dir)
    write_status(config, {
        **previous,
        "state": "ok",
        "last_attempt_at": timestamp,
        "last_success_at": timestamp,
        "last_error": "",
        "sessions": int(payload.get("local_records", _inventory_count(config.audit_dir))),
        "source_unchanged": payload.get("source_unchanged"),
        "refresh_interval_minutes": int(os.environ.get("CODEX_HISTORY_REFRESH_MINUTES", "15")),
        "read_only": True,
    })


def main() -> int:
    config = resolve_config()
    try:
        refresh(config)
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        previous = _read_existing_status(config.audit_dir)
        write_status(config, {
            **previous,
            "state": "error",
            "last_attempt_at": now_text(),
            "last_error": type(error).__name__,
            "refresh_interval_minutes": int(os.environ.get("CODEX_HISTORY_REFRESH_MINUTES", "15")),
            "read_only": True,
        })
        print(f"Обновление аудита не выполнено: {error}", file=sys.stderr)
        return 1
    print(f"Локальный аудит обновлён: {config.audit_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
