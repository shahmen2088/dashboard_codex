# Chat List Details Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use native execution and verify each task before committing.

**Goal:** Показывать исходные названия чатов из индекса ChatGPT и открывать описание проекта при выборе чата из основного списка.

**Architecture:** Сервер отдаёт `index_thread_name` как приоритетное название для всех представлений. Интерфейс оставляет один основной список чатов; карточки проектов убираются, а боковая панель загружает описание проекта выбранного чата.

**Tech Stack:** Python standard library, HTML, vanilla JavaScript, CSS, Playwright.

**Spec:** Требование пользователя от 2026-10-19: использовать названия из левой панели ChatGPT, убрать «Проекты и направления», открывать описание по нажатию на чат.

## Global Constraints

- Не изменять исходную историю Codex и реальные данные пользователя.
- Не придумывать и не переименовывать названия чатов.
- Сохранить режим только чтения.
- Каждый логический набор изменений проверить, закоммитить и отправить в GitHub.

## Review Focus

- При наличии обоих полей `index_thread_name` и `proposed_name` показывается индексное название.
- При отсутствии индексного названия сохраняется безопасный резервный вариант.
- Нажатие на чат открывает описание соответствующего проекта, а не отдельную карточку проекта.
- Пустой список и ошибка загрузки сохраняют понятное состояние интерфейса.
- На мобильной ширине список и описание не выходят за экран.

### Task 1: Source title priority

**Files:**
- Modify: `codex-history-organizer/server/history_store.py`
- Test: `codex-history-organizer/tests/test_history_store.py`

- [x] Проверить тестом, что `index_thread_name` имеет приоритет над `proposed_name` в сессиях и чатах.
- [x] Изменить общий сборщик карточек на порядок `index_thread_name`, затем `proposed_name`.
- [x] Запустить модульные тесты.

### Task 2: Chat-driven details layout

**Files:**
- Modify: `codex-history-organizer/dashboard/index.html`
- Modify: `codex-history-organizer/dashboard/app.js`
- Modify: `codex-history-organizer/dashboard/styles.css`
- Test: `codex-history-organizer/tests/playwright_history_dashboard.py`

- [x] Удалить отдельную секцию «Проекты и направления» и её загрузку из интерфейса.
- [x] Сделать строки чатов интерактивными и передавать выбранный проект в существующую панель описания.
- [x] Обновить пустое состояние панели, чтобы оно объясняло выбор чата.
- [x] Проверить браузером, что список чатов остаётся основным, описание открывается по нажатию, а проектные карточки отсутствуют.

### Task 3: Verification and delivery

- [x] Запустить 18 модульных тестов и Playwright-проверку.
- [x] Проверить `git diff --check`, состояние дерева и визуальный скриншот.
- [ ] Создать отдельный коммит и отправить его в `origin/master`.
