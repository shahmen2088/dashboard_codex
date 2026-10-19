from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


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
    subprocess.run(
        [sys.executable, str(config.generator)],
        cwd=str(config.generator.parent),
        env=environment,
        check=True,
    )


def main() -> int:
    try:
        refresh()
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        print(f"Обновление аудита не выполнено: {error}", file=sys.stderr)
        return 1
    print(f"Локальный аудит обновлён: {resolve_config().audit_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
