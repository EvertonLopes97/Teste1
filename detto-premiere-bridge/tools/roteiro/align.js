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
 * Alinha todas as FALAs do roteiro (em ordem) com a transcrição inteira.
 * Retorna, por trecho, o índice da 1ª e da última palavra transcrita casada (ou null).
 * @param {Array<{fields: Record<string, string>}>} segs @param {string[]} wt
 * @returns {Array<{first: number, last: number, score: number, lead: number}|null>}
 */
function globalAlign(segs, wt) {
  /** @type {Array<{t: string, seg: number, k: number}>} */
  const R = [];
  segs.forEach((seg, i) => {
    tokens((seg.fields.FALA || "").replace(/"/g, "")).forEach((t, k) => R.push({ t, seg: i, k }));
  });
  const n = R.length;
  const m = wt.length;
  /** @type {Array<{first: number, last: number, score: number, lead: number}|null>} */
  const res = segs.map(() => null);
  if (!n || !m) return res;
  // ids de palavras e cache de close() (o mesmo par se repete muito)
  /** @type {Map<string, number>} */
  const ids = new Map();
  const id = (/** @type {string} */ w) => {
    let v = ids.get(w);
    if (v === undefined) ids.set(w, (v = ids.size));
    return v;
  };
  const ri = R.map((r) => id(r.t));
  const ti = wt.map((t) => id(t));
  const words = [...ids.keys()];
  /** @type {Map<number, number>} */
  const memo = new Map();
  const K = ids.size;
  const sim = (/** @type {number} */ a, /** @type {number} */ b) => {
    // palavras curtas ("o", "e", "pra") casam em qualquer lugar: valem pouco
    if (a === b) return words[a].length >= 5 ? 3 : words[a].length >= 4 ? 2 : 0.8;
    const key = a * K + b;
    let v = memo.get(key);
    if (v === undefined) {
      v = words[a] && words[b] && close(words[a], words[b]) ? 2 : -1;
      memo.set(key, v);
    }
    return v;
  };
  const GAP_R = -0.6; // palavra do roteiro que não foi dita
  const GAP_T = -0.35; // palavra dita fora do roteiro (improviso, muleta)
  const bt = new Uint8Array((n + 1) * (m + 1));
  let prev = new Float32Array(m + 1);
  let cur = new Float32Array(m + 1);
  for (let j = 1; j <= m; j++) {
    prev[j] = prev[j - 1] + GAP_T;
    bt[j] = 2;
  }
  for (let i = 1; i <= n; i++) {
    cur[0] = prev[0] + GAP_R;
    bt[i * (m + 1)] = 1;
    const a = ri[i - 1];
    for (let j = 1; j <= m; j++) {
      const diag = prev[j - 1] + sim(a, ti[j - 1]);
      const up = prev[j] + GAP_R;
      const left = cur[j - 1] + GAP_T;
      let v = diag;
      let d = 0;
      if (up > v) {
        v = up;
        d = 1;
      }
      if (left > v) {
        v = left;
        d = 2;
      }
      cur[j] = v;
      bt[i * (m + 1) + j] = d;
    }
    [prev, cur] = [cur, prev];
  }
  /** @type {Array<number[]>} */
  const hits = segs.map(() => []);
  /** posição (no trecho) da 1ª palavra do roteiro casada: palavras antes dela foram ditas de outro jeito */
  const lead = segs.map(() => 0);
  /** @type {Array<number[]>} */
  const strong = segs.map(() => []);
  let i = n;
  let j = m;
  while (i > 0 && j > 0) {
    const d = bt[i * (m + 1) + j];
    if (d === 0) {
      if (sim(ri[i - 1], ti[j - 1]) > 0) {
        hits[R[i - 1].seg].push(j - 1);
        // o começo do trecho é marcado por palavra de conteúdo (4+ letras), não por "e"/"o"
        if (R[i - 1].t.length >= 4 || !strong[R[i - 1].seg].length) {
          if (R[i - 1].t.length >= 4) strong[R[i - 1].seg].push(j - 1);
          lead[R[i - 1].seg] = R[i - 1].k;
        }
      }
      i--;
      j--;
    } else if (d === 1) i--;
    else j--;
  }
  const count = segs.map(() => 0);
  for (const r of R) count[r.seg]++;
  hits.forEach((h, s) => {
    if (!h.length) return;
    const score = h.length / Math.max(1, count[s]);
    // poucas palavras casadas num trecho longo = provavelmente casou por acaso
    if (h.length < Math.min(3, count[s]) || score < 0.2) return;
    const st = strong[s].length ? strong[s] : h;
    res[s] = { first: Math.min(...st), last: Math.max(...h), score, lead: lead[s] };
  });
  return res;
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

  // 1) alinhamento global roteiro × fala (programação dinâmica). Tolera fala mudada:
  //    palavras trocadas, cortadas, acrescentadas e trechos de improviso inteiros.
  const startIdx = globalAlign(segs, wt);
  segs.forEach((seg, i) => {
    const hit = startIdx[i];
    if (hit) {
      report.matched++;
      report.details.push({ tc: seg.start, at: words[hit.first].s, score: Number(hit.score.toFixed(2)) });
    } else {
      report.estimated++;
      report.details.push({ tc: seg.start, at: null, score: 0 });
    }
  });
  // começo do trecho: na maior pausa logo antes da 1ª palavra casada (recuando só o número de
  // palavras do começo da FALA que foram ditas de outro jeito; o improviso antes fica no trecho anterior)
  /** @type {number[]} */
  const starts = segs.map(() => NaN);
  let prevLast = -1;
  segs.forEach((seg, i) => {
    const hit = startIdx[i];
    if (!hit) return;
    let best = hit.first;
    let bestGap = -1;
    for (let j = Math.max(prevLast + 1, 1, hit.first - hit.lead - 2); j <= hit.first; j++) {
      const g = words[j].s - words[j - 1].e;
      if (g > bestGap) {
        bestGap = g;
        best = j;
      }
    }
    if (prevLast < 0 && hit.first > 0) {
      // primeiro trecho: começa na primeira fala, salvo se a 1ª palavra casada vem logo depois
      best = words[hit.first].s - words[0].s < 6 ? 0 : best;
    }
    starts[i] = Math.max(0, words[best].s - 0.12);
    prevLast = hit.last;
  });
  // trechos sem fala casada (vinhetas, telas sem FALA): proporcional ao tempo do roteiro entre vizinhos
  for (let i = 0; i < segs.length; i++) {
    if (!Number.isNaN(starts[i])) continue;
    let p = i - 1;
    while (p >= 0 && Number.isNaN(starts[p])) p--;
    let n = i + 1;
    while (n < segs.length && Number.isNaN(starts[n])) n++;
    const pt = p >= 0 ? starts[p] : 0;
    const ptc = p >= 0 ? segs[p].tc : 0;
    const nt = n < segs.length ? starts[n] : opts.mediaDuration;
    const ntc = n < segs.length ? segs[n].tc : scriptEnd;
    if (!segs[i].fields.FALA && n < segs.length && !Number.isNaN(starts[n])) {
      // vinheta sem fala: logo antes do trecho seguinte, com a duração prevista no roteiro
      const len = Math.min(segs[i].tcEnd - segs[i].tc, 2.5);
      starts[i] = Math.max(pt + 0.5, nt - len);
    } else {
      starts[i] = pt + ((segs[i].tc - ptc) / Math.max(1e-6, ntc - ptc)) * (nt - pt);
    }
  }
  segs.forEach((seg, i) => (seg.start = starts[i]));
  for (let i = 1; i < segs.length; i++) {
    if (segs[i].start <= segs[i - 1].start) segs[i].start = segs[i - 1].start + 0.5;
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

module.exports = { globalAlign, alignRoteiro, makeMapper, tokens, norm, close, findPhrase };
