# Технический раздел dashboard — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Убрать служебные сведения из основного сценария и собрать их в отдельной вкладке для технических пользователей.

**Architecture:** Основной экран сохраняет только безопасный статус «Только чтение» и пользовательские показатели. Блоки обновления, подключения, планировщика и диагностики перемещаются в новый view-панель `tech`; переключение сохраняется тем же механизмом вкладок и не меняет API.

**Tech Stack:** HTML, CSS, vanilla JavaScript, Playwright.

## Global Constraints

- Не изменять серверный API и бизнес-логику.
- Не скрывать технический раздел полностью: он должен быть доступен одним кликом.
- Сохранить текущие автообновление, onboarding и read-only предупреждение.
- Каждое логическое изменение фиксировать отдельным коммитом.

## Review Focus

- Обычный пользователь не видит технические панели при открытии карты — browser-проверка начального состояния.
- Технические панели доступны на вкладке «Техника» — browser-проверка перехода.
- Все пять существующих представлений не ломаются — browser-проверка всех view.
- Мобильная раскладка не создаёт горизонтального переполнения — CSS review и browser-проверка на узком viewport.

### Task 1: Move technical controls into a dedicated view

**Files:**
- Modify: `codex-history-organizer/dashboard/index.html`
- Modify: `codex-history-organizer/dashboard/styles.css`
- Modify: `codex-history-organizer/dashboard/app.js`
- Modify: `codex-history-organizer/tests/playwright_history_dashboard.py`

- [ ] Переместить refresh/setup блоки из hero и верхнего потока в view `tech`.
- [ ] Добавить вкладку «Техника», сохранив главный view `map` по умолчанию.
- [ ] Добавить спокойную адаптивную раскладку технического раздела без изменения API.
- [ ] Расширить browser-проверку начального скрытия и открытия технического раздела.
- [ ] Запустить unit-тесты и Playwright на текущем и demo-наборе.
- [ ] Commit: `feat: separate technical dashboard data`

