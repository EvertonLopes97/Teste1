// @ts-check
"use strict";

/**
 * Legendas dinâmicas palavra por palavra.
 *
 * O texto é o que foi FALADO de verdade (transcrição): se a fala mudou em relação ao
 * roteiro, a legenda acompanha a fala. O roteiro só corrige a grafia das palavras
 * parecidas (nomes: "Götze", "Di María", "Matheuzinho", números) e a ERRATA troca
 * nomes que o Whisper errou. As duas sequências são alinhadas dentro de cada trecho.
 */

const { tokens, close } = require("./align");

/**
 * @typedef {{w: string, s: number, e: number}} Word
 * @typedef {{w: string, s: number, e: number, hl: boolean}} CaptionWord
 * @typedef {{start: number, end: number, text: string, words: CaptionWord[]}} Caption
 */

/**
 * Alinha `display` (palavras do roteiro) a `heard` (palavras transcritas com tempo).
 * @param {string[]} display
 * @param {Word[]} heard
 * @returns {Array<{s: number, e: number}|null>}
 */
function alignWords(display, heard) {
  const a = display.map((d) => tokens(d).join(""));
  const b = heard.map((h) => tokens(h.w).join(""));
  const n = a.length;
  const m = b.length;
  // dp[i][j] = melhor pontuação alinhando a[0..i) com b[0..j)
  const dp = Array.from({ length: n + 1 }, () => new Float64Array(m + 1));
  const bt = Array.from({ length: n + 1 }, () => new Uint8Array(m + 1));
  for (let i = 1; i <= n; i++) bt[i][0] = 1;
  for (let j = 1; j <= m; j++) bt[0][j] = 2;
  for (let i = 1; i <= n; i++) {
    for (let j = 1; j <= m; j++) {
      const match = a[i - 1] && b[j - 1] && close(a[i - 1], b[j - 1]) ? 2 : -1;
      const diag = dp[i - 1][j - 1] + match;
      const up = dp[i - 1][j] - 0.6;
      const left = dp[i][j - 1] - 0.6;
      if (diag >= up && diag >= left) {
        dp[i][j] = diag;
        bt[i][j] = 0;
      } else if (up >= left) {
        dp[i][j] = up;
        bt[i][j] = 1;
      } else {
        dp[i][j] = left;
        bt[i][j] = 2;
      }
    }
  }
  /** @type {Array<{s: number, e: number}|null>} */
  const out = new Array(n).fill(null);
  let i = n;
  let j = m;
  while (i > 0 && j > 0) {
    if (bt[i][j] === 0) {
      // substituição também carrega o tempo (palavra ouvida diferente da escrita)
      out[i - 1] = { s: heard[j - 1].s, e: heard[j - 1].e };
      i--;
      j--;
    } else if (bt[i][j] === 1) i--;
    else j--;
  }
  // preenche palavras sem tempo interpolando entre vizinhas
  for (let k = 0; k < n; k++) {
    if (out[k]) continue;
    const prev = out.slice(0, k).reverse().find(Boolean);
    const next = out.slice(k + 1).find(Boolean);
    if (prev && next) out[k] = { s: prev.e, e: Math.max(prev.e + 0.05, next.s) };
    else if (prev) out[k] = { s: prev.e, e: prev.e + 0.25 };
    else if (next) out[k] = { s: Math.max(0, next.s - 0.25), e: next.s };
  }
  return out;
}

/** Números, datas, placares e nomes próprios ganham destaque. */
/** @param {string} w @param {number} index */
function isHighlight(w, index) {
  const clean = w.replace(/[^\p{L}\p{N}]/gu, "");
  if (/\d/.test(clean)) return true;
  if (index > 0 && /^\p{Lu}/u.test(clean) && clean.length > 2) return true;
  return false;
}

/**
 * Para cada palavra ouvida, o índice da palavra do roteiro parecida com ela (ou -1).
 * @param {string[]} display @param {Word[]} heard
 */
