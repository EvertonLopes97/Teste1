// @ts-check
"use strict";

const { MARKER_COLORS, GRAPHIC_TYPES, KNOWN_PLAN_KEYS, TIME_EPSILON } = require("./constants");
const { fpsEquals, isFrameAligned, COMMON_FPS } = require("./time");
const { normalizeForCompare } = require("./paths");
const { resolveTrack } = require("./tracks");

/**
 * @typedef {{code: string, path: string, message: string}} Issue
 * @typedef {{valid: boolean, errors: Issue[], warnings: Issue[]}} ValidationResult
 */

/**
 * Faz o parse do texto de um EDIT_PLAN sem lançar exceções.
 * @param {string} text
 * @returns {{ok: true, plan: any} | {ok: false, error: Issue}}
 */
function parseEditPlan(text) {
  if (typeof text !== "string" || text.trim() === "") {
    return { ok: false, error: { code: "EMPTY_PLAN", path: "$", message: "Arquivo de EDIT_PLAN vazio." } };
  }
  try {
    // remove BOM, comum em arquivos gerados no Windows
    const plan = JSON.parse(text.replace(/^﻿/, ""));
    return { ok: true, plan };
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return { ok: false, error: { code: "INVALID_JSON", path: "$", message: `JSON inválido: ${message}` } };
  }
}

/**
 * Valida a estrutura e a coerência de um EDIT_PLAN.
 * Erros bloqueiam a execução; avisos apenas informam.
 * @param {any} plan
 * @returns {ValidationResult}
 */
