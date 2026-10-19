# Codex History Organizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local, read-only Codex plugin with a clear visual map of projects, chats, decisions, and unfinished work.

**Architecture:** A self-contained plugin package will read only the generated `CodexChatAudit` reports, expose read-only MCP tools, and serve a local dashboard. The dashboard will be the primary visual surface; the MCP tools will let Codex answer questions from the same indexed data. No code will be added to or executed from the existing `control_center` application.

**Tech Stack:** Python standard library for CSV/Markdown loading, HTTP serving, and stdio MCP transport; semantic HTML/CSS/vanilla JavaScript for the dashboard; Python `unittest`; Playwright for browser verification.

**Spec:** `CodexChatAudit/report.md`, `CodexChatAudit/projects.md`, and the current user brief.

## Global Constraints

- Read only: never edit or delete Codex JSONL, indexes, SQLite, source projects, or application state.
- Read only: allowlist `inventory.csv`, `actions.csv`, `projects.md`, and `project_summaries/*.md` as data sources.
- Never read `auth.json`, credential files, raw secrets, or raw session content.
- Do not expose full prompts, tool logs, tokens, API keys, or passwords in the UI or MCP results.
- Keep the package separate from `control_center`.
- Every implementation task ends with a focused verification and a Git commit.

## Review Focus

- Missing or malformed audit files must produce a useful empty/error state, not a server crash.
- CSV values may contain commas, quotes, newlines, Unicode, and redacted text; parsing must remain correct.
- Secret-like fields and raw paths must not leak into search results or summaries.
- Long project names and 47+ sessions must remain legible without horizontal overflow.
- The dashboard must remain usable on narrow screens, with keyboard focus and reduced-motion support.

---

### Task 1: Create the plugin package and safety boundary

**Files:**
- Create: `codex-history-organizer/plugin.json`
- Create: `codex-history-organizer/.codex-plugin/plugin.json`
- Create: `codex-history-organizer/mcp.json`
- Create: `codex-history-organizer/skills/codex-history-organizer/SKILL.md`
- Create: `codex-history-organizer/README.md`
- Test: `codex-history-organizer/tests/test_package.py`

**Interfaces:**
- Produces a package rooted at `codex-history-organizer/` with a portable manifest, Codex compatibility manifest, read-only MCP declaration, and a skill describing safe use.
- The package must use `${PLUGIN_ROOT}` for local server paths and require local execution for the desktop-only stdio server.

- [ ] **Step 1: Write failing package validation tests** for manifest JSON, required paths, read-only wording, and absence of secret-file references.
- [ ] **Step 2: Run `python -m unittest codex-history-organizer/tests/test_package.py -v`** and verify the new tests fail because the package is absent.
- [ ] **Step 3: Implement the manifests, skill, and README** with explicit read-only behavior and manual install instructions.
- [ ] **Step 4: Run the focused package tests** and verify all assertions pass.
- [ ] **Step 5: Commit** with `feat: scaffold codex history organizer plugin`.

### Task 2: Implement the safe audit-data store

**Files:**
- Create: `codex-history-organizer/server/history_store.py`
- Create: `codex-history-organizer/server/schemas.py`
- Create: `codex-history-organizer/tests/test_history_store.py`

**Interfaces:**
- `HistoryStore(audit_dir: Path)` reads only the allowlisted report files.
- `HistoryStore.overview() -> dict` returns counts, groups, date range, and verification flags.
- `HistoryStore.list_sessions(query: str = "", group: str = "", limit: int = 100) -> list[dict]` returns redacted session cards.
- `HistoryStore.project_summary(project: str) -> dict` returns a project summary and safe open-task text.
- `redact_text(value: str) -> str` removes secret-like values, credential labels, and full prompt/tool-log payloads.

- [ ] **Step 1: Write failing tests** for valid audit data, quoted CSV fields, empty files, missing files, Unicode, secret redaction, and the 47-record fixture shape.
- [ ] **Step 2: Run the focused store tests** and verify failure before implementation.
- [ ] **Step 3: Implement allowlisted loading, typed normalization, stable sorting, and redaction** without any write operation.
- [ ] **Step 4: Run the focused tests** and verify counts and redaction behavior.
- [ ] **Step 5: Commit** with `feat: add read-only history data store`.

### Task 3: Add read-only MCP tools

**Files:**
- Create: `codex-history-organizer/server/mcp_server.py`
- Modify: `codex-history-organizer/mcp.json`
- Create: `codex-history-organizer/tests/test_mcp_server.py`

