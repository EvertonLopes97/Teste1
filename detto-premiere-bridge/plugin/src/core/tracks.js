// @ts-check
"use strict";

const { TRACK_LAYOUT } = require("./constants");

/**
 * Resolve uma referência de track do plano ("V2", "B-ROLL", "b_roll", 1) para
 * a entrada do layout DETTO.
 *
 * @param {"video"|"audio"} kind
 * @param {string|number|undefined|null} ref
 * @returns {{id: string, index: number, role: string} | null}
 */
function resolveTrack(kind, ref) {
  const layout = TRACK_LAYOUT[kind];
  if (ref === undefined || ref === null || ref === "") return null;
  if (typeof ref === "number") {
    // número no plano = número humano (1 = V1/A1)
    return layout.find((t) => t.index === ref - 1) || null;
  }
  const key = normalizeRole(String(ref));
  return layout.find((t) => t.id === key || normalizeRole(t.role) === key) || null;
}

/** @param {string} s */
function normalizeRole(s) {
  return s.trim().toUpperCase().replace(/[\s_]+/g, "-");
}

/** Track de vídeo padrão para cortes (V1 PRESENTER). */
const DEFAULT_CUT_VIDEO_TRACK = "V1";
/** Track de áudio padrão para cortes (A1 VOICE). */
const DEFAULT_CUT_AUDIO_TRACK = "A1";

/**
 * Determina os índices de track de um corte.
 * @param {{track?: string|number, audioTrack?: string|number}} cut
 */
function tracksForCut(cut) {
  const video = resolveTrack("video", cut.track ?? DEFAULT_CUT_VIDEO_TRACK);
  const audio = resolveTrack("audio", cut.audioTrack ?? DEFAULT_CUT_AUDIO_TRACK);
  return { video, audio };
}

/** Quantidade mínima de tracks exigida pelo layout. */
function requiredTrackCounts() {
  return { video: TRACK_LAYOUT.video.length, audio: TRACK_LAYOUT.audio.length };
}

module.exports = {
  resolveTrack,
  tracksForCut,
  requiredTrackCounts,
  DEFAULT_CUT_VIDEO_TRACK,
  DEFAULT_CUT_AUDIO_TRACK,
};