function validateEditPlan(plan) {
  /** @type {Issue[]} */
  const errors = [];
  /** @type {Issue[]} */
  const warnings = [];
  const err = (/** @type {string} */ code, /** @type {string} */ path, /** @type {string} */ message) =>
    errors.push({ code, path, message });
  const warn = (/** @type {string} */ code, /** @type {string} */ path, /** @type {string} */ message) =>
    warnings.push({ code, path, message });

  if (!isObject(plan)) {
    err("INVALID_ROOT", "$", "O EDIT_PLAN deve ser um objeto JSON.");
    return { valid: false, errors, warnings };
  }

  for (const key of Object.keys(plan)) {
    if (!KNOWN_PLAN_KEYS.includes(key)) warn("UNKNOWN_KEY", `$.${key}`, `Chave desconhecida "${key}" será ignorada.`);
  }

  // ---------- project ----------
  const project = plan.project;
  if (!isObject(project)) {
    err("MISSING_PROJECT", "$.project", "Campo obrigatório 'project' ausente ou inválido.");
  } else {
    requireString(project, "name", "$.project", err);
    requirePositiveNumber(project, "fps", "$.project", err);
    requirePositiveInt(project, "width", "$.project", err);
    requirePositiveInt(project, "height", "$.project", err);
    if (project.path !== undefined && !isNonEmptyString(project.path)) {
      err("INVALID_FIELD", "$.project.path", "'project.path' deve ser uma string.");
    }
  }

  // ---------- sequence ----------
  const sequence = plan.sequence;
  if (!isObject(sequence)) {
    err("MISSING_SEQUENCE", "$.sequence", "Campo obrigatório 'sequence' ausente ou inválido.");
  } else {
    requireString(sequence, "name", "$.sequence", err);
    requirePositiveNumber(sequence, "fps", "$.sequence", err);
    requirePositiveInt(sequence, "width", "$.sequence", err);
    requirePositiveInt(sequence, "height", "$.sequence", err);
    if (sequence.preset !== undefined && !isNonEmptyString(sequence.preset)) {
      err("INVALID_FIELD", "$.sequence.preset", "'sequence.preset' deve ser o caminho de um .sqpreset.");
    }
  }

  // ---------- coerência project × sequence ----------
  if (isObject(project) && isObject(sequence)) {
    if (isPositiveNumber(project.fps) && isPositiveNumber(sequence.fps) && !fpsEquals(project.fps, sequence.fps)) {
      err(
        "FPS_MISMATCH",
        "$.sequence.fps",
        `FPS incompatível: project.fps=${project.fps} e sequence.fps=${sequence.fps}.`
      );
    }
    if (
      isPositiveInt(project.width) &&
      isPositiveInt(sequence.width) &&
      (project.width !== sequence.width || project.height !== sequence.height)
    ) {
      warn(
        "RESOLUTION_MISMATCH",
        "$.sequence",
        `Resolução do projeto (${project.width}x${project.height}) difere da sequência (${sequence.width}x${sequence.height}).`
      );
    }
  }
  const fps = isObject(sequence) && isPositiveNumber(sequence.fps) ? sequence.fps : 0;
  if (fps && !COMMON_FPS.some((f) => fpsEquals(f, fps))) {
    warn("UNUSUAL_FPS", "$.sequence.fps", `FPS ${fps} não é um valor padrão de broadcast.`);
  }

  // ---------- media ----------
  /** @type {Map<string, any>} */
  const mediaById = new Map();
  if (!Array.isArray(plan.media)) {
    err("MISSING_MEDIA", "$.media", "Campo obrigatório 'media' deve ser um array.");
  } else {
    /** @type {Map<string, string>} */
    const idsByPath = new Map();
    plan.media.forEach((/** @type {any} */ m, /** @type {number} */ i) => {
      const p = `$.media[${i}]`;
      if (!isObject(m)) return err("INVALID_MEDIA", p, "Item de mídia deve ser um objeto.");
      const okId = requireString(m, "id", p, err);
      const okPath = requireString(m, "path", p, err);
      if (m.duration !== undefined && !isPositiveNumber(m.duration)) {
        err("INVALID_FIELD", `${p}.duration`, "'duration' deve ser um número positivo (segundos).");
      }
      if (okId) {
        if (mediaById.has(m.id)) err("DUPLICATE_MEDIA_ID", `${p}.id`, `ID de mídia duplicado: "${m.id}".`);
        else mediaById.set(m.id, m);
      }
      if (okPath) {
        const key = normalizeForCompare(m.path);
        const other = idsByPath.get(key);
        if (other !== undefined && other !== m.id) {
          warn(
            "DUPLICATE_MEDIA_PATH",
            `${p}.path`,
            `Arquivo duplicado: "${m.path}" já declarado como "${other}". Será importado uma única vez.`
          );
        } else {
          idsByPath.set(key, m.id);
        }
      }
    });
  }

  // ---------- cuts ----------
  const cuts = optionalArray(plan, "cuts", err);
  /** @type {Map<string, Array<{start: number, end: number, index: number}>>} */
  const occupied = new Map();
  /** @type {Set<string>} */
  const cutKeys = new Set();
  cuts.forEach((/** @type {any} */ c, /** @type {number} */ i) => {
    const p = `$.cuts[${i}]`;
    if (!isObject(c)) return err("INVALID_CUT", p, "Corte deve ser um objeto.");
    requireString(c, "source", p, err);
    const okStart = requireNonNegativeNumber(c, "start", p, err);
    const okEnd = requireNonNegativeNumber(c, "end", p, err);
    const okTimeline = requireNonNegativeNumber(c, "timeline", p, err);

    if (isNonEmptyString(c.source) && plan.media && !mediaById.has(c.source)) {
      err("UNKNOWN_MEDIA_REFERENCE", `${p}.source`, `Corte referencia mídia inexistente: "${c.source}".`);
    }
    if (okStart && okEnd && c.end <= c.start) {
      err("INVALID_CUT_RANGE", p, `Intervalo inválido: end (${c.end}) deve ser maior que start (${c.start}).`);
    }
    const media = mediaById.get(c.source);
    if (okEnd && media && isPositiveNumber(media.duration) && c.end > media.duration + TIME_EPSILON) {
      err(
        "CUT_OUT_OF_RANGE",
        `${p}.end`,
        `Corte fora do intervalo: end=${c.end}s excede a duração da mídia "${c.source}" (${media.duration}s).`
      );
    }
    const vTrack = resolveTrack("video", c.track ?? "V1");
    if (!vTrack) err("UNKNOWN_TRACK", `${p}.track`, `Track de vídeo desconhecida: "${c.track}".`);
    if (c.audioTrack !== undefined && c.audioTrack !== null && !resolveTrack("audio", c.audioTrack)) {
      err("UNKNOWN_TRACK", `${p}.audioTrack`, `Track de áudio desconhecida: "${c.audioTrack}".`);
    }

    if (fps && okStart && okEnd && okTimeline) {
      if (![c.start, c.end, c.timeline].every((t) => isFrameAligned(t, fps))) {
        warn("NOT_FRAME_ALIGNED", p, `Tempos do corte não alinhados a ${fps}fps; serão ajustados ao frame mais próximo.`);
      }
    }

    if (okStart && okEnd && okTimeline && vTrack && c.end > c.start) {
      const key = [c.source, c.start, c.end, c.timeline, vTrack.id].join("|");
      if (cutKeys.has(key)) {
        warn("DUPLICATE_CUT", p, "Corte idêntico declarado mais de uma vez; será inserido apenas uma vez.");
        return;
      }
      cutKeys.add(key);
      const tStart = c.timeline;
      const tEnd = c.timeline + (c.end - c.start);
      const list = occupied.get(vTrack.id) || [];
      const clash = list.find((o) => tStart < o.end - TIME_EPSILON && tEnd > o.start + TIME_EPSILON);
      if (clash) {
        warn(
          "CUT_OVERLAP",
          p,
          `Corte sobrepõe o corte #${clash.index} na track ${vTrack.id}; o último sobrescreve o anterior.`
        );
      }
      list.push({ start: tStart, end: tEnd, index: i });
      occupied.set(vTrack.id, list);
    }
  });

  // ---------- markers ----------
  const markers = optionalArray(plan, "markers", err);
  /** @type {Set<string>} */
  const markerKeys = new Set();
  markers.forEach((/** @type {any} */ m, /** @type {number} */ i) => {
    const p = `$.markers[${i}]`;
    if (!isObject(m)) return err("INVALID_MARKER", p, "Marker deve ser um objeto.");
    const okTime = requireNonNegativeNumber(m, "time", p, err);
    const okName = requireString(m, "name", p, err);
    if (m.duration !== undefined && !isNonNegativeNumber(m.duration)) {
      err("INVALID_FIELD", `${p}.duration`, "'duration' deve ser >= 0.");
    }
    if (m.color !== undefined && !(String(m.color).toLowerCase() in MARKER_COLORS)) {
      warn("UNKNOWN_MARKER_COLOR", `${p}.color`, `Cor "${m.color}" não suportada; será usada a cor padrão.`);
    }
    if (okTime && okName) {
      const key = `${m.name}|${m.time}`;
      if (markerKeys.has(key)) warn("DUPLICATE_MARKER", p, `Marker "${m.name}" em ${m.time}s duplicado; será criado uma vez.`);
      markerKeys.add(key);
    }
  });

  // ---------- graphics ----------
  const graphics = optionalArray(plan, "graphics", err);
  graphics.forEach((/** @type {any} */ g, /** @type {number} */ i) => {
    const p = `$.graphics[${i}]`;
    if (!isObject(g)) return err("INVALID_GRAPHIC", p, "Graphic deve ser um objeto.");
    requireString(g, "type", p, err);
    requireNonNegativeNumber(g, "start", p, err);
    requirePositiveNumber(g, "duration", p, err);
    if (g.text !== undefined && typeof g.text !== "string") err("INVALID_FIELD", `${p}.text`, "'text' deve ser string.");
    if (isNonEmptyString(g.type) && !GRAPHIC_TYPES.includes(g.type)) {
      warn("UNKNOWN_GRAPHIC_TYPE", `${p}.type`, `Tipo de graphic "${g.type}" desconhecido; será tratado como genérico.`);
    }
  });

  // ---------- vfx ----------
  const vfx = optionalArray(plan, "vfx", err);
  vfx.forEach((/** @type {any} */ v, /** @type {number} */ i) => {
    const p = `$.vfx[${i}]`;
    if (!isObject(v)) return err("INVALID_VFX", p, "VFX deve ser um objeto.");
    requireNonNegativeNumber(v, "start", p, err);
    requirePositiveNumber(v, "duration", p, err);
    if (!isNonEmptyString(v.name) && !isNonEmptyString(v.description)) {
      err("MISSING_FIELD", p, "VFX precisa de 'name' ou 'description'.");
    }
  });

  // ---------- effects ----------
  const effects = optionalArray(plan, "effects", err);
  effects.forEach((/** @type {any} */ e, /** @type {number} */ i) => {
    const p = `$.effects[${i}]`;
    if (!isObject(e)) return err("INVALID_EFFECT", p, "Efeito deve ser um objeto.");
    requireString(e, "name", p, err);
  });

  return { valid: errors.length === 0, errors, warnings };
}

