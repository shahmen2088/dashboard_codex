const state = { overview: null, sessions: [], selectedProject: "" };

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

function renderSessions(sessions) {
  $("#session-count").textContent = `${sessions.length} найдено`;
  if (!sessions.length) {
    $("#session-list").innerHTML = `<div class="empty-state">Ничего не найдено. Попробуйте изменить запрос.</div>`;
    return;
  }
  $("#session-list").innerHTML = sessions.map((session) => `<article class="session-row">
    <div><strong>${escapeHtml(session.name || "Без названия")}</strong><small>${escapeHtml(session.project)}</small></div>
    <div class="session-row__topic"><small>${escapeHtml(session.topic)}</small></div>
    <span class="session-row__status" data-value="${escapeHtml(session.value)}">${escapeHtml(session.value || "не указано")}</span>
    <small>${escapeHtml(session.confidence || "—")}</small>
  </article>`).join("");
}

async function loadSessions() {
  const query = new URLSearchParams({ q: $("#query").value, value: $("#value").value, limit: "100" });
  try {
    renderSessions(await getJson(`/api/sessions?${query}`));
  } catch (error) {
    $("#session-list").innerHTML = `<div class="empty-state">Не удалось загрузить список: ${escapeHtml(error.message)}</div>`;
  }
}

async function loadProject(project) {
  state.selectedProject = project;
  const panel = $("#detail-panel");
  panel.innerHTML = `<div class="detail-empty"><span class="detail-icon">…</span><p>Загружаю карту проекта.</p></div>`;
  try {
    const data = await getJson(`/api/projects/${encodeURIComponent(project)}`);
    panel.innerHTML = `<div class="detail-panel__header"><p class="eyebrow">Выбранное направление</p><h3>${escapeHtml(data.project)}</h3><p>Сводка построена по локальному индексу.</p></div>
      <div class="detail-metric"><span>Сессий</span><strong>${data.sessions}</strong></div>
      <div class="detail-metric"><span>Высокой ценности</span><strong>${data.high_value}</strong></div>
      <ul class="detail-list">${(data.highlights || []).slice(0, 6).map((item) => `<li>${escapeHtml(item.replace(/^[-# ]+/, ""))}</li>`).join("") || "<li>Краткие сведения пока не подготовлены.</li>"}</ul>`;
  } catch (error) {
    panel.innerHTML = `<div class="detail-empty"><span class="detail-icon">!</span><h3>Не удалось открыть проект</h3><p>${escapeHtml(error.message)}</p></div>`;
  }
}

async function init() {
  try {
    state.overview = await getJson("/api/overview");
    renderStats(state.overview);
    renderProjects(state.overview.groups_data || []);
    await loadSessions();
  } catch (error) {
    $("#project-grid").innerHTML = `<div class="empty-state">Данные пока недоступны: ${escapeHtml(error.message)}</div>`;
  }
  $("#query").addEventListener("input", loadSessions);
  $("#value").addEventListener("change", loadSessions);
  $("#filters").addEventListener("reset", () => setTimeout(loadSessions, 0));
}

init();
