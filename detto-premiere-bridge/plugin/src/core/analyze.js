// @ts-check
"use strict";

const { validateEditPlan } = require("./schema");
const { normalizeForCompare } = require("./paths");
const { toTimecode } = require("./time");

/**
 * @typedef {Object} PlanPreview
 * @property {{cuts: number, markers: number, graphics: number, vfx: number, effects: number, assets: number}} counts
 * @property {number} timelineDuration  duração estimada da timeline (s)
 * @property {string} timelineTimecode
 * @property {string[]} missingMedia    ids de mídia cujo arquivo não existe
 * @property {import("./schema").ValidationResult} validation
 * @property {boolean} canExecute
 */

/**
 * Gera o resumo exibido no MODO PREVIEW antes de executar.
 * @param {any} plan
 * @param {{exists: (path: string) => Promise<boolean>}} [fs] se informado, verifica a existência das mídias
 * @returns {Promise<PlanPreview>}
 */
async function analyzePlan(plan, fs) {
  const validation = validateEditPlan(plan);
  const safe = plan && typeof plan === "object" ? plan : {};
  const arr = (/** @type {string} */ k) => (Array.isArray(safe[k]) ? safe[k] : []);

  const media = arr("media");
  const uniquePaths = new Set(media.filter((m) => m && m.path).map((m) => normalizeForCompare(m.path)));

  let timelineDuration = 0;
  for (const c of arr("cuts")) {
    if (c && typeof c.timeline === "number" && typeof c.end === "number" && typeof c.start === "number") {
      timelineDuration = Math.max(timelineDuration, c.timeline + (c.end - c.start));
    }
  }
  for (const g of [...arr("graphics"), ...arr("vfx")]) {
    if (g && typeof g.start === "number" && typeof g.duration === "number") {
      timelineDuration = Math.max(timelineDuration, g.start + g.duration);
    }
  }

  /** @type {string[]} */
  const missingMedia = [];
  if (fs) {
    for (const m of media) {
      if (m && typeof m.path === "string" && !(await fs.exists(m.path))) missingMedia.push(m.id);
    }
  }

  const fps = (safe.sequence && safe.sequence.fps) || 30;
  return {
    counts: {
      cuts: arr("cuts").length,
      markers: arr("markers").length,
      graphics: arr("graphics").length,
      vfx: arr("vfx").length,
      effects: arr("effects").length,
      assets: uniquePaths.size,
    },
    timelineDuration,
    timelineTimecode: toTimecode(timelineDuration, fps),
    missingMedia,
    validation,
    canExecute: validation.valid,
  };
}

/**
 * Texto curto do preview, no formato pedido pelo painel.
 * @param {PlanPreview} preview
 */
function formatPreview(preview) {
  const c = preview.counts;
  const lines = [
    `Cortes: ${c.cuts}`,
    `Markers: ${c.markers}`,
    `Graphics: ${c.graphics}`,
    `VFX: ${c.vfx}`,
    `Effects: ${c.effects}`,
    `Assets: ${c.assets}`,
    `Duração: ${preview.timelineTimecode}`,
  ];
  if (preview.missingMedia.length) lines.push(`Mídias ausentes: ${preview.missingMedia.join(", ")}`);
  if (preview.validation.errors.length) lines.push(`Erros de validação: ${preview.validation.errors.length}`);
  if (preview.validation.warnings.length) lines.push(`Avisos: ${preview.validation.warnings.length}`);
  return lines.join("\n");
}

module.exports = { analyzePlan, formatPreview };
