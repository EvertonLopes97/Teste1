// @ts-check
"use strict";

const { STEPS, LOG_STATUS, MARKER_COLORS, PLACEHOLDER_COLORS } = require("../constants");
const { snapToFrame, timesEqual } = require("../time");
const { ApiNotAvailableError } = require("../errors");

/**
 * @typedef {Object} MarkerJob
 * @property {string} step
 * @property {string} target
 * @property {import("../report").ExecutionReport["summary"]["markers"]} counter
 * @property {import("../types").MarkerRequest} request
 * @property {string|undefined} requestedColor
 */

/**
 * Carrega (uma vez) os markers existentes, para não duplicar.
 * @param {import("../executor").ExecutionContext} ctx
 */
async function loadExistingMarkers(ctx) {
  if (ctx.state.existingMarkers) return ctx.state.existingMarkers;
  /** @type {Array<{name: string, start: number}>} */
  let list = [];
  try {
    list = await ctx.host.listMarkers(ctx.state.sequence);
  } catch (_) {
    list = [];
  }
  ctx.state.existingMarkers = list;
  return list;
}

/**
 * @param {import("../executor").ExecutionContext} ctx
 * @param {MarkerJob} job
 */
async function addMarker(ctx, job) {
  const { host, logger, state } = ctx;
  const t0 = ctx.now();
  const halfFrame = 0.5 / ctx.plan.sequence.fps;
  const existing = await loadExistingMarkers(ctx);
  const { request: m, counter } = job;

  if (existing.some((e) => e.name === m.name && timesEqual(e.start, m.start, halfFrame))) {
    counter.skipped++;
    logger.log(job.step, LOG_STATUS.SKIPPED, { duration_ms: ctx.now() - t0, target: job.target, reason: "already_exists" });
    return;
  }
  try {
    const result = await host.addMarker(state.sequence, m);
    existing.push({ name: m.name, start: m.start });
    counter.done++;
    logger.log(job.step, LOG_STATUS.SUCCESS, {
      duration_ms: ctx.now() - t0,
      target: job.target,
      message: `"${m.name}" @ ${m.start.toFixed(3)}s`,
    });
    if (job.requestedColor && m.colorIndex !== null && !result.colorApplied) {
      logger.log(job.step, LOG_STATUS.FALLBACK, {
        target: job.target,
        reason: "marker_color_not_available",
        message: `Cor "${job.requestedColor}" não aplicada; marker criado com a cor padrão.`,
      });
    }
  } catch (e) {
    const unavailable = e instanceof ApiNotAvailableError;
    if (unavailable) counter.fallback++;
    else counter.failed++;
    logger.log(job.step, unavailable ? LOG_STATUS.FALLBACK : LOG_STATUS.ERROR, {
      duration_ms: ctx.now() - t0,
      target: job.target,
      reason: unavailable ? /** @type {any} */ (e).code : "marker_failed",
      message: e instanceof Error ? e.message : String(e),
    });
  }
}

/** @param {string|undefined} color */
function colorIndex(color) {
  if (!color) return null;
  const idx = /** @type {Record<string, number>} */ (MARKER_COLORS)[String(color).toLowerCase()];
  return idx === undefined ? null : idx;
}

/** @param {import("../executor").ExecutionContext} ctx */
async function createMarkers(ctx) {
  const fps = ctx.plan.sequence.fps;
  const markers = Array.isArray(ctx.plan.markers) ? ctx.plan.markers : [];
  for (let i = 0; i < markers.length; i++) {
    await ctx.pause.checkpoint();
    const m = markers[i];
    await addMarker(ctx, {
      step: STEPS.CREATE_MARKERS,
      target: m.id ? String(m.id) : `markers[${i}]`,
      counter: ctx.report.summary.markers,
      requestedColor: m.color,
      request: {
        name: m.name,
        start: snapToFrame(m.time, fps),
        duration: snapToFrame(m.duration || 0, fps),
        comment: m.comment || "",
        colorIndex: colorIndex(m.color),
      },
    });
  }
}

/**
 * Graphics ainda não têm API confiável para MOGRT/texto via UXP:
 * cada graphic vira um marker-placeholder com duração e os dados no comentário,
 * pronto para o editor (ou fase 2 do Bridge) substituir pelo template real.
 *
 * @param {import("../executor").ExecutionContext} ctx
 */
async function createGraphicsPlaceholders(ctx) {
  const fps = ctx.plan.sequence.fps;
  const graphics = Array.isArray(ctx.plan.graphics) ? ctx.plan.graphics : [];
  for (let i = 0; i < graphics.length; i++) {
    await ctx.pause.checkpoint();
    const g = graphics[i];
    const label = g.text ? `: ${g.text}` : "";
    await addMarker(ctx, {
      step: STEPS.GRAPHICS_PLACEHOLDERS,
      target: g.id ? String(g.id) : `graphics[${i}]`,
      counter: ctx.report.summary.graphics,
      requestedColor: PLACEHOLDER_COLORS.graphics,
      request: {
        name: `GFX ${String(g.type).toUpperCase()}${label}`,
        start: snapToFrame(g.start, fps),
        duration: snapToFrame(g.duration, fps),
        comment: JSON.stringify({ detto: "graphic_placeholder", track: "V3 GRAPHICS", ...g }),
        colorIndex: colorIndex(PLACEHOLDER_COLORS.graphics),
      },
    });
  }
}

/**
 * VFX também viram markers-placeholder (referência para a track V5 VFX REFERENCES).
 * @param {import("../executor").ExecutionContext} ctx
 */
async function createVfxPlaceholders(ctx) {
  const fps = ctx.plan.sequence.fps;
  const vfx = Array.isArray(ctx.plan.vfx) ? ctx.plan.vfx : [];
  for (let i = 0; i < vfx.length; i++) {
    await ctx.pause.checkpoint();
    const v = vfx[i];
    await addMarker(ctx, {
      step: STEPS.VFX_PLACEHOLDERS,
      target: v.id ? String(v.id) : `vfx[${i}]`,
      counter: ctx.report.summary.vfx,
      requestedColor: PLACEHOLDER_COLORS.vfx,
      request: {
        name: `VFX: ${v.name || v.description}`,
        start: snapToFrame(v.start, fps),
        duration: snapToFrame(v.duration, fps),
        comment: JSON.stringify({ detto: "vfx_placeholder", track: "V5 VFX REFERENCES", ...v }),
        colorIndex: colorIndex(PLACEHOLDER_COLORS.vfx),
      },
    });
  }
}

module.exports = { createMarkers, createGraphicsPlaceholders, createVfxPlaceholders, colorIndex };
