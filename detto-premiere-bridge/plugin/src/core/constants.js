// @ts-check
"use strict";

/** Status global do painel / do executor. */
const STATUS = Object.freeze({
  IDLE: "IDLE",
  PROCESSING: "PROCESSING",
  PAUSED: "PAUSED",
  COMPLETE: "COMPLETE",
  ERROR: "ERROR",
});

/** Status de cada entrada de log. */
const LOG_STATUS = Object.freeze({
  SUCCESS: "success",
  ERROR: "error",
  WARNING: "warning",
  FALLBACK: "fallback",
  SKIPPED: "skipped",
  INFO: "info",
});

/** Passos do pipeline, na ordem em que são executados. */
const STEPS = Object.freeze({
  LOAD_PLAN: "LOAD_PLAN",
  VALIDATE_PLAN: "VALIDATE_PLAN",
  DETECT_ENVIRONMENT: "DETECT_ENVIRONMENT",
  CHECK_MEDIA: "CHECK_MEDIA",
  ENSURE_PROJECT: "ENSURE_PROJECT",
  BACKUP_PROJECT: "BACKUP_PROJECT",
  IMPORT_MEDIA: "IMPORT_MEDIA",
  ENSURE_SEQUENCE: "ENSURE_SEQUENCE",
  ENSURE_TRACKS: "ENSURE_TRACKS",
  PLACE_CLIPS: "PLACE_CLIPS",
  CREATE_MARKERS: "CREATE_MARKERS",
  GRAPHICS_PLACEHOLDERS: "GRAPHICS_PLACEHOLDERS",
  VFX_PLACEHOLDERS: "VFX_PLACEHOLDERS",
  APPLY_EFFECTS: "APPLY_EFFECTS",
  SAVE_PROJECT: "SAVE_PROJECT",
  JOB_QUEUE: "JOB_QUEUE",
  RENDER: "RENDER",
});

/**
 * Estrutura de tracks padrão do DETTO.
 * `index` é zero-based, como na API do Premiere (V1 = 0).
 */
const TRACK_LAYOUT = Object.freeze({
  video: Object.freeze([
    { id: "V1", index: 0, role: "PRESENTER" },
    { id: "V2", index: 1, role: "B-ROLL" },
    { id: "V3", index: 2, role: "GRAPHICS" },
    { id: "V4", index: 3, role: "OVERLAYS" },
    { id: "V5", index: 4, role: "VFX REFERENCES" },
  ]),
  audio: Object.freeze([
    { id: "A1", index: 0, role: "VOICE" },
    { id: "A2", index: 1, role: "MUSIC" },
    { id: "A3", index: 2, role: "SFX" },
    { id: "A4", index: 3, role: "AMBIENCE" },
  ]),
});

/** Índices de cor de marker do Premiere Pro. */
const MARKER_COLORS = Object.freeze({
  green: 0,
  red: 1,
  purple: 2,
  magenta: 2,
  orange: 3,
  yellow: 4,
  white: 5,
  blue: 6,
  cyan: 7,
});

/** Tipos de graphics aceitos no plano (por enquanto viram placeholders). */
const GRAPHIC_TYPES = Object.freeze([
  "headline",
  "lower_third",
  "title",
  "caption",
  "logo",
  "overlay",
  "generic",
  "date_stamp", // carimbo de data/local
  "scoreboard", // placa de placar
  "counter", // contador / cronômetro / relógio de jogo
  "cta", // inscreva-se, comente, compartilhe
  "timeline_bar", // linha do tempo no rodapé
  "stat_card", // ficha / estante de troféus
]);

/** Cores padrão de placeholders. */
const PLACEHOLDER_COLORS = Object.freeze({ graphics: "yellow", vfx: "purple" });

/** Chaves de topo conhecidas no EDIT_PLAN. */
const KNOWN_PLAN_KEYS = Object.freeze([
  "version",
  "job_id",
  "project",
  "media",
  "sequence",
  "cuts",
  "markers",
  "graphics",
  "vfx",
  "effects",
  "audio",
  "captions",
  "export",
  "meta",
]);

/** Tolerância (em segundos) ao comparar tempos de timeline. */
const TIME_EPSILON = 0.0005;

module.exports = {
  STATUS,
  LOG_STATUS,
  STEPS,
  TRACK_LAYOUT,
  MARKER_COLORS,
  GRAPHIC_TYPES,
  PLACEHOLDER_COLORS,
  KNOWN_PLAN_KEYS,
  TIME_EPSILON,
};
