"use strict";

/**
 * "Diretor" da edição dinâmica. Transforma o EDIT_PLAN numa timeline:
 *
 *  - cada gráfico entra na palavra exata em que é falado (âncora na transcrição);
 *  - os gráficos alternam entre estilos:
 *      full      → só o gráfico em tela cheia, com a voz ao fundo
 *      camWindow → rosto numa janela com moldura + gráfico ao lado
 *      gfxCard   → gráfico num card com moldura sobre a câmera (rosto deslocado)
 *      photoCard → foto de apoio (b-roll) num quadro com moldura e zoom lento
 *  - a base é o enquadramento original da gravação; o rosto só é centralizado
 *    na dinâmica: zoom seco em alguns cortes, aproximação lenta no suspense e
 *    punch-ins nas deixas;
 *  - SFX sincronizados com cada entrada.
 */

const { flagCode } = require("./flags");

const LEAD = 0.12; // gráfico entra um pouco antes da palavra (o olho chega antes do ouvido)
const DUR = { era: 2.0, score: 3.0, number: 2.4, headline: 2.6, bars: 3.2, list: 4.2, redcard: 2.6, keyword: 1.6, chip: 2.8, cta: 2.6, photo: 3.6 };
const MIN_PLATE = 1.3;
const GAP = 0.6; // respiro mínimo entre dois gráficos de tela

// ------------------------------------------------------------------ texto

function clean(s) {
  return String(s || "")
    .replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}\u{200D}\u{2B00}-\u{2BFF}\u{E0000}-\u{E007F}]/gu, "")
    .replace(/\s+/g, " ")
    .trim();
}

function norm(s) {
  return String(s)
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();
}

const NUM_WORDS = {
  nenhum: 0, zero: 0, dois: 2, duas: 2, tres: 3, quatro: 4, cinco: 5, seis: 6, sete: 7, oito: 8, nove: 9,
  dez: 10, onze: 11, doze: 12, treze: 13, quatorze: 14, catorze: 14, quinze: 15, dezesseis: 16,
  dezessete: 17, dezoito: 18, dezenove: 19, vinte: 20, trinta: 30, quarenta: 40, cinquenta: 50,
  sessenta: 60, setenta: 70, oitenta: 80, noventa: 90, cem: 100, duzentos: 200, mil: 1000,
};
const MONTHS = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
const STOP = new Set(
  "a o as os de da do das dos e em no na nos nas um uma por pra para com que se ao aos the mais menos muito ja nao sim ele ela isso esse essa este esta foi vai tem teve copa final jogo jogos mundo argentina messi selecao gol gols time contra depois".split(" ")
);

/** Tokens de uma palavra falada: texto normalizado, dígitos e números por extenso. */
function wordTokens(w) {
  const n = norm(w).replace(/[^a-z0-9x]+/g, " ").trim();
  const out = new Set();
  for (const part of n.split(" ")) {
    if (!part) continue;
    out.add(part);
    if (NUM_WORDS[part] !== undefined) out.add(String(NUM_WORDS[part]));
    // "2x1" falado só casa com placar (não vale como "2" solto)
    if (/^\d+x\d+$/.test(part)) continue;
    const lead = part.match(/^(\d+)/);
    if (lead) out.add(lead[1]);
  }
  return out;
}

/**
 * Chaves de busca de um texto de gráfico, com peso: placar "2x1", números, datas
 * (dia, mês por extenso, ano), nomes próprios e palavras distintivas.
 */
