"use strict";

/**
 * Renderização do painel a partir do estado do BridgeController.
 * Usa apenas textContent (nunca innerHTML) — o conteúdo do plano não é confiável.
 */

const { STATUS } = require("../core/constants");
const { formatPreview } = require("../core/analyze");
const { formatReport } = require("../core/report");

const $ = (id) => document.getElementById(id);

/**
 * @param {import("../core/controller").BridgeState} s
 */
function renderState(s) {
  const premiere = $("st-premiere");
  premiere.textContent = s.connected ? `CONNECTED ${s.premiereVersion ? `(${s.premiereVersion})` : ""}` : "DISCONNECTED";
  premiere.className = `v ${s.connected ? "state-ok" : "state-err"}`;
  $("st-uxp").textContent = s.uxpVersion || "-";
  $("st-project").textContent = s.projectName || "-";
  $("st-sequence").textContent = s.sequenceName || "-";
  $("st-plan").textContent = s.planFile || "-";

  const status = $("st-status");
  status.textContent = s.currentStep ? `${s.status} · ${s.currentStep}` : s.status;
  status.className = `v ${
    s.status === STATUS.ERROR ? "state-err" : s.status === STATUS.COMPLETE ? "state-ok" : s.status === STATUS.IDLE ? "" : "state-busy"
  }`;
  $("progress-bar").style.width = `${Math.round((s.progress || 0) * 100)}%`;
  $("st-message").textContent = s.message || "";

  const busy = s.status === STATUS.PROCESSING || s.status === STATUS.PAUSED;
  const canExecute = !busy && s.connected && !!s.preview && s.preview.canExecute;
  $("btn-load").disabled = busy;
  $("btn-analyze").disabled = busy || !s.planFile;
  $("btn-execute").disabled = !canExecute;
  $("btn-execute-preview").disabled = !canExecute;
  $("btn-pause").disabled = !busy;
  $("btn-pause").textContent = s.status === STATUS.PAUSED ? "RETOMAR" : "PAUSAR";
  $("btn-open").disabled = busy;
  $("btn-render").disabled = busy;

  renderPreview(s.preview);
  renderReport(s.report);
}

/** @param {import("../core/analyze").PlanPreview|null} preview */
function renderPreview(preview) {
  const card = $("preview");
  if (!preview) {
    card.classList.add("hidden");
    return;
  }
  card.classList.remove("hidden");
  $("preview-counts").textContent = formatPreview(preview);
  const list = $("preview-issues");
  list.textContent = "";
  const items = [
    ...preview.validation.errors.map((i) => ({ ...i, level: "error" })),
    ...preview.validation.warnings.map((i) => ({ ...i, level: "warning" })),
  ];
  for (const issue of items.slice(0, 50)) {
    const li = document.createElement("li");
    li.className = issue.level;
    li.textContent = `${issue.path}: ${issue.message}`;
    list.appendChild(li);
  }
  if (items.length > 50) {
    const li = document.createElement("li");
    li.textContent = `... +${items.length - 50}`;
    list.appendChild(li);
  }
}

/** @param {import("../core/report").ExecutionReport|null} report */
function renderReport(report) {
  const card = $("report");
  if (!report) {
    card.classList.add("hidden");
    return;
  }
  card.classList.remove("hidden");
  $("report-text").textContent = formatReport(report);
}

const MAX_LOG_ROWS = 500;

/** @param {import("../core/logger").LogEntry} e */
function appendLog(e) {
  const list = $("log-list");
  const row = document.createElement("div");
  row.className = `log-entry ${e.status}`;
  const time = e.timestamp.slice(11, 19);
  const s = document.createElement("span");
  s.className = "s";
  s.textContent = e.status.toUpperCase();
  row.appendChild(document.createTextNode(`${time} ${e.step} `));
  row.appendChild(s);
  const extra = [e.target, e.reason, e.message, e.duration_ms ? `${e.duration_ms}ms` : ""].filter(Boolean).join(" · ");
  if (extra) row.appendChild(document.createTextNode(` ${extra}`));
  list.appendChild(row);
  while (list.childNodes.length > MAX_LOG_ROWS) list.removeChild(list.firstChild);
  list.scrollTop = list.scrollHeight;
}

function clearLog() {
  $("log-list").textContent = "";
}

function toggleLog() {
  $("log").classList.toggle("hidden");
}

module.exports = { renderState, appendLog, clearLog, toggleLog };