function mapHeard(display, heard) {
  const a = display.map((d) => tokens(d).join(""));
  const b = heard.map((h) => tokens(h.w).join(""));
  const n = a.length;
  const m = b.length;
  const dp = Array.from({ length: n + 1 }, () => new Float64Array(m + 1));
  const bt = Array.from({ length: n + 1 }, () => new Uint8Array(m + 1));
  for (let i = 1; i <= n; i++) bt[i][0] = 1;
  for (let j = 1; j <= m; j++) bt[0][j] = 2;
  for (let i = 1; i <= n; i++) {
    for (let j = 1; j <= m; j++) {
      const diag = dp[i - 1][j - 1] + (a[i - 1] && b[j - 1] && close(a[i - 1], b[j - 1]) ? 2 : -1);
      const up = dp[i - 1][j] - 0.5;
      const left = dp[i][j - 1] - 0.5;
      if (diag >= up && diag >= left) {
        dp[i][j] = diag;
        bt[i][j] = 0;
      } else if (up >= left) {
        dp[i][j] = up;
        bt[i][j] = 1;
      } else {
        dp[i][j] = left;
        bt[i][j] = 2;
      }
    }
  }
  const out = new Array(m).fill(-1);
  let i = n;
  let j = m;
  while (i > 0 && j > 0) {
    if (bt[i][j] === 0) {
      if (a[i - 1] && b[j - 1] && close(a[i - 1], b[j - 1])) out[j - 1] = i - 1;
      i--;
      j--;
    } else if (bt[i][j] === 1) i--;
    else j--;
  }
  return out;
}

/**
 * O que foi FALADO em cada trecho (texto da transcrição com a grafia do roteiro nos nomes),
 * e quanto da FALA escrita foi dita (0 a 1).
 * @param {import("./parse").Roteiro} roteiro  roteiro já alinhado (tempos na mídia)
 * @param {Word[]} words
 * @returns {Array<{text: string, parecido: number}>}
 */
