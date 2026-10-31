// @ts-check
"use strict";

const { LOG_STATUS } = require("./constants");

/** @typedef {{total: number, done: number, skipped: number, failed: number, fallback: number}} Counter */

/** @returns {Counter} */
function counter(total = 0) {
  return { total, done: 0, skipped: 0, failed: 0, fallback: 0 };
}

/**
 * Cria o relatório de execução de um job.
 * @param {string} jobId
 * @param {any} plan
 * @param {Date} startedAt
 */
function createReport(jobId, plan, startedAt) {
  const len = (/** @type {string} */ k) => (plan && Array.isArray(plan[k]) ? plan[k].length : 0);
  return {
    job_id: jobId,
    plan_name: (plan && plan.project && plan.project.name) || "",
    /** @type {"running"|"completed"|"completed_with_errors"|"failed"} */
    status: "running",
    started_at: startedAt.toISOString(),
    finished_at: "",
    duration_ms: 0,
    /** @type {{code: string, message: string} | null} */
    fatal: null,
    environment: /** @type {any} */ (null),
    project: { name: "", path: "", created: false, opened: false, backup: "" },
    sequence: { name: "", created: false, reused: false },
    summary: {
      media: { ...counter(len("media")), imported: 0, reused: 0, missing: 0 },
      cuts: counter(len("cuts")),
      markers: counter(len("markers")),
      graphics: counter(len("graphics")),
      vfx: counter(len("vfx")),
      effects: counter(len("effects")),
    },
    /** @type {Array<{code: string, path: string, message: string}>} */
    validation_warnings: [],
    /** @type {Array<{step: string, target?: string, reason?: string, message?: string}>} */
    fallbacks: [],
    /** @type {Array<{step: string, target?: string, reason?: string, message?: string}>} */
    errors: [],
  };
}

/** @typedef {ReturnType<typeof createReport>} ExecutionReport */

/**
 * Fecha o relatório consolidando erros e fallbacks registrados no log.
 * @param {ExecutionReport} report
 * @param {import("./logger").LogEntry[]} entries
 * @param {Date} finishedAt
 */
function finalizeReport(report, entries, finishedAt) {
  report.finished_at = finishedAt.toISOString();
  report.duration_ms = finishedAt.getTime() - new Date(report.started_at).getTime();
  const pick = (/** @type {import("./logger").LogEntry} */ e) => ({
    step: e.step,
    ...(e.target !== undefined ? { target: e.target } : {}),
    ...(e.reason !== undefined ? { reason: e.reason } : {}),
    ...(e.message !== undefined ? { message: e.message } : {}),
  });
  report.errors = entries.filter((e) => e.status === LOG_STATUS.ERROR).map(pick);
  report.fallbacks = entries.filter((e) => e.status === LOG_STATUS.FALLBACK).map(pick);
  if (report.fatal) report.status = "failed";
  else report.status = report.errors.length ? "completed_with_errors" : "completed";
  return report;
}

/**
 * Resumo legível do relatório para o painel.
 * @param {ExecutionReport} r
 */
function formatReport(r) {
  const s = r.summary;
  const line = (/** @type {string} */ label, /** @type {Counter} */ c, /** @type {string} */ doneLabel) =>
    `${label}: ${c.done}/${c.total} ${doneLabel}` +
    (c.skipped ? `, ${c.skipped} ignorados` : "") +
    (c.fallback ? `, ${c.fallback} fallback` : "") +
    (c.failed ? `, ${c.failed} com erro` : "");
  return [
    `Job: ${r.job_id} — ${r.status.toUpperCase()} (${(r.duration_ms / 1000).toFixed(1)}s)`,
    r.fatal ? `FALHA: [${r.fatal.code}] ${r.fatal.message}` : "",
    `Projeto: ${r.project.name || "-"}${r.project.created ? " (criado)" : ""}`,
    r.project.backup ? `Backup: ${r.project.backup}` : "",
    `Sequência: ${r.sequence.name || "-"}${r.sequence.created ? " (criada)" : r.sequence.reused ? " (reutilizada)" : ""}`,
    `Mídia: ${s.media.imported} importadas, ${s.media.reused} reutilizadas, ${s.media.missing} ausentes` +
      (s.media.failed ? `, ${s.media.failed} falharam` : ""),
    line("Cortes", s.cuts, "inseridos"),
    line("Markers", s.markers, "criados"),
    line("Graphics", s.graphics, "placeholders"),
    line("VFX", s.vfx, "placeholders"),
    line("Effects", s.effects, "aplicados"),
    `Erros: ${r.errors.length} | Fallbacks: ${r.fallbacks.length}`,
  ]
    .filter(Boolean)
    .join("\n");
}

module.exports = { createReport, finalizeReport, formatReport };