function anchorKeys(text) {
  const t = clean(text);
  /** @type {Array<{k: string, w: number}>} */
  const keys = [];
  const add = (k, w) => {
    if (k && !keys.some((x) => x.k === k)) keys.push({ k, w });
  };
  for (const m of t.matchAll(/(\d+)\s*x\s*(\d+)/gi)) add(`${m[1]}x${m[2]}`, 4);
  for (const m of t.matchAll(/(\d{1,2})\/(\d{1,2})\/(\d{4})/g)) {
    add(String(Number(m[1])), 2);
    add(MONTHS[Number(m[2]) - 1], 4);
    add(m[3], 3);
  }
  // números de 1 dígito são comuns na fala ("1", "2"): pesam menos que "113" ou "2005"
  for (const m of t.matchAll(/\b(\d{1,3}(?:\.\d{3})+|\d+)/g)) add(m[1].split(".")[0], m[1].length >= 2 ? 3 : 2);
  for (const raw of t.split(/[\s•→:|,()]+/)) {
    const w = norm(raw).replace(/[^a-z]/g, "");
    if (w.length < 4 || STOP.has(w)) continue;
    add(w, w.length >= 6 || (/^[A-ZÁÉÍÓÚÂÊÔÃÕÇ]/.test(raw) && raw !== raw.toUpperCase()) ? 3 : 2);
  }
  return keys;
}

/**
 * Procura na fala (palavras da legenda, tempo da timeline) o ponto em que o texto
 * do gráfico é dito. Retorna o tempo da primeira palavra casada ou null.
 * @param {Array<{w: string, s: number, tok: Set<string>}>} words
 */
function findAnchor(words, text, from, to) {
  const keys = anchorKeys(text);
  if (!keys.length) return null;
  const win = words.filter((w) => w.s >= from && w.s < to);
  let best = null;
  for (let i = 0; i < win.length; i++) {
    let score = 0;
    let first = null;
    const used = new Set();
    for (let j = i; j < Math.min(win.length, i + 9); j++) {
      for (const { k, w } of keys) {
        if (used.has(k)) continue;
        if (win[j].tok.has(k) || (k.length >= 5 && [...win[j].tok].some((x) => x.length >= 5 && (x.startsWith(k.slice(0, 5)) || k.startsWith(x.slice(0, 5)))))) {
          used.add(k);
          score += w;
          if (first === null) first = win[j].s;
        }
      }
    }
    // a janela tem de começar numa palavra casada
    if (first === null || first !== win[i].s) continue;
    if (!best || score > best.score) best = { score, t: first };
  }
  return best && best.score >= 3 ? best.t : null;
}

// ------------------------------------------------------------------ parsers de gráfico

function parseScore(text) {
  const raw = clean(text);
  const lossMark = /❌/.test(text);
  const [main, ...rest] = raw.split("•").map((p) => p.trim());
  const paren = (main.match(/\(([^)]*)\)/) || [])[1] || "";
  const core = main.replace(/\([^)]*\)/g, "").trim();
  const m = core.match(/^(.+?)\s+(\d+)\s*x\s*(\d+)\s+(.+)$/i);
  if (!m) return null;
  const a = m[1].trim();
  const b = m[4].trim();
  if (/\d|→/.test(a + b)) return null;
  const sa = Number(m[2]);
  const sb = Number(m[3]);
  const fa = flagCode(a);
  const fb = flagCode(b);
  if (!fa && !fb) return null;
  let loss = lossMark;
  if (fa === "ar" || fb === "ar") {
    if (sa !== sb) loss = fa === "ar" ? sa < sb : sb < sa;
    else {
      const pen = paren.match(/(\d+)\s*x\s*(\d+)\s*(.*)$/);
      if (pen && pen[3]) loss = flagCode(pen[3]) !== "ar";
    }
  }
  return { a: { name: a, flag: fa }, b: { name: b, flag: fb }, sa, sb, sub: paren, comp: rest.join(" • "), loss };
}

