# Выдача по чатам и навигация в ChatGPT — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Заменить выдачу отдельных rollout-сессий на понятные карточки чатов и дать безопасный способ открыть или найти исходный чат в ChatGPT.

**Architecture:** Новый read-only endpoint `/api/chats` агрегирует строки `inventory.csv` по локальному `session_meta_id` и проекту. Он использует только доступные поля индекса, ищет также по проектной сводке и возвращает либо проверенный URL из разрешённых полей, либо инструкцию поиска по названию, проекту и локальному ID. Остальные представления продолжают использовать `/api/sessions`.

**Tech Stack:** Python stdlib, HTML, CSS, vanilla JavaScript, unittest, Playwright.

## Global Constraints

- Не выдумывать прямые URL чатов и не изменять внутренние базы Codex.
- Сохранять read-only режим и существующую редактировку путей/секретов.
- Не ломать таблицу, канбан, хронологию и граф, которым нужен список сессий.
- Каждое логическое изменение фиксировать отдельным Git-коммитом.

## Review Focus

- Несколько rollout-записей одного чата объединяются в один результат — unit-тест.
- При отсутствии URL показывается инструкция поиска, а не пустая ссылка — unit- и browser-тест.
- Выдача ищет по проектному описанию — unit-тест.
- Остальные view продолжают получать исходные сессии — существующий полный набор тестов.
- Demo-экспорт без URL остаётся полностью рабочим — browser-проверка.

### Task 1: Add chat aggregation and navigation metadata

**Files:**
- Modify: `codex-history-organizer/server/history_store.py`
- Modify: `codex-history-organizer/server/dashboard_server.py`
- Modify: `codex-history-organizer/tests/test_history_store.py`
- Modify: `codex-history-organizer/tests/test_dashboard_server.py`

- [ ] Добавить `HistoryStore.list_chats()` с группировкой по чату и проекту.
- [ ] Вернуть `chat_url` только из безопасных URL-полей, иначе `chat_locator`.
- [ ] Добавить read-only endpoint `/api/chats`.
- [ ] Добавить тесты группировки, поиска по описанию и fallback-инструкции.
- [ ] Commit: `feat: add chat-level history search`

### Task 2: Switch map search to chats

**Files:**
- Modify: `codex-history-organizer/dashboard/index.html`
- Modify: `codex-history-organizer/dashboard/app.js`
- Modify: `codex-history-organizer/dashboard/styles.css`
- Modify: `codex-history-organizer/tests/playwright_history_dashboard.py`

- [ ] Заменить список сессий в карте на выдачу чатов/проектов.
- [ ] Показать ссылку «Открыть чат в ChatGPT» только при наличии проверенного URL.
- [ ] Иначе показать инструкцию поиска по названию, проекту и ID.
- [ ] Сохранить правую панель описания проекта и остальные представления.
- [ ] Запустить unit, browser и mobile проверки.
- [ ] Commit: `feat: show chat navigation results`