**Interfaces:**
- MCP tools: `history_overview`, `search_history`, and `get_project_summary`.
- Each tool returns structured JSON and explicitly states that no mutation is supported.
- The stdio process must write protocol responses to stdout and diagnostics only to stderr.

- [ ] **Step 1: Write failing protocol tests** for initialize, tools/list, valid tool calls, unknown tools, malformed requests, and read-only tool descriptions.
- [ ] **Step 2: Run the focused MCP tests** and verify failure before implementation.
- [ ] **Step 3: Implement the minimal stdio JSON-RPC/MCP loop** backed by `HistoryStore`.
- [ ] **Step 4: Run the focused tests** and verify deterministic structured responses.
- [ ] **Step 5: Commit** with `feat: expose read-only history MCP tools`.

### Task 4: Build the visual history map

**Files:**
- Create: `codex-history-organizer/dashboard/index.html`
- Create: `codex-history-organizer/dashboard/styles.css`
- Create: `codex-history-organizer/dashboard/app.js`
- Create: `codex-history-organizer/server/dashboard_server.py`
- Create: `codex-history-organizer/tests/test_dashboard_server.py`

**Interfaces:**
- HTTP endpoints: `GET /`, `GET /api/overview`, `GET /api/sessions`, `GET /api/projects/:name`.
- UI regions: overview strip, project map, attention queue, searchable session list, project detail panel.
- Query parameters: `q`, `group`, `value`, and `limit`.

**Design direction:**
- Dark archival-map visual language matching the Neuroplov ecosystem: deep ink background, paper-like blue panels, cyan for navigation, amber for attention, and green only for verified safe state.
- The primary visual is a project map with proportional session counts and confidence markers, not a wall of identical cards.
- Use a calm two-column desktop layout that collapses to a single column on mobile; keep action language plain and avoid technical identifiers in the first view.
- Make uncertainty visible with labels such as “нужно проверить”, not with misleading completion colors.

- [ ] **Step 1: Write failing HTTP tests** for static serving, JSON endpoints, filters, empty state, and missing-data errors.
- [ ] **Step 2: Run the focused server tests** and verify failure before implementation.
- [ ] **Step 3: Implement the local dashboard server** with safe CORS-free same-origin JSON endpoints.
- [ ] **Step 4: Implement the dashboard layout, filtering, detail panel, responsive states, keyboard focus, and reduced-motion styles.**
- [ ] **Step 5: Run the focused server tests** and verify all endpoint assertions pass.
- [ ] **Step 6: Commit** with `feat: add codex history visual dashboard`.

### Task 5: Browser verification and packaging check

**Files:**
- Create: `codex-history-organizer/tests/playwright_history_dashboard.py`
- Modify: `codex-history-organizer/README.md`

**Interfaces:**
- The test starts the local server, opens the dashboard, checks the rendered project map, filters sessions, opens a project detail panel, checks console errors, and captures a screenshot.

- [ ] **Step 1: Run `python C:/Users/s.buronov/.codex/skills/webapp-testing/scripts/with_server.py --help`** before using the helper.
- [ ] **Step 2: Run the Playwright smoke test** against the local dashboard and verify it reports zero console errors and the expected visible sections.
- [ ] **Step 3: Validate JSON manifests and run the complete unit-test suite** for the plugin.
- [ ] **Step 4: Review the screenshot for hierarchy, overflow, contrast, and mobile layout; fix only verified defects.**
- [ ] **Step 5: Commit** with `test: verify history dashboard and plugin package`.

### Task 6: Prepare safe Codex installation instructions

**Files:**
- Modify: `codex-history-organizer/README.md`
- Create: `codex-history-organizer/INSTALL_WINDOWS.md`

**Interfaces:**
- Document how to set `CODEX_HISTORY_AUDIT_DIR`, run the dashboard locally, test MCP tools, and manually register the plugin through a supported local marketplace or plugin upload flow.
- Clearly separate implemented behavior from future live-history integration.

- [ ] **Step 1: Document the exact commands and paths used by the verified tests.**
- [ ] **Step 2: Add a security checklist covering read-only mode, secret exclusion, and no production publication.**
- [ ] **Step 3: Run the final verification command** and record the output before claiming the package is ready.
- [ ] **Step 4: Commit** with `docs: document codex history organizer setup`.

## Verification Summary

Before describing the first release as ready, run:

```powershell
python -m unittest discover -s codex-history-organizer/tests -p "test_*.py" -v
python codex-history-organizer/tests/playwright_history_dashboard.py
```

The result must show zero failing unit tests, a successful browser smoke test, no console errors, and no writes outside the new plugin directory.
