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
 * @property {string} [sub]                     sub-bloco ("POLÊMICA 1: ...")
 * @property {boolean} [opensSub]               primeiro trecho do sub-bloco
 * @property {string} [improv]                  "[IMPROVISA: ...]": fala livre que não está no roteiro
 * @property {boolean} [header]                 trecho criado a partir do cabeçalho do bloco
 *
 * @typedef {Object} Roteiro
 * @property {string} title
 * @property {string[]} blocks
 * @property {Segment[]} segments
 * @property {Array<{index: number, title: string, ranges: Array<{start: number, end: number}>, hook: string}>} verticalCuts
 * @property {Array<{heard: string, correct: string}>} errata
 * @property {Array<{time: number, text: string}>} timedNotes   notas gerais com [mm:ss] (ex.: palavrão)
 * @property {string} [assets]                  texto da "LISTA DE ASSETS" (times dos jogadores)
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
  // formato com modos de edição (MODO: [CAM] / [CAM+MG] / [MG+VO] / [LANCE+VO])
  MODO: "MODO",
  MG: "MG",
  VFX: "VFX",
  LANCE: "LANCE",
  TELESTRATOR: "TELESTRATOR",
  "TRANSIÇÃO": "TRANSICAO",
  TRANSICAO: "TRANSICAO",
  TRILHA: "TRILHA",
  NOTA: "NOTA",
  "NOTA PRO EDITOR": "NOTA",
};

