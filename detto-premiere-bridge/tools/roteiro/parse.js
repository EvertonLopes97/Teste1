// @ts-check
"use strict";

/**
 * Parser do formato de roteiro de edição DETTO:
 *
 *   =====
 *    BLOCO 1 — A ESTREIA (2005)
 *   =====
 *   >>> LINHA DO TEMPO avança para 2006
 *   [00:55 – 01:08]
 *   FALA: "..."
 *   VISUAL: ...
 *   TELA: ...
 *   GRÁFICO: ...
 *   SFX: ...
 *   EFEITO: ...
 *   MÚSICA: ...
 *   >>> OBS: ...
 *
 * mais as seções "CORTES VERTICAIS" e "ERRATA".
 */

/**
 * @typedef {Object} Segment
 * @property {number} start
 * @property {number} end
 * @property {string} block
 * @property {Record<string, string>} fields   FALA, VISUAL, TELA, GRAFICO, SFX, EFEITO, MUSICA
 * @property {string[]} notes                   linhas ">>>" dentro do segmento (OBS)
 * @property {string[]} events                  linhas ">>>" logo antes do segmento (linha do tempo, música)
 *
 * @typedef {Object} Roteiro
 * @property {string} title
 * @property {string[]} blocks
 * @property {Segment[]} segments
 * @property {Array<{index: number, title: string, ranges: Array<{start: number, end: number}>, hook: string}>} verticalCuts
 * @property {Array<{heard: string, correct: string}>} errata
 * @property {Array<{time: number, text: string}>} timedNotes   notas gerais com [mm:ss] (ex.: palavrão)
 */

const FIELD_KEYS = {
  FALA: "FALA",
  VISUAL: "VISUAL",
  TELA: "TELA",
  "GRÁFICO": "GRAFICO",
  "GRÁFICO PRINCIPAL": "GRAFICO",
  GRAFICO: "GRAFICO",
  SFX: "SFX",
  EFEITO: "EFEITO",
  "MÚSICA": "MUSICA",
  MUSICA: "MUSICA",
};

const RANGE_RE = /\[(\d{1,2}):(\d{2})(?:\.(\d+))?\s*[–—-]\s*(\d{1,2}):(\d{2})(?:\.(\d+))?\]/;
const FIELD_RE = /^(FALA|VISUAL|TELA|GR[ÁA]FICO(?: PRINCIPAL)?|SFX|EFEITO|M[ÚU]SICA)\s*:\s*(.*)$/;

/** @param {string} m @param {string} s @param {string|undefined} frac */
function toSeconds(m, s, frac) {
  return Number(m) * 60 + Number(s) + (frac ? Number(`0.${frac}`) : 0);
}

/**
 * Remove escapes de Markdown (quando o texto vem exportado do Drive) e
 * emojis corrompidos (UTF-8 lido como Latin-1, ex.: "ð¤").
 * @param {string} text
 */