function parseNumber(text) {
  const raw = clean(text);
  if (/\d{2}:\d{2}/.test(raw)) return null;
  const m = raw.match(/([+]?)(\d{1,3}(?:\.\d{3})+|\d+)(['º°ª]?)/);
  if (!m) return null;
  const num = Number(m[2].replace(/\./g, ""));
  const tidy = (x) => x.replace(/^[\s:•-]+|[\s:•-]+$/g, "").trim();
  const upper = (x) => (x && x === x.toUpperCase() ? x : x.length <= 3 ? x.toUpperCase() : "");
  const before = upper(tidy(raw.slice(0, m.index)));
  const after = upper(tidy(raw.slice(m.index + m[0].length)));
  return { display: m[0], num, prefix: m[1], suffix: m[3], thousands: m[2].includes("."), label: before && after ? after : before || after, top: before && after ? before : "" };
}

function headlineLines(text) {
  const t = clean(text).replace(/\s*→\s*/g, " → ");
  let parts = t.split(/\s*(?:→|•|\.\.\.)\s*/).filter(Boolean);
  if (parts.length === 1) {
    const words = parts[0].split(" ");
    if (words.length >= 4) {
      const third = Math.ceil(words.length / 3);
      parts = [words.slice(0, third).join(" "), words.slice(third, 2 * third).join(" "), words.slice(2 * third).join(" ")].filter(Boolean);
    }
  }
  return parts.slice(0, 4).map((p, i, arr) => ({ text: p, box: arr.length > 1 && i === Math.floor(arr.length / 2) }));
}

function keywordColor(text, mood) {
  if (/PERD|EXPULS|VAIAD|TRISTE|ZEBRA|DESESPERO|ADEUS|CHORANDO|BANCO|DE NOVO/i.test(text) || mood === "loss") return "red";
  if (/CAMPE|T[ÍI]TULO|OURO|VIRADA|RECORDE|BICAMPE|HAT-TRICK/i.test(text)) return "";
  return "white";
}

// ------------------------------------------------------------------ diretor

/**
 * @param {any} plan EDIT_PLAN (com meta.segments e captions)
 * @param {{images?: Record<string, any>, faceAt?: (t: number) => {cx: number, cy: number, w: number}, facecamColorFx?: boolean}} [opts]
 */
function direct(plan, opts = {}) {
  const fps = plan.sequence.fps;
  const last = plan.cuts.reduce((m, c) => Math.max(m, c.timeline + (c.end - c.start)), 0);
  const duration = Math.round(last * fps) / fps;
  const segments = (plan.meta && plan.meta.segments) || [];
  const graphics = (plan.graphics || []).slice().sort((a, b) => a.start - b.start);
  const markers = plan.markers || [];
  const vfx = plan.vfx || [];
  const images = opts.images || {};

  const words = [];
  for (const c of plan.captions || []) for (const w of c.words) words.push({ w: w.w, s: w.s, e: w.e, tok: wordTokens(w.w) });
  words.sort((a, b) => a.s - b.s);

  /** @type {any[]} */ const cands = []; // gráficos de tela (placas/cards) e fotos
  /** @type {any[]} */ const overlays = [];
  /** @type {any[]} */ const sfx = [];
  let prevYear = 2005;

  segments.forEach((seg, si) => {
    const S = seg.start;
    const E = si + 1 < segments.length ? segments[si + 1].start : duration;
    const anchor = (text, fallback) => {
      const t = findAnchor(words, text, S - 0.4, E + 0.3);
      return t === null ? { t: fallback, synced: false } : { t: Math.max(0, t - LEAD), synced: true };
    };
    const inSeg = graphics.filter((g) => g.start >= S - 0.01 && g.start < E && g.type !== "generic" && g.type !== "timeline_bar");
    const dateG = inSeg.find((g) => g.type === "date_stamp");
    const mood = seg.mood;
    const push = (c) => cands.push({ seg: si, segStart: S, segEnd: E, ...c });

    // cartão de era: entra quando o ano/assunto do bloco é dito
    const blockMarker = markers.find((m) => m.color === "blue" && Math.abs(m.time - S) < 0.05);
    if (blockMarker && /^BLOCO/i.test(blockMarker.name)) {
      const tl = markers.find((m) => /LINHA DO TEMPO/.test(m.name) && Math.abs(m.time - S) < 0.05);
      const year = (tl && tl.name.match(/(\d{4})/)?.[1]) || blockMarker.name.match(/\((\d{4})/)?.[1] || blockMarker.name.match(/(\d{4})/)?.[1];
      const title = blockMarker.name.replace(/^BLOCO\s+\d+\s*[—-]\s*/i, "").replace(/\s*\(\d{4}(?:[–-]\d{4})?\)\s*$/, "");
      if (year) {
        const a = anchor(year, S);
        push({ type: "era", start: Math.min(a.t, S + 1.5), dur: DUR.era, prio: 9, synced: a.synced, data: { year, title, prevYear } });
        prevYear = Number(year);
      }
    }

    // placares
    const scores = inSeg.filter((g) => g.type === "scoreboard").map((g) => ({ g, s: parseScore(g.text) }));
    const parsed = scores.filter((x) => x.s);
    if (parsed.length >= 3) {
      const titleG = scores.find((x) => !x.s);
      const a = anchor(parsed.map((x) => `${x.s.a.name} ${x.s.b.name}`).join(" "), parsed[0].g.start);
      push({
        type: "list",
        start: a.t,
        dur: Math.min(5, 1.4 + parsed.length * 0.45),
        prio: 6,
        synced: a.synced,
        data: {
          title: clean((titleG && titleG.g.text) || (dateG && dateG.text) || "Jogo a jogo"),
          rows: parsed.map(({ s }) => ({ text: `${s.a.name} ${s.sa} x ${s.sb} ${s.b.name}`, flags: [s.a.flag, s.b.flag].filter(Boolean), note: clean([s.sub, s.comp].filter(Boolean).join(" • ")).slice(0, 34), loss: s.loss })),
        },
      });
    } else {
      for (const { g, s } of scores) {
        if (s) {
          const a = anchor(`${s.sa}x${s.sb} ${s.a.flag === "ar" ? s.b.name : s.a.name}`, g.start);
          push({ type: "score", start: a.t, dur: DUR.score, prio: 7, synced: a.synced, data: { comp: s.comp, a: s.a, b: s.b, sa: s.sa, sb: s.sb, sub: s.sub, date: dateG ? clean(dateG.text) : "", mood: s.loss ? "loss" : "" } });
        } else if (/\d\s*x\s*\d/.test(g.text)) {
          const a = anchor(g.text, g.start);
          push({ type: "headline", start: a.t, dur: DUR.headline + 0.4, prio: 4, synced: a.synced, data: { lines: headlineLines(g.text), mood } });
        }
      }
    }

    // contadores / números / barras
    for (const g of inSeg.filter((x) => x.type === "counter")) {
      const t = clean(g.text);
      const bars = t.match(/MESSI\s+(\d+)\s+BATISTUTA\s+(\d+)/i);
      if (bars) {
        const a = anchor("Batistuta", g.start);
        push({ type: "bars", start: a.t, dur: DUR.bars, prio: 6, synced: a.synced, data: { title: "Artilheiros da seleção", bars: [{ name: "Messi", value: Number(bars[1]) }, { name: "Batistuta", value: Number(bars[2]), gray: true }] } });
        continue;
      }
      for (const part of t.split(/\s*→\s*/)) {
        const n = parseNumber(part);
        if (!n) continue;
        const a = anchor(part, g.start);
        push({ type: "number", start: a.t, dur: DUR.number, prio: 5, synced: a.synced, data: { ...n, mood: /PERDID/.test(part) || (n.num === 0 && mood === "loss") ? "loss" : "" } });
      }
    }

    // fichas / estante
    for (const g of inSeg.filter((x) => x.type === "stat_card")) {
      const t = clean(g.text);
      if (/^\d{4}(\s+\d{4})*$/.test(t) || t !== t.toUpperCase()) continue;
      if (/ESTANTE/i.test(t)) {
        const lines = inSeg
          .filter((x) => x.type === "overlay" && x.start > g.start)
          .flatMap((x) => String(x.text).split(/\s{2,}/).map(clean))
          .filter((x) => /\d{4}/.test(x));
        if (lines.length) {
          const a = anchor("Copa América 2021 Finalíssima títulos", g.start);
          push({ type: "list", start: a.t, dur: Math.min(5, 1.6 + lines.length * 0.45), prio: 6, synced: a.synced, data: { title: "Estante de troféus", rows: lines.map((l) => ({ text: l, flags: [] })) } });
          continue;
        }
      }
      const a = anchor(t, g.start);
      push({ type: "headline", start: a.t, dur: DUR.headline, prio: 4, synced: a.synced, data: { lines: headlineLines(t), mood: mood === "win" ? "win" : "" } });
    }

    // manchetes: viram card no trecho de narração; palavra-chave nos de opinião
    for (const g of inSeg.filter((x) => x.type === "headline" || (x.type === "overlay" && clean(x.text) === clean(x.text).toUpperCase() && !/^\W*$/.test(clean(x.text))))) {
      const t = clean(g.text);
      if (!t || /^\d{4}(\s+\d{4})*$/.test(t)) continue;
      if (/[a-zà-ú]{3,}/.test(t) && t !== t.toUpperCase()) continue;
      if (g.type === "overlay" && inSeg.some((x) => x.type === "stat_card" && /ESTANTE/i.test(x.text))) continue;
      const a = anchor(t, g.start);
      if (/CART[ÃA]O VERMELHO/i.test(t)) {
        const b = anchor("cartão vermelho", g.start);
        push({ type: "redcard", start: b.t, dur: DUR.redcard, prio: 7, synced: b.synced, data: { label: "EXPULSO!" } });
        continue;
      }
      if (seg.broll && t.length > 14) push({ type: "headline", start: a.t, dur: DUR.headline + 0.15 * headlineLines(t).length, prio: 3, synced: a.synced, data: { lines: headlineLines(t), mood: mood === "win" ? "win" : mood } });
      else overlays.push({ type: "keyword", start: a.t, dur: DUR.keyword, synced: a.synced, data: { text: t.replace(/\s*→\s*/g, " "), color: keywordColor(t, mood) } });
    }

    // CTA: na palavra de chamada ("inscreve", "segue", "comenta", "compartilha")
    for (const g of inSeg.filter((x) => x.type === "cta")) {
      const t = clean(g.text);
      if (/^(INSCREVER-SE|SEGUIR)$/i.test(t)) continue;
      const btn = inSeg.some((x) => x.type === "cta" && /INSCREV/i.test(x.text)) ? "INSCREVER-SE" : inSeg.some((x) => x.type === "cta" && /SEGUIR/i.test(x.text)) ? "SEGUIR" : "";
      const callT = findAnchor(words, "inscreve inscrever segue seguir comenta comentar compartilha salva curte", S - 0.3, E + 0.3);
      overlays.push({ type: "cta", start: callT !== null ? callT - LEAD : g.start, dur: DUR.cta, synced: callT !== null, data: { label: t.replace(/\s*→\s*/g, " • "), button: btn } });
    }
    if (dateG) {
      const a = anchor(dateG.text, dateG.start);
      overlays.push({ type: "chip", start: a.t, dur: DUR.chip, synced: a.synced, data: { text: clean(dateG.text), icon: "●" } });
    }

    // foto de apoio do trecho (b-roll)
    const img = images[seg.id];
    if (seg.broll && img) push({ type: "photo", start: S + 0.15, dur: DUR.photo, prio: 1, synced: true, flexible: true, data: { file: img.file, credit: `${img.creator} • ${img.license}`, label: clean(dateG ? dateG.text : /^BLOCO/i.test(seg.block) ? seg.block.replace(/^BLOCO\s+\d+\s*[—-]\s*/i, "") : "") } });
  });

  // ---------------------------------------------------------------- agenda
  // ordem de prioridade: gráficos sincronizados ficam onde a fala manda; os demais se ajustam
  cands.sort((a, b) => a.start - b.start || b.prio - a.prio);
  /** @type {any[]} */ const plates = [];
  const overlapsPlate = (a, b) => plates.find((p) => a < p.end + GAP && b > p.start - GAP);
  // na ordem da fala: cada gráfico entra na sua palavra; o anterior é encurtado para dar lugar
  for (const c of cands.filter((x) => !x.flexible).sort((a, b) => a.start - b.start || b.prio - a.prio)) {
    let start = c.start;
    let skip = false;
    // resolve contra o anterior; se ele sair, confere de novo com o que ficou antes dele
    for (let prev = plates[plates.length - 1]; prev && start < prev.end + GAP; prev = plates[plates.length - 1]) {
      if (start - GAP - prev.start >= MIN_PLATE) prev.end = start - GAP;
      else if (c.synced && c.prio > prev.prio) {
        plates.pop(); // o anterior ficaria curto demais: vale o mais importante
        continue;
      } else if (!c.synced) start = prev.end + GAP;
      else skip = true;
      break;
    }
    if (skip) continue;
    const end = Math.min(start + c.dur, c.segEnd + 0.8);
    if (end - start < MIN_PLATE) continue;
    plates.push({ ...c, start, end });
  }
  // fotos ocupam os espaços livres do trecho (sem cobrir gráficos sincronizados)
  for (const c of cands.filter((x) => x.flexible)) {
    let start = c.start;
    for (let tries = 0; tries < 8; tries++) {
      const end = Math.min(start + c.dur, c.segEnd - 0.2);
      if (end - start < 2.0) break;
      const clash = overlapsPlate(start, end);
      if (!clash) {
        plates.push({ ...c, start, end });
        break;
      }
      start = clash.end + GAP;
    }
  }
  plates.sort((a, b) => a.start - b.start);

  // layout de cada gráfico: mistura tela cheia (só o gráfico, voz ao fundo), janela e card
  const CYCLE = ["full", "gfxCard", "full", "camWindow"];
  let flip = 0;
  let nPhoto = 0;
  for (const p of plates) {
    if (p.type === "photo") p.layout = nPhoto++ % 3 === 2 ? "full" : "photoCard";
    else {
      p.layout = CYCLE[flip++ % CYCLE.length];
      if (p.layout === "gfxCard" && (p.type === "list" || p.type === "bars" || p.type === "era")) p.layout = "camWindow";
    }
    sfx.push({ t: p.start, kind: p.type === "photo" ? "whoosh_short" : "whoosh" });
    if (p.type === "score") sfx.push({ t: p.start + 0.32, kind: "hit" });
    if (p.type === "era") sfx.push({ t: p.start + 0.12, kind: "hit" });
    if (p.type === "number") sfx.push({ t: p.start + 0.05, kind: "hit" }, { t: p.start + 0.75, kind: "tick" });
    if (p.type === "redcard") sfx.push({ t: p.start + 0.42, kind: "hit" }, { t: p.start + 0.42, kind: "click" });
    if (p.type === "bars") sfx.push({ t: p.start + 0.3, kind: "riser" });
    if (p.type === "list") p.data.rows.forEach((_, i) => sfx.push({ t: p.start + 0.3 + i * 0.3, kind: "tick" }));
    if (p.type === "headline") p.data.lines.forEach((_, i) => sfx.push({ t: p.start + 0.05 + i * 0.16, kind: "pop" }));
  }

  // sobreposições sobre a câmera: fora das janelas de gráfico
  const busy = plates.map((p) => [p.start, p.end, p.layout]);
  /** @type {any[]} */ const placed = [];
  const lastEnd = {};
  for (const o of overlays.sort((a, b) => a.start - b.start)) {
    let start = o.start;
    const inPlate = busy.find(([x, y, l]) => start >= x - 0.1 && start < y && l !== "photoCard");
    if (inPlate) {
      if (o.synced && o.type !== "chip") continue; // fora do tempo da fala não serve
      start = inPlate[1] + 0.15;
    }
    if (lastEnd[o.type] && start < lastEnd[o.type]) start = lastEnd[o.type] + 0.1;
    let end = start + o.dur;
    const next = busy.find(([x, , l]) => x > start && x < end && l !== "photoCard");
    if (next) end = next[0];
    if (end - start < 0.9) continue;
    placed.push({ type: o.type, start, end, data: o.data });
    lastEnd[o.type] = end;
    if (o.type === "keyword") sfx.push({ t: start, kind: "pop" });
    if (o.type === "chip") sfx.push({ t: start, kind: "tick" });
    if (o.type === "cta") sfx.push({ t: start, kind: "pop" }, { t: start + 1.0, kind: "click" }, { t: start + 1.1, kind: "ding" });
  }

  // efeitos de tela
  /** @type {any[]} */ const fx = [];
  for (const v of vfx) {
    if (/FLASH/.test(v.name) && v.start < 0.5) fx.push({ type: "flash", start: 0, end: 0.35, data: {} });
    if (/CONFETTI/.test(v.name)) fx.push({ type: "confetti", start: v.start + 0.3, end: v.start + 3.3, data: { seed: Math.round(v.start * 10) } });
  }

  // legendas: com a câmera em tela cheia (ao lado da foto/card, deslocadas para o lado do rosto)
  const blockers = [...plates.filter((p) => p.layout === "camWindow" || p.layout === "full").map((p) => [p.start, p.end]), ...placed.filter((p) => p.type === "keyword" || p.type === "cta").map((p) => [p.start, p.end])];
  const sideCards = plates.filter((p) => p.layout === "gfxCard" || p.layout === "photoCard").map((p) => [p.start, p.end]);
  /** @type {any[]} */ const caps = [];
  for (const c of plan.captions || []) {
    const mid = (c.start + c.end) / 2;
    if (blockers.some(([x, y]) => mid >= x && mid < y)) continue;
    const cut = blockers.find(([x]) => x > c.start && x < c.end);
    const side = sideCards.some(([x, y]) => mid >= x && mid < y);
    caps.push({ type: "caption", start: c.start, end: cut ? cut[0] : c.end, data: { words: c.words, side } });
  }

  // ---------------------------------------------------------------- câmera virtual
  // base = enquadramento original da gravação (sem zoom, sem centralizar). O rosto só é
  // centralizado nos momentos de dinâmica: zoom seco em alguns jump cuts, aproximação
  // lenta nos trechos de suspense e punch-ins nas deixas.
  const pushes = vfx
    .filter((v) => /SLOW_ZOOM|BREATH|FREEZE_FRAME|SLOW_MOTION/.test(v.name) && v.start > 1)
    .map((v) => {
      const len = Math.min(v.duration || 4, 6);
      return { start: round3(v.start), end: round3(v.start + len), ramp: Math.min(3.5, len * 0.7), dz: 0.22 };
    });
  const inPush = (a, b) => pushes.some((p) => a < p.end && b > p.start);
  const bounds = [...new Set([0, ...plan.cuts.map((c) => round3(c.timeline))])].filter((b) => b < duration).sort((a, b) => a - b);
  const ZOOMS = [1.2, 1.28, 1.16];
  /** @type {Array<{start: number, end: number, z: number, c: number, style: string}>} */
  const shots = [];
  let nz = 0;
  bounds.forEach((b, i) => {
    const end = i + 1 < bounds.length ? bounds[i + 1] : duration;
    // a cada 3 jump cuts, um zoom seco no rosto (até ~3,5 s; depois volta ao plano original)
    const zoom = i % 3 === 2 && end - b > 1 && !inPush(b, Math.min(end, b + 3.5));
    if (zoom) {
      const zEnd = Math.min(end, b + 3.5);
      shots.push({ start: round3(b), end: round3(zEnd), z: ZOOMS[nz++ % ZOOMS.length], c: 1, style: "cut" });
      if (zEnd < end) shots.push({ start: round3(zEnd), end: round3(end), z: 1, c: 0, style: "base" });
    } else {
      shots.push({ start: round3(b), end: round3(end), z: 1, c: 0, style: "base" });
    }
  });
  const punches = vfx
    .filter((v) => /ZOOM_PUNCH_IN/.test(v.name) && !v.approximate)
    .map((v) => ({ start: v.start, end: v.start + Math.min(1.4, v.duration || 1.4), dz: 0.14 }));
  for (const p of punches) sfx.push({ t: p.start, kind: "whoosh_short" });
  // tremores suaves nos impactos (placar, cartão), nunca contínuos
  const shakes = plates.filter((p) => p.type === "score" || p.type === "redcard").map((p) => ({ t: p.start + 0.38, amp: 7 }));

  const items = [
    ...plates.map((p) => ({ type: p.type, start: p.start, end: p.end, layout: p.layout, data: p.data, z: 10 })),
    ...placed.map((p) => ({ ...p, z: 20 })),
    ...caps.map((c) => ({ ...c, z: 15 })),
    ...fx.map((f) => ({ ...f, z: f.type === "flash" ? 40 : 30 })),
  ].map((it, i) => ({ id: `${it.type}_${i}`, ...it }));

  const synced = plates.filter((p) => p.type !== "photo");
  return {
    fps,
    duration,
    items,
    shots,
    pushes,
    punches,
    shakes,
    fadeOut: (vfx.filter((v) => /FADE_TO_BLACK/.test(v.name)).map((v) => [v.start, v.start + v.duration]))[0] || null,
    sfx: sfx.filter((s) => s.t >= 0 && s.t < duration).sort((a, b) => a.t - b.t),
    stats: {
      plates: plates.filter((p) => p.type !== "photo").length,
      photos: plates.filter((p) => p.type === "photo").length,
      synced: `${synced.filter((p) => p.synced).length}/${synced.length}`,
      overlays: placed.length,
      captions: caps.length,
      shots: shots.length,
    },
  };
}

/**
 * Câmera virtual no tempo t.
 *   z = zoom; c = quanto o rosto é centralizado (0 = enquadramento original, 1 = rosto no centro);
 *   sx/sy = tremor amortecido.
 */
function cameraAt(d, t) {
  const shot = d.shots.find((s) => t >= s.start && t < s.end) || d.shots[d.shots.length - 1];
  let z = shot.z;
  let c = shot.c;
  for (const p of d.pushes || []) {
    if (t >= p.start && t < p.end) {
      const q = Math.min(1, (t - p.start) / p.ramp);
      const e = q * q * (3 - 2 * q); // aproximação suave, como câmera andando
      z = Math.max(z, 1 + p.dz * e);
      c = Math.max(c, e);
    }
  }
  for (const p of d.punches) {
    if (t >= p.start && t < p.end) {
      const q = 1 - Math.pow(1 - Math.min(1, (t - p.start) / 0.22), 3);
      z += p.dz * q;
      c = Math.max(c, q);
    }
  }
  let sx = 0;
  let sy = 0;
  for (const s of d.shakes) {
    const u = t - s.t;
    if (u >= 0 && u < 0.6) {
      const decay = Math.exp(-u * 6);
      // ~2 Hz com amortecimento: balanço suave, não vibração
      sx += s.amp * Math.sin(u * 2 * Math.PI * 2.1) * decay;
      sy += s.amp * 0.6 * Math.sin(u * 2 * Math.PI * 1.7 + 0.8) * decay;
    }
  }
  return { z, c, sx, sy };
}

function round3(t) {
  return Math.round(t * 1000) / 1000;
}

module.exports = { direct, cameraAt, parseScore, parseNumber, headlineLines, anchorKeys, findAnchor, wordTokens, clean };