// ---------------------------------------------------------------- helpers

/** @param {any} v */
function isObject(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}
/** @param {any} v */
function isNonEmptyString(v) {
  return typeof v === "string" && v.trim() !== "";
}
/** @param {any} v */
function isFiniteNumber(v) {
  return typeof v === "number" && Number.isFinite(v);
}
/** @param {any} v */
function isPositiveNumber(v) {
  return isFiniteNumber(v) && v > 0;
}
/** @param {any} v */
function isNonNegativeNumber(v) {
  return isFiniteNumber(v) && v >= 0;
}
/** @param {any} v */
function isPositiveInt(v) {
  return Number.isInteger(v) && v > 0;
}

/** @typedef {(code: string, path: string, message: string) => void} Reporter */

/** @param {any} obj @param {string} key @param {string} base @param {Reporter} err */
function requireString(obj, key, base, err) {
  if (!isNonEmptyString(obj[key])) {
    err(obj[key] === undefined ? "MISSING_FIELD" : "INVALID_FIELD", `${base}.${key}`, `'${key}' deve ser uma string não vazia.`);
    return false;
  }
  return true;
}
/** @param {any} obj @param {string} key @param {string} base @param {Reporter} err */
function requirePositiveNumber(obj, key, base, err) {
  if (!isPositiveNumber(obj[key])) {
    err(obj[key] === undefined ? "MISSING_FIELD" : "INVALID_FIELD", `${base}.${key}`, `'${key}' deve ser um número > 0.`);
    return false;
  }
  return true;
}
/** @param {any} obj @param {string} key @param {string} base @param {Reporter} err */
function requireNonNegativeNumber(obj, key, base, err) {
  if (!isNonNegativeNumber(obj[key])) {
    err(obj[key] === undefined ? "MISSING_FIELD" : "INVALID_FIELD", `${base}.${key}`, `'${key}' deve ser um número >= 0.`);
    return false;
  }
  return true;
}
/** @param {any} obj @param {string} key @param {string} base @param {Reporter} err */
function requirePositiveInt(obj, key, base, err) {
  if (!isPositiveInt(obj[key])) {
    err(obj[key] === undefined ? "MISSING_FIELD" : "INVALID_FIELD", `${base}.${key}`, `'${key}' deve ser um inteiro > 0.`);
    return false;
  }
  return true;
}
/** @param {any} plan @param {string} key @param {Reporter} err @returns {any[]} */
function optionalArray(plan, key, err) {
  if (plan[key] === undefined) return [];
  if (!Array.isArray(plan[key])) {
    err("INVALID_FIELD", `$.${key}`, `'${key}' deve ser um array.`);
    return [];
  }
  return plan[key];
}

module.exports = { parseEditPlan, validateEditPlan };