function spokenBySegment(roteiro, words) {
  return roteiro.segments.map((seg) => {
    const fala = (seg.fields.FALA || "").replace(/"/g, "");
    const display = fala.split(/\s+/).filter(Boolean);
    const heard = words.filter((w) => w.s >= seg.start - 0.05 && w.s < seg.end);
    if (!heard.length) return { text: "", parecido: 0 };
    const map = display.length ? mapHeard(display, heard) : heard.map(() => -1);
    const text = heard
      .map((h, j) => {
        const k = map[j];
        return k >= 0 && (/^\p{Lu}|\d/u.test(display[k]) || tokens(display[k]).join("") === tokens(h.w).join("")) ? display[k] : h.w.trim();
      })
      .join(" ");
    const usados = new Set(map.filter((k) => k >= 0));
    return { text, parecido: display.length ? usados.size / display.length : 0 };
  });
}

/**
 * Corrige a grafia com a ERRATA ("Rúlque" → HULK); vale para 1 a 3 palavras seguidas.
 * @param {CaptionWord[]} list @param {Array<{heard: string, correct: string}>} errata
 */
function applyErrata(list, errata) {
  for (const e of errata || []) {
    const h = tokens(e.heard);
    if (!h.length) continue;
    const fix = e.correct.toLowerCase().replace(/(^|[\s-])(\p{L})/gu, (x) => x.toUpperCase());
    for (let k = 0; k + h.length <= list.length; k++) {
      if (!h.every((t, n) => close(tokens(list[k + n].w).join(""), t))) continue;
      const punct = (list[k + h.length - 1].w.match(/[.,!?:;]+$/) || [""])[0];
      list[k].w = fix + punct;
      list[k].e = list[k + h.length - 1].e;
      list[k].hl = true;
      list.splice(k + 1, h.length - 1);
    }
  }
}

/**
 * Gera legendas na timeline final.
 * @param {import("./parse").Roteiro} roteiro  roteiro já alinhado (tempos na mídia)
 * @param {Word[]} words                       transcrição (tempos na mídia)
 * @param {(t: number) => number} toTimeline   mapeamento mídia → timeline (jump cuts)
 * @param {{maxWords?: number, maxChars?: number}} [opts]
 * @returns {Caption[]}
 */
function buildCaptions(roteiro, words, toTimeline, opts = {}) {
  const maxWords = opts.maxWords ?? 3;
  const maxChars = opts.maxChars ?? 20;
  /** @type {CaptionWord[]} */
  const all = [];
  const done = new Set();
  for (const seg of roteiro.segments) {
    const fala = (seg.fields.FALA || "").replace(/^"|"$/g, "").replace(/"/g, "");
    const display = fala.split(/\s+/).filter(Boolean);
    const idx = words.map((w, i) => i).filter((i) => !done.has(i) && words[i].s >= seg.start - 0.05 && words[i].s < seg.end);
    const heard = idx.map((i) => words[i]);
    const map = display.length ? mapHeard(display, heard) : heard.map(() => -1);
    heard.forEach((h, j) => {
      done.add(idx[j]);
      const k = map[j];
      // palavra parecida com a do roteiro: grafia do roteiro (acentos, nome, maiúscula); senão, o que foi dito
      let w = k >= 0 ? display[k] : h.w.trim();
      if (k >= 0 && tokens(display[k]).join("") !== tokens(h.w).join("") && !/^\p{Lu}|\d/u.test(display[k])) w = h.w.trim();
      all.push({ w, s: toTimeline(h.s), e: toTimeline(Math.max(h.e, h.s + 0.05)), hl: isHighlight(w, k >= 0 ? k : 1) });
    });
  }
  // fala fora de qualquer trecho do roteiro
  words.forEach((h, i) => {
    if (!done.has(i)) all.push({ w: h.w.trim(), s: toTimeline(h.s), e: toTimeline(Math.max(h.e, h.s + 0.05)), hl: isHighlight(h.w.trim(), 1) });
  });
  all.sort((x, y) => x.s - y.s);
  applyErrata(all, roteiro.errata);

  /** @type {Caption[]} */
  const caps = [];
  /** @type {CaptionWord[]} */
  let cur = [];
  const flush = () => {
    if (!cur.length) return;
    caps.push({ start: cur[0].s, end: cur[cur.length - 1].e, text: cur.map((c) => c.w).join(" "), words: cur });
    cur = [];
  };
  for (const w of all) {
    const prev = cur[cur.length - 1];
    const text = [...cur.map((c) => c.w), w.w].join(" ");
    if (prev && (cur.length >= maxWords || text.length > maxChars || w.s - prev.e > 0.35 || /[.!?,:;]$/.test(prev.w))) flush();
    cur.push(w);
  }
  flush();
  // cada legenda fica na tela até a próxima (sem piscar), no máximo +0.4 s
  caps.forEach((c, i) => {
    const next = caps[i + 1];
    c.end = next ? Math.min(next.start, c.end + 0.4) : c.end + 0.4;
  });
  return caps;
}

/** @param {number} t */
function srtTime(t) {
  const ms = Math.round(t * 1000);
  const h = Math.floor(ms / 3600000);
  const m = Math.floor(ms / 60000) % 60;
  const s = Math.floor(ms / 1000) % 60;
  const r = ms % 1000;
  const p = (/** @type {number} */ n, l = 2) => String(n).padStart(l, "0");
  return `${p(h)}:${p(m)}:${p(s)},${p(r, 3)}`;
}

/** SRT para importar no Premiere (Arquivo › Importar › legendas). */
/** @param {Caption[]} caps */
function toSrt(caps) {
  return caps.map((c, i) => `${i + 1}\n${srtTime(c.start)} --> ${srtTime(c.end)}\n${c.text}\n`).join("\n");
}

module.exports = { buildCaptions, alignWords, mapHeard, spokenBySegment, toSrt, isHighlight };