function normalizeText(text) {
  return text
    .replace(/^﻿/, "")
    .replace(/\r\n?/g, "\n")
    .replace(/\\([[\]\-~!*&=>#_])/g, "$1")
    .replace(/ð[\u0080-¿]{0,3}/g, "")
    .replace(/[âã][\u0080-\u009F][\u0080-¿]/g, "");
}

/**
 * @param {string} raw
 * @returns {Roteiro}
 */
function parseRoteiro(raw) {
  const lines = normalizeText(raw).split("\n");
  /** @type {Roteiro} */
  const out = { title: "", blocks: [], segments: [], verticalCuts: [], errata: [], timedNotes: [] };
  const isRule = (/** @type {string|undefined} */ l) => !!l && /^\s*={5,}\s*$/.test(l);

  let block = "";
  let section = "";
  /** @type {Segment|null} */
  let seg = null;
  /** @type {string|null} */
  let lastField = null;
  /** @type {string[]} */
  let pendingEvents = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    // título: primeira linha depois da primeira régua
    if (!out.title && isRule(lines[i - 1]) && trimmed) {
      const m = trimmed.match(/"([^"]+)"/);
      out.title = m ? m[1] : trimmed;
      section = "PREAMBLE";
      continue;
    }
    // cabeçalho de seção entre réguas "====="
    if (out.title && isRule(lines[i - 1]) && trimmed && !isRule(line) && isRule(lines[i + 1])) {
      seg = null;
      lastField = null;
      if (/CORTES VERTICAIS/i.test(trimmed)) section = "VERTICAL";
      else if (/ERRATA/i.test(trimmed)) section = "ERRATA";
      else if (/LISTA DE SFX/i.test(trimmed)) section = "IGNORE";
      else {
        section = "BLOCK";
        block = trimmed;
        out.blocks.push(trimmed);
      }
      continue;
    }
    if (isRule(line)) continue;

    if (section === "PREAMBLE" || section === "") {
      // notas gerais com horário, ex.: "PALAVRÃO: em [07:05] ..."
      const note = RANGE_RE.test(trimmed) ? null : trimmed.match(/\[(\d{1,2}):(\d{2})\]/);
      if (note) out.timedNotes.push({ time: toSeconds(note[1], note[2], undefined), text: trimmed.replace(/^-\s*/, "") });
      continue;
    }

    if (section === "VERTICAL") {
      const m = trimmed.match(/^(\d+)\.\s*"([^"]+)"\s*:\s*(.*)$/);
      if (m) {
        /** @type {Array<{start: number, end: number}>} */
        const ranges = [];
        const re = new RegExp(RANGE_RE.source, "g");
        let r;
        while ((r = re.exec(m[3]))) ranges.push({ start: toSeconds(r[1], r[2], r[3]), end: toSeconds(r[4], r[5], r[6]) });
        const hook = (m[3].match(/Gancho[^:]*:\s*"([^"]+)"/i) || [])[1] || "";
        out.verticalCuts.push({ index: Number(m[1]), title: m[2], ranges, hook });
      }
      continue;
    }
    if (section === "ERRATA") {
      const m = trimmed.match(/^-\s*(.+?)\s*→\s*(.+)$/);
      if (m) out.errata.push({ heard: m[1].replace(/"/g, ""), correct: m[2] });
      continue;
    }
    if (section !== "BLOCK") continue;

    const range = trimmed.match(RANGE_RE);
    if (range && trimmed.startsWith("[")) {
      seg = {
        start: toSeconds(range[1], range[2], range[3]),
        end: toSeconds(range[4], range[5], range[6]),
        block,
        fields: {},
        notes: [],
        events: pendingEvents,
      };
      pendingEvents = [];
      out.segments.push(seg);
      lastField = null;
      continue;
    }
    if (trimmed.startsWith(">>>")) {
      const text = trimmed.replace(/^>+\s*/, "");
      if (seg && lastField) {
        // OBS dentro do segmento (pode continuar nas linhas ">>>" seguintes)
        if (/^OBS/i.test(text) || seg.notes.length === 0) seg.notes.push(text);
        else seg.notes[seg.notes.length - 1] += ` ${text}`;
      } else {
        pendingEvents.push(text);
      }
      continue;
    }
    const field = trimmed.match(FIELD_RE);
    if (field && seg) {
      const key = /** @type {Record<string, string>} */ (FIELD_KEYS)[field[1]] || field[1];
      seg.fields[key] = seg.fields[key] ? `${seg.fields[key]} ${field[2]}` : field[2];
      lastField = key;
      continue;
    }
    if (trimmed && seg && lastField) {
      // em TELA/GRÁFICO cada linha extra é um item (listas de placas, chaveamento, ficha)
      const sep = lastField === "TELA" || lastField === "GRAFICO" ? "\n" : " ";
      seg.fields[lastField] += `${sep}${trimmed}`;
    }
  }
  return out;
}

module.exports = { parseRoteiro, normalizeText, toSeconds };
