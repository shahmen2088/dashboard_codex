# Поиск сессий и описание проекта — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Сделать поиск сессий заметнее и разрешить находить сессии по описанию выбранного проекта.

**Architecture:** API `HistoryStore.list_sessions` дополнит поисковый набор текстом соответствующей сводки проекта из `project_summaries/*.md`; исходные `.codex` и проекты не читаются. В карте поиска будет размещён перед карточками проектов, а правая панель продолжит показывать описание и ключевые сведения выбранного проекта.

**Tech Stack:** Python stdlib, HTML, CSS, vanilla JavaScript, unittest, Playwright.

## Global Constraints

- Сохранять read-only границу и существующий API URL.
- Не добавлять в ответ необезличенное содержимое: применять существующее редактирование путей и секретов.
- Поиск по описанию проекта должен работать без изменения формата CSV.
- Каждое логическое изменение фиксировать отдельным Git-коммитом.

## Review Focus

- Запрос, встречающийся только в `project_summaries/*.md`, возвращает сессии проекта — unit-тест.
- Отсутствующая сводка не ломает поиск — unit-тест.
- Поиск расположен до карточек проектов — browser-проверка порядка элементов.
- Правая панель сохраняет описание проекта — browser-проверка выбора проекта.
- Узкий экран не получает горизонтального переполнения — browser-проверка.

### Task 1: Search project descriptions and raise search controls

**Files:**
- Modify: `codex-history-organizer/server/history_store.py`
- Modify: `codex-history-organizer/tests/test_history_store.py`
- Modify: `codex-history-organizer/dashboard/index.html`
- Modify: `codex-history-organizer/dashboard/styles.css`
- Modify: `codex-history-organizer/tests/playwright_history_dashboard.py`

- [ ] Добавить безопасное чтение проектной сводки как дополнительного поискового текста.
- [ ] Перенести блок поиска перед сеткой проектов, сохранив правую панель описания.
- [ ] Обновить responsive-раскладку и подписи поиска.
- [ ] Добавить unit- и browser-проверки.
- [ ] Запустить полный набор проверок и визуально осмотреть экран.
- [ ] Commit: `feat: improve session search context`

