# Codex Dashboard

Репозиторий содержит локальный read-only органайзер истории Codex. Он строит
карту проектов, таблицу сессий, канбан-сигналы, хронологию и граф связей по
заранее подготовленному экспорту `CodexChatAudit`.

## Быстрый запуск без личной истории

Из корня репозитория:

```powershell
$env:CODEX_HISTORY_AUDIT_DIR = (Resolve-Path .\codex-history-organizer\demo\CodexChatAudit)
python .\codex-history-organizer\server\dashboard_server.py
```

Откройте `http://127.0.0.1:8787/`. Demo-набор содержит только один
обезличенный проект и нужен для проверки установки и интерфейса.

## Подключение личного экспорта

1. Сформируйте аудит в отдельной папке `CodexChatAudit` по инструкции
   [codex-history-organizer/INSTALL_WINDOWS.md](codex-history-organizer/INSTALL_WINDOWS.md).
2. Укажите путь через `CODEX_HISTORY_AUDIT_DIR` или разместите папку рядом с
   репозиторием.
3. Для автоматического обновления зарегистрируйте локальную задачу Windows,
   описанную в инструкции пакета.

Исходные сессии `.codex`, JSONL, SQLite, индексы и учётные данные не нужны
органайзеру. Панель читает только подготовленные CSV/Markdown/JSON-файлы.

## Что входит в пакет

- [README пакета](codex-history-organizer/README.md) — назначение и граница
  безопасности.
- [Инструкция Windows](codex-history-organizer/INSTALL_WINDOWS.md) — запуск,
  MCP и обновление локального экспорта.
- `codex-history-organizer/demo/CodexChatAudit` — безопасный demo-экспорт.
- `codex-history-organizer/tests` — unit- и browser-проверки.

## Безопасность

Пакет не переименовывает, не архивирует, не перемещает и не удаляет чаты,
файлы или проекты. Корневые правила Git исключают личные отчёты, статусы,
кэши и локальные рабочие каталоги. Перед публикацией всегда проверяйте
`git status` и не добавляйте личный `CodexChatAudit` в коммит.

## Проверка

```powershell
python -m unittest discover -s .\codex-history-organizer\tests -p "test_*.py" -v
```

Подробности API и MCP находятся в [README пакета](codex-history-organizer/README.md).
