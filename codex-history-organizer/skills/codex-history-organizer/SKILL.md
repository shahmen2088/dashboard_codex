---
name: codex-history-organizer
description: Search and explain the user's locally indexed Codex history without changing chats, projects, files, or application state.
---

# Codex History Organizer

Use this skill when the user asks to find, compare, summarize, or understand
local Codex history.

Safety rules:

- Use only the read-only history tools exposed by this plugin.
- Never read `auth.json`, credential files, raw session streams, or SQLite
  databases.
- Never rename, move, archive, delete, or edit chats or projects.
- Treat completion and open-task labels as audit signals, not proof.
- Prefer the visual dashboard for orientation and use project summaries for
  details.
- Mention when the local audit index may be stale.
