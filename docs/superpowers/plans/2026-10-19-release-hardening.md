# Первый публичный запуск Codex History Organizer — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Подготовить репозиторий к безопасному запуску другими пользователями без публикации личной истории Codex.

**Architecture:** Корневые инструкции объясняют запуск и границу безопасности. Пакет получает небольшой обезличенный demo-экспорт, который можно использовать вместо личного `CodexChatAudit`. Проверка из чистого клона подтверждает, что репозиторий самодостаточен.

**Tech Stack:** Python stdlib, JSON/CSV/Markdown, Git, локальный HTTP dashboard.

**Spec:** Запрос пользователя «Что дальше» после публикации репозитория и согласованный этап подготовки к первым тестовым пользователям.

## Global Constraints

- Не изменять бизнес-логику существующего проекта.
- Не добавлять в GitHub личные сессии, пути, токены или текущий `CodexChatAudit`.
- Не менять исходную историю Codex и не выполнять операции записи в `.codex`.
- Каждое логическое изменение фиксировать отдельным коммитом.
- Перед заявлением о готовности выполнить свежие тесты и проверку чистого клона.

## Review Focus

- Чистый клон не должен зависеть от личных файлов в корне рабочего каталога — проверка клонированием.
- Demo-режим должен содержать только обезличенные данные — проверка по фиксированным значениям и отсутствию персональных путей.
- Личные CSV и статусы не должны случайно индексироваться — проверка корневого `.gitignore` и `git status`.
- Пустой или отсутствующий экспорт должен оставаться безопасным — существующие тесты `HistoryStore` и dashboard.
- Документация не должна обещать запись или управление чатами — проверка README и манифестов.

### Task 1: Release documentation and safe ignore rules

**Files:**
- Create: `README.md`
- Create: `.gitignore`

- [ ] Написать корневую инструкцию с быстрым запуском, demo-режимом, локальным экспортом и границей read-only.
- [ ] Добавить исключения для личного `CodexChatAudit`, временных файлов и Python-кэшей.
- [ ] Проверить, что правила не скрывают уже отслеживаемые файлы.
- [ ] Commit: `docs: prepare repository for first users`

### Task 2: Safe demo export

**Files:**
- Create: `codex-history-organizer/demo/CodexChatAudit/inventory.csv`
- Create: `codex-history-organizer/demo/CodexChatAudit/actions.csv`
- Create: `codex-history-organizer/demo/CodexChatAudit/projects.md`
- Create: `codex-history-organizer/demo/CodexChatAudit/project_summaries/demo-project.md`
- Create: `codex-history-organizer/demo/CodexChatAudit/refresh_status.json`
- Modify: `codex-history-organizer/tests/test_package.py`

- [ ] Добавить один полностью обезличенный demo-проект с корректной схемой аудита.
- [ ] Проверить наличие demo-файлов и отсутствие локальных путей, секретов и реальных названий.
- [ ] Commit: `feat: add sanitized demo audit`

### Task 3: Fresh-clone verification and release marker

**Files:**
- Modify: `codex-history-organizer/README.md`
- Create: `codex-history-organizer/VERSION`
- Create: `codex-history-organizer/tests/test_release_readiness.py`

- [ ] Дополнить пакетную документацию ссылкой на demo и корневую инструкцию.
- [ ] Зафиксировать версию `0.1.0` без изменения API.
- [ ] Добавить тест согласованности версии и demo-пути.
- [ ] Запустить полный unittest-набор и Playwright-проверку на demo-данных.
- [ ] Создать коммит `chore: mark first public release readiness`.
- [ ] Запушить коммиты в `origin/master` и проверить, что чистый клон запускает тесты без личных файлов.