const RANGE_RE = /\[(\d{1,2}):(\d{2})(?:\.(\d+))?\s*[–—-]\s*(\d{1,2}):(\d{2})(?:\.(\d+))?\]/;
/** intervalo entre parênteses no cabeçalho do bloco: "GANCHO (0:00 – 0:40)" */
const HEAD_RANGE_RE = /\((\d{1,2}):(\d{2})\s*[–—-]\s*(\d{1,2}):(\d{2})\)/;
const FIELD_RE = /^(FALA|VISUAL|TELA|GR[ÁA]FICO(?: PRINCIPAL)?|SFX|EFEITO|M[ÚU]SICA|MODO|MG|VFX|LANCE|TELESTRATOR|TRANSI[ÇC][ÃA]O|TRILHA|NOTA(?: PRO EDITOR)?)\s*(?:\([^)]*\))?\s*:\s*(.*)$/;
/** campos que só ajustam o bloco (não pedem nada na tela) */
const BLOCK_ONLY = new Set(["MODO", "TRILHA", "MUSICA", "NOTA"]);
/** campos que viram lista (uma linha = um item) */
const LIST_FIELDS = new Set(["TELA", "GRAFICO", "MG"]);

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
  const out = { title: "", blocks: [], segments: [], verticalCuts: [], errata: [], timedNotes: [], assets: "" };
  const isRule = (/** @type {string|undefined} */ l) => !!l && /^\s*={5,}\s*$/.test(l);

  let block = "";
  let section = "";
  /** @type {any} */
  let seg = null;
  /** @type {string|null} */
  let lastField = null;
  /** @type {string[]} */
  let pendingEvents = [];
  /** intervalo e campos padrão do bloco atual (cabeçalho "BLOCO (1:40 – 2:50)  MODO: [CAM]") */
  /** @type {{start: number, end: number}|null} */
  let blockRange = null;
  /** @type {Record<string, string>} */
  let blockDefaults = {};
  /** @type {any} */
  let headerSeg = null; // trecho criado a partir do cabeçalho (campos antes do 1º [tempo])
  let sub = "";
  let opensSub = false;
  /** @type {string[]} */
  let vertBuf = [];

  const flushVertical = () => {
    const txt = vertBuf.join(" ").replace(/\s+/g, " ").trim();
    vertBuf = [];
    const m = txt.match(/^(\d+)\.\s*"([^"]+)"\s*[:—–-]+\s*(.*)$/);
    if (!m) return;
    /** @type {Array<{start: number, end: number}>} */
    const ranges = [];
    const re = new RegExp(RANGE_RE.source, "g");
    let r;
    while ((r = re.exec(m[3]))) ranges.push({ start: toSeconds(r[1], r[2], r[3]), end: toSeconds(r[4], r[5], r[6]) });
    const hook = (m[3].match(/Gancho[^:]*:\s*"([^"]+)"/i) || [])[1] || "";
    out.verticalCuts.push({ index: Number(m[1]), title: m[2], ranges, hook });
  };
  /** trecho do cabeçalho só com MODO/TRILHA vira padrão do bloco */
  const settleHeader = () => {
    if (!headerSeg) return;
    const keys = Object.keys(headerSeg.fields);
    for (const k of keys) if (BLOCK_ONLY.has(k)) blockDefaults[k] = headerSeg.fields[k];
    if (keys.every((k) => BLOCK_ONLY.has(k))) out.segments.splice(out.segments.indexOf(headerSeg), 1);
    headerSeg = null;
  };
  /** @param {string} key @param {string} value */
  const setField = (key, value) => {
    if (!seg) return;
    seg.fields[key] = seg.fields[key] ? `${seg.fields[key]}${LIST_FIELDS.has(key) ? "\n" : " "}${value}` : value;
    lastField = key;
  };

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
      if (section === "VERTICAL") flushVertical();
      settleHeader();
      seg = null;
      lastField = null;
      sub = "";
      blockDefaults = {};
      blockRange = null;
      if (/CORTES VERTICAIS/i.test(trimmed)) section = "VERTICAL";
      else if (/ERRATA/i.test(trimmed)) section = "ERRATA";
      else if (/LISTA DE ASSETS|ASSETS/i.test(trimmed)) section = "ASSETS";
      else if (/LISTA DE SFX|SFX PRA BAIXAR|CONFER[ÊE]NCIA|FONTES/i.test(trimmed)) section = "IGNORE";
      else {
        section = "BLOCK";
        const hr = trimmed.match(HEAD_RANGE_RE);
        blockRange = hr ? { start: toSeconds(hr[1], hr[2], undefined), end: toSeconds(hr[3], hr[4], undefined) } : null;
        // "CTA 1 (4:00 – 4:15)  MODO: [CAM]" → MODO vale para o bloco
        const rest = hr ? trimmed.slice(trimmed.indexOf(hr[0]) + hr[0].length).trim() : "";
        const f = rest.match(FIELD_RE);
        if (f) blockDefaults[FIELD_KEYS[/** @type {keyof typeof FIELD_KEYS} */ (f[1])] || f[1]] = f[2];
        block = hr ? trimmed.slice(0, trimmed.indexOf(hr[0])).trim() : trimmed.replace(/\s+MODO:.*$/, "");
        out.blocks.push(block);
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
      if (/^\d+\./.test(trimmed)) flushVertical();
      if (/^\d+\./.test(trimmed) || (vertBuf.length && trimmed)) vertBuf.push(trimmed);
      continue;
    }
    if (section === "ERRATA") {
      const m = trimmed.match(/^-\s*(.+?)\s*→\s*(.+)$/);
      if (m) out.errata.push({ heard: m[1].replace(/"/g, ""), correct: m[2] });
      continue;
    }
    if (section === "ASSETS") {
      out.assets += `${trimmed}\n`;
      continue;
    }
    if (section !== "BLOCK") continue;

    // sub-bloco: "----- POLÊMICA 1: A EXPULSÃO -----"
    const subm = trimmed.match(/^-{3,}\s*(.+?)\s*-{3,}$/);
    if (subm) {
      sub = subm[1];
      opensSub = true;
      seg = null;
      lastField = null;
      continue;
    }

    const range = trimmed.match(RANGE_RE);
    if (range && trimmed.startsWith("[")) {
      const start = toSeconds(range[1], range[2], range[3]);
      if (headerSeg) {
        headerSeg.end = Math.max(headerSeg.start, start);
        settleHeader();
      }
      seg = {
        start,
        end: toSeconds(range[4], range[5], range[6]),
        block,
        sub,
        opensSub,
        fields: {},
        notes: [],
        events: pendingEvents,
        defaults: { ...blockDefaults },
      };
      opensSub = false;
      pendingEvents = [];
      out.segments.push(seg);
      lastField = null;
      // "[0:00 – 0:06]  MODO: [CAM] + [VFX]"
      const rest = trimmed.slice((range.index || 0) + range[0].length).trim();
      const f = rest.match(FIELD_RE);
      if (f) setField(FIELD_KEYS[/** @type {keyof typeof FIELD_KEYS} */ (f[1])] || f[1], f[2]);
      continue;
    }
    if (/^\[IMPROVISA/i.test(trimmed)) {
      if (seg) {
        seg.improv = trimmed.replace(/^\[|\]$/g, "");
        seg.notes.push(seg.improv);
      }
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
    if (field) {
      const key = /** @type {Record<string, string>} */ (FIELD_KEYS)[field[1]] || field[1];
      if (!seg && blockRange) {
        // campos logo depois do cabeçalho do bloco (sem [tempo]): trecho do próprio cabeçalho
        seg = headerSeg = {
          start: blockRange.start,
          end: blockRange.end,
          block,
          sub,
          opensSub,
          fields: {},
          notes: [],
          events: pendingEvents,
          defaults: blockDefaults,
          header: true,
        };
        opensSub = false;
        pendingEvents = [];
        out.segments.push(seg);
      }
      if (seg) {
        setField(key, field[2]);
        continue;
      }
    }
    if (trimmed && seg && lastField) {
      // em TELA/GRÁFICO/MG cada linha extra é um item (listas de placas, cards, campinho)
      const sep = LIST_FIELDS.has(lastField) ? "\n" : " ";
      seg.fields[lastField] += `${sep}${trimmed}`;
    }
  }
  if (section === "VERTICAL") flushVertical();
  settleHeader();
  // MODO do bloco vale para os trechos sem MODO próprio
  for (const s of out.segments) {
    const d = /** @type {any} */ (s).defaults || {};
    if (!s.fields.MODO && d.MODO) s.fields.MODO = d.MODO;
    delete (/** @type {any} */ (s).defaults);
  }
  out.segments.sort((a, b) => a.start - b.start);
  return out;
}

module.exports = { parseRoteiro, normalizeText, toSeconds };
