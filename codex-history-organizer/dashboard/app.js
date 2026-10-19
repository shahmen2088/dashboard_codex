const state = { overview: null, chats: [], allSessions: [], selectedProject: "", activeView: "map", refreshTimer: null, refreshing: false };

const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
}[char]));

async function getJson(url) {
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function renderStats(overview) {
  $("#stat-sessions").textContent = overview.sessions;
  $("#stat-groups").textContent = overview.groups;
  $("#stat-high-value").textContent = overview.high_value;
  $("#stat-attention").textContent = overview.needs_attention;
}

function renderFreshness(overview, error = false) {
  const label = $("#freshness");
  const dot = $("#refresh-dot");
  if (error) {
    label.textContent = "Источник недоступен";
    dot.className = "refresh-dot refresh-dot--error";
    return;
  }
  const raw = overview.last_updated;
  const formatted = raw ? new Intl.DateTimeFormat("ru-RU", { dateStyle: "short", timeStyle: "short" }).format(new Date(raw)) : "нет аудита";
  label.textContent = `Источник обновлён ${formatted}`;
  dot.className = "refresh-dot refresh-dot--ready";
}

function formatDateTime(value) {
  if (!value) return "время не указано";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "время не указано" : new Intl.DateTimeFormat("ru-RU", { dateStyle: "short", timeStyle: "short" }).format(date);
}

function renderSetup(status) {
  const auditReady = status.audit_ready;
  const refreshReady = status.state === "ok";
  const steps = [
    { label: "Панель плагина доступна", note: "локальный сервер отвечает", state: "ready" },
    { label: "Экспорт CodexChatAudit найден", note: auditReady ? `${status.sessions} сессий в индексе` : "нужен первый запуск сборщика", state: auditReady ? "ready" : "attention" },
    { label: "Последнее обновление источника", note: refreshReady ? formatDateTime(status.last_success_at) : "сборщик ещё не отработал успешно", state: refreshReady ? "ready" : "attention" },
    { label: "Планировщик Windows", note: "проверяется отдельно командой ниже", state: "manual" },
  ];
  $("#setup-steps").innerHTML = steps.map((step, index) => `<div class="setup-step setup-step--${step.state}"><span class="setup-step__index">0${index + 1}</span><div><strong>${step.label}</strong><small>${step.note}</small></div><span class="setup-step__state">${step.state === "ready" ? "готово" : step.state === "manual" ? "проверить" : "внимание"}</span></div>`).join("");
  const ok = auditReady && refreshReady;
  $("#setup-summary").textContent = ok ? "Готово к работе" : "Нужна проверка";
  $("#setup-summary").className = `setup-summary ${ok ? "setup-summary--ready" : "setup-summary--attention"}`;
  if (status.last_error) {
    $("#setup-steps").insertAdjacentHTML("beforeend", `<p class="setup-error">Последняя ошибка: ${escapeHtml(status.last_error)}</p>`);
  }
}

function renderProjects(groups) {
  const total = Math.max(...groups.map((group) => group.sessions), 1);
  $("#project-grid").innerHTML = groups.map((group, index) => {
    const uncertain = group.uncertain > 0;
    const width = Math.max(10, Math.round((group.sessions / total) * 100));
    return `<button class="project-card ${uncertain ? "project-card--uncertain" : ""}" data-project="${escapeHtml(group.name)}">
      <span class="project-card__index">${String(index + 1).padStart(2, "0")}</span>
      <h3>${escapeHtml(group.name)}</h3>
      <div class="project-card__meta"><span>${group.sessions} сессий</span><span>${uncertain ? "нужно проверить" : "уверенная группа"}</span></div>
      <div class="project-card__bar" aria-label="Объём группы"><span style="width: ${width}%"></span></div>
    </button>`;
  }).join("");
  document.querySelectorAll("[data-project]").forEach((button) => {
    button.addEventListener("click", () => loadProject(button.dataset.project));
  });
}

function renderChats(chats) {
  $("#session-count").textContent = `${chats.length} чатов найдено`;
  if (!chats.length) {
    $("#chat-list").innerHTML = `<div class="empty-state">Чаты не найдены. Попробуйте изменить запрос или открыть другой проект.</div>`;
    return;
  }
  $("#chat-list").innerHTML = chats.map((chat) => `<article class="chat-row">
    <div class="chat-row__main"><strong>${escapeHtml(chat.title || "Без названия")}</strong><small>${escapeHtml(chat.project || "Без проекта")}</small></div>
    <div class="chat-row__context"><span>${escapeHtml((chat.topics || []).join(" · ") || "Тема не указана")}</span><small>${chat.sessions} связанных записей · обновлён ${formatDate(chat.last_event_at)}</small></div>
    <span class="session-row__status" data-value="${escapeHtml(chat.value)}">${escapeHtml(chat.value || "не указано")}</span>
    <div class="chat-row__action">${chat.chat_url ? `<a class="chat-row__open" href="${escapeHtml(chat.chat_url)}" target="_blank" rel="noopener noreferrer">Открыть чат в ChatGPT</a>` : `<small class="chat-row__locator"><strong>Как найти в ChatGPT</strong>${escapeHtml(chat.chat_locator || "Откройте проект и найдите чат по названию.")}</small>`}</div>
  </article>`).join("");
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium" }).format(date);
}

function renderTable(sessions) {
  $("#table-view").innerHTML = `<table class="history-table"><thead><tr><th>Сессия</th><th>Проект</th><th>Дата</th><th>Ценность</th><th>Уверенность</th></tr></thead><tbody>${sessions.map((session) => `<tr>
    <td><strong>${escapeHtml(session.name || "Без названия")}</strong><small>${escapeHtml(session.topic || "")}</small></td>
    <td>${escapeHtml(session.project || "Без проекта")}</td>
    <td>${formatDate(session.last_event_at || session.started_at)}</td>
    <td><span class="signal signal--${escapeHtml(session.value || "normal")}">${escapeHtml(session.value || "—")}</span></td>
    <td>${escapeHtml(session.confidence || "—")}</td>
  </tr>`).join("")}</tbody></table>`;
}

function renderBoard(sessions) {
  const lanes = [
    { key: "high", title: "Ценные сигналы", note: "уровень: высокий", items: sessions.filter((session) => session.value === "high") },
    { key: "review", title: "Нужно проверить", note: "не финальное решение", items: sessions.filter((session) => session.value !== "high" && (session.confidence !== "high" || session.action !== "keep_and_tag")) },
  ];
  const assigned = new Set(lanes.flatMap((lane) => lane.items.map((session) => session.record_id)));
  lanes.push({ key: "normal", title: "Обычные сигналы", note: "остальные записи", items: sessions.filter((session) => !assigned.has(session.record_id)) });
  $("#board-view").innerHTML = lanes.map((lane) => `<section class="board-column board-column--${lane.key}">
    <header><div><h3>${lane.title}</h3><small>${lane.note}</small></div><strong>${lane.items.length}</strong></header>
    <div class="board-column__items">${lane.items.slice(0, 18).map((session) => `<article class="board-card"><strong>${escapeHtml(session.name || "Без названия")}</strong><small>${escapeHtml(session.project || "Без проекта")}</small><span>${formatDate(session.last_event_at || session.started_at)}</span></article>`).join("") || `<div class="empty-state">Нет записей</div>`}</div>
  </section>`).join("");
}

function renderTimeline(sessions) {
  const items = [...sessions].sort((a, b) => String(b.last_event_at || b.started_at).localeCompare(String(a.last_event_at || a.started_at))).slice(0, 40);
  $("#timeline-view").innerHTML = items.map((session) => `<article class="timeline-item">
    <div class="timeline-item__date">${formatDate(session.last_event_at || session.started_at)}</div>
    <div class="timeline-item__dot"></div>
    <div class="timeline-item__body"><strong>${escapeHtml(session.name || "Без названия")}</strong><small>${escapeHtml(session.project || "Без проекта")} · ${escapeHtml(session.topic || "Без темы")}</small><p>${escapeHtml(session.summary || "Краткая сводка не подготовлена.")}</p></div>
  </article>`).join("") || `<div class="empty-state">Хронология пока пуста.</div>`;
}

function renderGraph(groups) {
  const svg = $("#history-graph");
  const center = { x: 500, y: 310 };
  const radius = 215;
  const nodes = groups.slice(0, 10).map((group, index, all) => {
    const angle = -Math.PI / 2 + (index * Math.PI * 2) / Math.max(all.length, 1);
    return { ...group, x: center.x + Math.cos(angle) * radius, y: center.y + Math.sin(angle) * radius };
  });
  const shorten = (value) => value.length > 24 ? `${value.slice(0, 23)}…` : value;
  svg.innerHTML = `<g class="graph-links">${nodes.map((node) => `<line x1="${center.x}" y1="${center.y}" x2="${node.x}" y2="${node.y}"></line>`).join("")}</g>
    <g class="graph-center"><circle cx="${center.x}" cy="${center.y}" r="70"></circle><text x="${center.x}" y="${center.y - 5}" text-anchor="middle">Codex</text><text x="${center.x}" y="${center.y + 18}" text-anchor="middle">История</text></g>
    <g class="graph-nodes">${nodes.map((node) => `<g class="graph-node" tabindex="0"><circle cx="${node.x}" cy="${node.y}" r="${Math.max(25, Math.min(48, 24 + node.sessions * 1.6))}"></circle><text x="${node.x}" y="${node.y - 5}" text-anchor="middle">${escapeHtml(shorten(node.name))}</text><text class="graph-node__count" x="${node.x}" y="${node.y + 17}" text-anchor="middle">${node.sessions} сесс.</text></g>`).join("")}</g>`;
}

function renderAlternativeViews() {
  renderTable(state.allSessions);
  renderBoard(state.allSessions);
  renderTimeline(state.allSessions);
  renderGraph(state.overview?.groups_data || []);
}

async function loadChats() {
  const query = new URLSearchParams({ q: $("#query").value, value: $("#value").value, limit: "100" });
  try {
    state.chats = await getJson(`/api/chats?${query}`);
    renderChats(state.chats);
  } catch (error) {
    $("#chat-list").innerHTML = `<div class="empty-state">Не удалось загрузить список чатов: ${escapeHtml(error.message)}</div>`;
  }
}

async function loadProject(project) {
  state.selectedProject = project;
  const panel = $("#detail-panel");
  panel.innerHTML = `<div class="detail-empty"><span class="detail-icon">…</span><p>Загружаю карту проекта.</p></div>`;
  try {
    const data = await getJson(`/api/projects/${encodeURIComponent(project)}`);
    panel.innerHTML = `<div class="detail-panel__header"><p class="eyebrow">Выбранное направление</p><h3>${escapeHtml(data.project)}</h3><p class="detail-panel__description"><strong>Описание проекта</strong>${escapeHtml(data.description || "Описание пока не подготовлено.")}</p></div>
      <div class="detail-metric"><span>Сессий</span><strong>${data.sessions}</strong></div>
      <div class="detail-metric"><span>Высокой ценности</span><strong>${data.high_value}</strong></div>
      <ul class="detail-list">${(data.highlights || []).slice(0, 6).map((item) => `<li>${escapeHtml(item.replace(/^[-# ]+/, ""))}</li>`).join("") || "<li>Краткие сведения пока не подготовлены.</li>"}</ul>`;
  } catch (error) {
    panel.innerHTML = `<div class="detail-empty"><span class="detail-icon">!</span><h3>Не удалось открыть проект</h3><p>${escapeHtml(error.message)}</p></div>`;
  }
}

async function refreshDashboard({ silent = false } = {}) {
  if (state.refreshing) return;
  state.refreshing = true;
  try {
    state.overview = await getJson("/api/overview");
    renderSetup(await getJson("/api/status"));
    renderStats(state.overview);
    renderProjects(state.overview.groups_data || []);
    state.allSessions = await getJson("/api/sessions?limit=500");
    renderAlternativeViews();
    await loadChats();
    if (state.selectedProject) await loadProject(state.selectedProject);
    renderFreshness(state.overview);
  } catch (error) {
    if (!silent) $("#project-grid").innerHTML = `<div class="empty-state">Данные пока недоступны: ${escapeHtml(error.message)}</div>`;
    renderFreshness(state.overview || {}, true);
  } finally {
    state.refreshing = false;
  }
}

function setActiveView(view) {
  state.activeView = view;
  localStorage.setItem("codex-history-active-view", view);
  document.querySelectorAll("[data-view-panel]").forEach((panel) => {
    panel.hidden = panel.dataset.viewPanel !== view;
  });
  document.querySelectorAll(".view-tab").forEach((tab) => {
    const active = tab.dataset.view === view;
    tab.classList.toggle("view-tab--active", active);
    tab.setAttribute("aria-selected", String(active));
  });
}

function configureViews() {
  const saved = localStorage.getItem("codex-history-active-view");
  const available = ["map", "table", "board", "timeline", "graph", "tech"];
  setActiveView(available.includes(saved) ? saved : "map");
  document.querySelectorAll(".view-tab").forEach((tab) => tab.addEventListener("click", () => setActiveView(tab.dataset.view)));
}

function configureAutoRefresh() {
  const select = $("#refresh-interval");
  const saved = localStorage.getItem("codex-history-refresh-seconds");
  if (saved && [...select.options].some((option) => option.value === saved)) select.value = saved;
  const schedule = () => {
    if (state.refreshTimer) clearInterval(state.refreshTimer);
    const seconds = Number(select.value);
    localStorage.setItem("codex-history-refresh-seconds", select.value);
    if (seconds > 0) state.refreshTimer = setInterval(() => refreshDashboard({ silent: true }), seconds * 1000);
  };
  select.addEventListener("change", schedule);
  $("#refresh-now").addEventListener("click", () => refreshDashboard());
  schedule();
}

function configureSetup() {
  $("#setup-copy").addEventListener("click", async () => {
    const command = $("#setup-command").textContent;
    try {
      await navigator.clipboard.writeText(command);
      $("#setup-copy-status").textContent = "Скопировано";
    } catch (error) {
      $("#setup-copy-status").textContent = "Скопируйте команду вручную";
    }
    setTimeout(() => { $("#setup-copy-status").textContent = ""; }, 2400);
  });
}

async function init() {
  configureViews();
  configureAutoRefresh();
  configureSetup();
  await refreshDashboard();
  $("#query").addEventListener("input", loadChats);
  $("#value").addEventListener("change", loadChats);
  $("#filters").addEventListener("reset", () => setTimeout(loadChats, 0));
}

init();
