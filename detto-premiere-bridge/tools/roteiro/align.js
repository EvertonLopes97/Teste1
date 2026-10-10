// @ts-check
"use strict";

/**
 * Alinha o roteiro à fala real usando a transcrição com tempo por palavra
 * (Whisper: [{w, s, e}]). Os [TC] do roteiro são estimativas; aqui cada trecho
 * passa a começar onde a sua FALA começa de verdade.
 *
 * Também:
 *  - acha "deixas" citadas entre aspas no EFEITO/SFX/TELA ("saiu chorando", "última")
 *    para posicionar punch-ins e efeitos na palavra exata;
 *  - acha o palavrão das notas gerais (para o bip);
 *  - calcula os trechos de fala contínua (jump cuts), removendo pausas longas.
 */

/** @typedef {{w: string, s: number, e: number}} Word */

/** @param {string} s */
function norm(s) {
  return s
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

/** @param {string} s */
function tokens(s) {
  return norm(s).split(" ").filter(Boolean);
}

/** Distância de edição limitada (para "Götze" ≈ "gotz", "Lusail" ≈ "luzail"). */
/** @param {string} a @param {string} b */
function close(a, b) {
  if (a === b) return true;
  if (Math.min(a.length, b.length) < 4 || Math.abs(a.length - b.length) > 2) return false;
  const dp = Array.from({ length: a.length + 1 }, (_, i) => [i]);
  for (let j = 1; j <= b.length; j++) dp[0][j] = j;
  for (let i = 1; i <= a.length; i++)
    for (let j = 1; j <= b.length; j++)
      dp[i][j] = Math.min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
  return dp[a.length][b.length] <= (a.length > 6 ? 2 : 1);
}

/**
 * Melhor posição em `wt` (tokens da transcrição) para a sequência `target`,
 * procurando entre [from, to). Pontua quantos dos primeiros tokens do alvo
 * aparecem na janela, com bônus para a palavra inicial exata.
 * @param {string[]} wt @param {string[]} target @param {number} from @param {number} to
 */
function findPhrase(wt, target, from, to) {
  const K = Math.min(target.length, 8);
  if (K === 0) return { index: -1, score: 0 };
  let best = { index: -1, score: 0 };
  for (let p = Math.max(0, from); p < Math.min(wt.length, to); p++) {
    let score = 0;
    const window = wt.slice(p, p + K + 3);
    for (let k = 0; k < K; k++) if (window.some((w) => close(w, target[k]))) score++;
    if (close(wt[p], target[0])) score += 1.5;
    else if (K > 1 && close(wt[p], target[1])) score += 0.5;
    if (score > best.score) best = { index: p, score };
  }
  return { index: best.index, score: best.score / (K + 1.5) };
}

/**
 * @param {import("./parse").Roteiro} roteiro
 * @param {Word[]} words
 * @param {{mediaDuration: number, gap?: number, pad?: number}} opts
 */
function alignRoteiro(roteiro, words, opts) {
  const wt = words.map((w) => tokens(w.w).join(""));
  const report = { matched: 0, estimated: 0, details: /** @type {any[]} */ ([]) };
  const segs = roteiro.segments.map((s) => ({ ...s, tc: s.start, tcEnd: s.end, fields: { ...s.fields }, cues: /** @type {Record<string, number>} */ ({}) }));
  const scriptEnd = segs.length ? segs[segs.length - 1].end : 1;

  // 1) início de cada trecho = onde a FALA começa
  let cursor = 0;
  /** @type {number[]} */
  const startIdx = [];
  segs.forEach((seg, i) => {
    const target = tokens((seg.fields.FALA || "").replace(/"/g, ""));
    // janela de busca proporcional ao tempo estimado (tolerante a erro grande do roteiro)
    const expected = Math.round((seg.start / scriptEnd) * words.length);
    const from = cursor;
    const to = Math.max(cursor + 60, expected + Math.round(words.length * 0.15));
    const hit = findPhrase(wt, target, from, to);
    if (hit.index >= 0 && hit.score >= 0.45) {
      startIdx[i] = hit.index;
      cursor = hit.index + 1;
      report.matched++;
      report.details.push({ tc: seg.start, at: words[hit.index].s, score: Number(hit.score.toFixed(2)) });
    } else {
      startIdx[i] = -1;
      report.estimated++;
      report.details.push({ tc: seg.start, at: null, score: Number(hit.score.toFixed(2)) });
    }
  });

  // trechos não encontrados: interpola entre vizinhos
  segs.forEach((seg, i) => {
    if (startIdx[i] >= 0) {
      seg.start = Math.max(0, words[startIdx[i]].s - 0.12);
      return;
    }
    const prev = segs.slice(0, i).reverse().find((_, k) => startIdx[i - 1 - k] >= 0);
    const prevT = prev ? prev.start : 0;
    seg.start = prevT + 0.5;
  });
  for (let i = 0; i < segs.length; i++) {
    if (i > 0 && segs[i].start <= segs[i - 1].start) segs[i].start = segs[i - 1].start + 0.5;
  }
  segs[0].start = 0;
  segs.forEach((seg, i) => {
    seg.end = i + 1 < segs.length ? segs[i + 1].start : Math.min(opts.mediaDuration, (words.at(-1)?.e || seg.start) + 0.6);
  });

  // 2) deixas entre aspas dentro do trecho
  segs.forEach((seg) => {
    const inSeg = words.map((w, i) => ({ ...w, t: wt[i] })).filter((w) => w.s >= seg.start && w.s < seg.end);
    const source = [seg.fields.EFEITO, seg.fields.SFX, seg.fields.TELA].filter(Boolean).join(" ");
    const re = /"([^"]{2,40})"/g;
    let m;
    while ((m = re.exec(source))) {
      const target = tokens(m[1].replace(/\.\.\.$/, ""));
      if (!target.length || target.length > 6) continue;
      const k = inSeg.findIndex((w, j) => target.every((t, n) => inSeg[j + n] && close(inSeg[j + n].t, t)));
      if (k >= 0) seg.cues[m[1]] = inSeg[k].s;
    }
  });

  // 3) notas com horário (ex.: palavrão) → palavra real mais próxima
  const timedNotes = roteiro.timedNotes.map((n) => {
    const q = (n.text.match(/"([^"]+)"/) || [])[1];
    if (!q) return { ...n };
    const target = tokens(q);
    const last = target[target.length - 1];
    let bestI = -1;
    wt.forEach((t, i) => {
      if (close(t, last) && (bestI < 0 || Math.abs(words[i].s - n.time * (opts.mediaDuration / scriptEnd)) < Math.abs(words[bestI].s - n.time * (opts.mediaDuration / scriptEnd)))) bestI = i;
    });
    return bestI >= 0 ? { ...n, time: words[bestI].s, end: words[bestI].e, word: words[bestI].w } : { ...n };
  });

  // 4) jump cuts: ilhas de fala separadas por pausas > gap
  const gap = opts.gap ?? 0.8;
  const pad = opts.pad ?? 0.12;
  /** @type {Array<{start: number, end: number}>} */
  const keep = [];
  for (const w of words) {
    const s = Math.max(0, w.s - pad);
    const e = Math.min(opts.mediaDuration, w.e + pad);
    const last = keep[keep.length - 1];
    if (last && s - last.end <= gap - 2 * pad) last.end = Math.max(last.end, e);
    else keep.push({ start: s, end: e });
  }
  if (keep.length) keep[0].start = Math.min(keep[0].start, 0.05) < 0.3 ? 0 : keep[0].start;

  return { roteiro: { ...roteiro, segments: segs, timedNotes }, keep, report };
}

/**
 * Mapeia tempo da mídia → tempo da timeline após remover as pausas.
 * Tempos dentro de uma pausa removida vão para o início do próximo trecho.
 * @param {Array<{start: number, end: number}>} keep
 */
function makeMapper(keep) {
  /** @type {Array<{start: number, end: number, tl: number}>} */
  const acc = [];
  let tl = 0;
  for (const k of keep) {
    acc.push({ ...k, tl });
    tl += k.end - k.start;
  }
  return (/** @type {number} */ t) => {
    for (const k of acc) {
      if (t < k.start) return k.tl;
      if (t <= k.end) return k.tl + (t - k.start);
    }
    return tl;
  };
}

module.exports = { alignRoteiro, makeMapper, tokens, norm, close, findPhrase };
