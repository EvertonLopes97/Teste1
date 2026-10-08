"use strict";

/**
 * "Diretor" da edição dinâmica: transforma o EDIT_PLAN em uma timeline no estilo
 * das referências (Reels/YouTube de futebol):
 *
 *  - placas de tela cheia (era, placar com bandeiras, número gigante, lista, barras,
 *    texto) intercaladas com a facecam nos trechos de narração (onde entraria b-roll);
 *  - palavras-chave gigantes, chip de data e CTA sobre a facecam nos trechos de opinião;
 *  - legenda dinâmica só quando a facecam está limpa;
 *  - facecam reenquadrada a cada corte/frase (aberto, médio, fechado) + punch-ins;
 *  - eventos de SFX sincronizados com cada entrada.
 */

const { flagCode } = require("./flags");

const DUR = { era: 1.7, score: 2.8, number: 2.2, headline: 2.4, bars: 3.0, keyword: 1.5, chip: 2.6, cta: 2.4 };
const MIN_FACE = 1.0; // facecam mínima entre placas (s)

/** Remove emojis e símbolos decorativos. */
function clean(s) {
  return String(s || "")
    .replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}\u{200D}\u{2B00}-\u{2BFF}\u{E0000}-\u{E007F}]/gu, "")
    .replace(/\s+/g, " ")
    .trim();
}

/** "ARGENTINA 2 x 1 HUNGRIA (pênaltis: 4 x 2 Alemanha) • AMISTOSO • 2005" */
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
  if (/\d|→/.test(a + b)) return null; // placar animado "1 x 0 → 1 x 1 → 1 x 2"
  const sa = Number(m[2]);
  const sb = Number(m[3]);
  const fa = flagCode(a);
  const fb = flagCode(b);
  if (!fa && !fb) return null;
  let loss = lossMark;
  const argA = fa === "ar";
  const argB = fb === "ar";
  if (argA || argB) {
    if (sa !== sb) loss = argA ? sa < sb : sb < sa;
    else {
      const pen = paren.match(/(\d+)\s*x\s*(\d+)\s*(.*)$/);
      if (pen && pen[3]) loss = flagCode(pen[3]) !== "ar";
    }
  }
  return {
    a: { name: a, flag: fa },
    b: { name: b, flag: fb },
    sa,
    sb,
    sub: paren,
    comp: rest.join(" • "),
    loss,
  };
}

/**
 * Número principal de um texto de contador ("FINAIS PERDIDAS: 2", "+85.000", "113'",
 * "MENOS DE 2 MINUTOS" → topo "MENOS DE", número 2, rótulo "MINUTOS").
 */
function parseNumber(text) {
  const raw = clean(text);
  if (/\d{2}:\d{2}/.test(raw)) return null; // cronômetro "00:00 01:5X"
  const m = raw.match(/([+]?)(\d{1,3}(?:\.\d{3})+|\d+)(['º°ª]?)/);
  if (!m) return null;
  const num = Number(m[2].replace(/\./g, ""));
  const tidy = (x) => x.replace(/^[\s:•-]+|[\s:•-]+$/g, "").trim();
  let before = tidy(raw.slice(0, m.index));
  let after = tidy(raw.slice(m.index + m[0].length));
  // descrição de edição (minúsculas) não vira texto de tela
  const upper = (x) => (x && x === x.toUpperCase() ? x : x.length <= 3 ? x.toUpperCase() : "");
  before = upper(before);
  after = upper(after);
  const label = before && after ? after : before || after;
  const top = before && after ? before : "";
  return { display: m[0], num, prefix: m[1], suffix: m[3], thousands: m[2].includes("."), label, top };
}

/** Quebra texto de manchete em 2–3 linhas, com a do meio em caixa amarela. */
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

/**
 * @param {any} plan EDIT_PLAN (com meta.segments e captions)
 * @param {{seed?: number, facecamColorFx?: boolean}} [opts]
 */
function direct(plan, opts = {}) {
  const fps = plan.sequence.fps;
  const last = plan.cuts.reduce((m, c) => Math.max(m, c.timeline + (c.end - c.start)), 0);
  const duration = Math.round(last * fps) / fps;
  const segments = (plan.meta && plan.meta.segments) || [];
  const graphics = (plan.graphics || []).slice().sort((a, b) => a.start - b.start);
  const markers = plan.markers || [];
  const vfx = plan.vfx || [];

  /** @type {any[]} */ const plates = []; // {type,start,end,data}
  /** @type {any[]} */ const overlays = [];
  /** @type {any[]} */ const sfx = [];
  let uid = 0;
  const id = (p) => `${p}_${++uid}`;

  let prevYear = 2005;
  let cursor = 0; // fim da última placa (timeline)

  segments.forEach((seg, si) => {
    const S = seg.start;
    const E = si + 1 < segments.length ? segments[si + 1].start : duration;
    const inSeg = graphics.filter((g) => g.start >= S - 0.01 && g.start < E && g.type !== "generic" && g.type !== "timeline_bar");
    const dateG = inSeg.find((g) => g.type === "date_stamp");
    const mood = seg.mood;

    // ---------- cartão de era no começo de cada bloco
    const blockMarker = markers.find((m) => m.color === "blue" && Math.abs(m.time - S) < 0.05);
    if (blockMarker && /^BLOCO/i.test(blockMarker.name)) {
      const tl = markers.find((m) => /LINHA DO TEMPO/.test(m.name) && Math.abs(m.time - S) < 0.05);
      const year = (tl && tl.name.match(/(\d{4})/)?.[1]) || blockMarker.name.match(/\((\d{4})/)?.[1] || blockMarker.name.match(/(\d{4})/)?.[1];
      const title = blockMarker.name.replace(/^BLOCO\s+\d+\s*[—-]\s*/i, "").replace(/\s*\(\d{4}(?:[–-]\d{4})?\)\s*$/, "");
      if (year) {
        const start = Math.max(S, cursor);
        plates.push({ type: "era", start, end: start + DUR.era, data: { year, title, prevYear, mood: "" } });
        sfx.push({ t: start, kind: "whoosh" }, { t: start + 0.12, kind: "hit" });
        prevYear = Number(year);
        cursor = start + DUR.era;
      } else {
        overlays.push({ type: "keyword", start: Math.max(S, cursor) + 0.2, dur: 1.6, data: { text: clean(title), color: "" } });
      }
    }

    // ---------- candidatos
    /** @type {any[]} */
    const cands = [];
    const scores = inSeg.filter((g) => g.type === "scoreboard").map((g) => ({ g, s: parseScore(g.text) }));
    const parsedScores = scores.filter((x) => x.s);
    if (parsedScores.length >= 3) {
      const titleG = scores.find((x) => !x.s) || null;
      const title = clean((titleG && titleG.g.text) || (dateG && dateG.text) || "Jogo a jogo");
      const rows = parsedScores.map(({ s }) => ({
        text: `${s.a.name} ${s.sa} x ${s.sb} ${s.b.name}`,
        flags: [s.a.flag, s.b.flag].filter(Boolean),
        note: clean([s.sub, s.comp].filter(Boolean).join(" • ")).slice(0, 34),
        loss: s.loss,
      }));
      const dur = Math.min(4.6, 1.2 + rows.length * 0.35 + 1.0);
      cands.push({ type: "list", pref: parsedScores[0].g.start, dur, prio: 5, data: { title, rows, mood: "" } });
    } else {
      for (const { g, s } of scores) {
        if (s) {
          cands.push({
            type: "score",
            pref: g.start,
            dur: DUR.score,
            prio: 6,
            data: { comp: s.comp, a: s.a, b: s.b, sa: s.sa, sb: s.sb, sub: s.sub, date: dateG ? clean(dateG.text) : "", mood: s.loss ? "loss" : "" },
          });
        } else if (/\d\s*x\s*\d/.test(g.text)) {
          cands.push({ type: "headline", pref: g.start, dur: DUR.headline + 0.4, prio: 3, data: { lines: headlineLines(g.text), mood } });
        }
      }
    }
    for (const g of inSeg.filter((x) => x.type === "counter")) {
      const t = clean(g.text);
      const bars = t.match(/MESSI\s+(\d+)\s+BATISTUTA\s+(\d+)/i);
      if (bars) {
        cands.push({ type: "bars", pref: g.start, dur: DUR.bars, prio: 5, data: { title: "Artilheiros da seleção", bars: [{ name: "Messi", value: Number(bars[1]) }, { name: "Batistuta", value: Number(bars[2]), gray: true }] } });
        continue;
      }
      t.split(/\s*→\s*/).forEach((part, k) => {
        const n = parseNumber(part);
        if (!n) return;
        cands.push({ type: "number", pref: g.start + k * 0.1, dur: DUR.number, prio: 4, data: { ...n, mood: /PERDID|0$/.test(part) && mood === "loss" ? "loss" : "" } });
      });
    }
    for (const g of inSeg.filter((x) => x.type === "stat_card")) {
      const t = clean(g.text);
      if (/^\d{4}(\s+\d{4})*$/.test(t)) continue; // "2014 2015 2016": ilustração, não texto
      if (t !== t.toUpperCase()) continue; // descrição de animação, não texto de tela
      if (/ESTANTE/i.test(t)) {
        const lines = inSeg
          .filter((x) => x.type === "overlay" && x.start > g.start)
          .flatMap((x) => String(x.text).split(/\s{2,}/).map(clean))
          .map((x) => x.trim())
          .filter((x) => /\d{4}/.test(x));
        if (lines.length) {
          cands.push({ type: "list", pref: g.start, dur: Math.min(4.6, 1.4 + lines.length * 0.4), prio: 5, data: { title: "Estante de troféus", rows: lines.map((l) => ({ text: l, flags: [] })), mood: "win" } });
          continue;
        }
      }
      cands.push({ type: "headline", pref: g.start, dur: DUR.headline, prio: 3, data: { lines: headlineLines(t), mood: seg.mood === "win" ? "win" : "" } });
    }

    for (const g of inSeg.filter((x) => x.type === "headline" || (x.type === "overlay" && clean(x.text) === clean(x.text).toUpperCase() && !/^\W*$/.test(clean(x.text))))) {
      const t = clean(g.text);
      if (!t || /^\d{4}(\s+\d{4})*$/.test(t)) continue;
      if (/[a-zà-ú]{3,}/.test(t) && t !== t.toUpperCase()) continue; // descrição ("split screen ...")
      if (g.type === "overlay" && inSeg.some((x) => x.type === "stat_card" && /ESTANTE/i.test(x.text))) continue;
      if (/CART[ÃA]O VERMELHO/i.test(t)) {
        cands.push({ type: "redcard", pref: g.start, dur: 2.4, prio: 6, data: { label: /EXPULSO/i.test(t) ? t.replace(/CART[ÃA]O VERMELHO\s*(3D)?/i, "").trim() || "EXPULSO!" : "EXPULSO!" } });
        continue;
      }
      if (seg.broll && t.length > 14) cands.push({ type: "headline", pref: g.start, dur: DUR.headline + 0.15 * headlineLines(t).length, prio: 2, data: { lines: headlineLines(t), mood: seg.mood === "win" ? "win" : seg.mood } });
      else overlays.push({ type: "keyword", start: g.start, dur: DUR.keyword, data: { text: t.replace(/\s*→\s*/g, " "), color: keywordColor(t, mood) } });
    }
    for (const g of inSeg.filter((x) => x.type === "cta")) {
      const t = clean(g.text);
      const btn = /INSCREV/i.test(t) ? "INSCREVER-SE" : /SEGUIR/i.test(t) ? "SEGUIR" : "";
      if (btn && t.replace(/[^A-Z]/gi, "").length <= 14) continue; // só o rótulo do botão: vai junto do CTA principal
      const hasBtn = inSeg.some((x) => x.type === "cta" && /SEGUIR|INSCREV/i.test(x.text));
      overlays.push({
        type: "cta",
        start: g.start,
        dur: DUR.cta,
        data: { label: t.replace(/\s*→\s*/g, " • "), button: hasBtn ? (/INSCREV/i.test(inSeg.map((x) => x.text).join(" ")) ? "INSCREVER-SE" : "SEGUIR") : "", done: "" },
      });
    }
    if (dateG) overlays.push({ type: "chip", start: dateG.start, dur: DUR.chip, data: { text: clean(dateG.text), icon: "●" } });

    // ---------- agenda das placas: intercala com facecam
    cands.sort((a, b) => a.pref - b.pref || b.prio - a.prio);
    for (const c of cands) {
      const minStart = cursor === 0 && S === 0 ? 0 : cursor + MIN_FACE;
      let start = Math.max(c.pref, minStart, S);
      let dur = c.dur;
      if (start + dur > E + 0.6) dur = Math.max(1.6, E + 0.6 - start);
      if (start + dur > E + 0.6 || start >= E) {
        // não coube: placas curtas viram palavra-chave sobre a facecam
        if (c.type === "number") overlays.push({ type: "keyword", start: Math.max(S, c.pref), dur: DUR.keyword, data: { text: `${c.data.display} ${c.data.label}`.trim(), color: "" } });
        continue;
      }
      plates.push({ type: c.type, start, end: start + dur, data: c.data });
      sfx.push({ t: start - 0.04, kind: "whoosh" });
      if (c.type === "score") sfx.push({ t: start + 0.32, kind: "hit" });
      if (c.type === "number") sfx.push({ t: start + 0.05, kind: "hit" }, { t: start + 0.75, kind: "tick" });
      if (c.type === "list") c.data.rows.forEach((_, i) => sfx.push({ t: start + 0.25 + i * Math.min(0.32, Math.max(0.12, (dur - 1.2) / c.data.rows.length)), kind: "tick" }));
      if (c.type === "bars") sfx.push({ t: start + 0.3, kind: "riser" });
      if (c.type === "redcard") sfx.push({ t: start + 0.42, kind: "hit" }, { t: start + 0.42, kind: "click" });
      if (c.type === "headline") c.data.lines.forEach((_, i) => sfx.push({ t: start + 0.05 + i * 0.16, kind: "pop" }));
      cursor = start + dur;
    }
  });

  // ---------- abertura com flash, letterbox e confete a partir dos VFX
  /** @type {any[]} */ const fx = [];
  for (const v of vfx) {
    if (/FLASH/.test(v.name) && v.start < 0.5) fx.push({ type: "flash", start: 0, end: 0.35, data: {} });
    if (/LETTERBOX/.test(v.name)) fx.push({ type: "letterbox", start: v.start, end: v.start + v.duration, data: {} });
    if (/CONFETTI/.test(v.name)) fx.push({ type: "confetti", start: v.start + 0.3, end: v.start + 3.3, data: { seed: Math.round(v.start * 10) } });
  }

  // ---------- sobreposições só onde a facecam está visível
  const busy = plates.map((p) => [p.start, p.end]);
  const isBusy = (a, b) => busy.some(([x, y]) => a < y && b > x);
  /** @type {any[]} */ const placed = [];
  const lastEnd = {};
  for (const o of overlays.sort((a, b) => a.start - b.start)) {
    let start = o.start;
    const plate = busy.find(([x, y]) => start >= x - 0.1 && start < y);
    if (plate) start = plate[1] + 0.15;
    // mesmo tipo não se sobrepõe
    if (lastEnd[o.type] && start < lastEnd[o.type]) start = lastEnd[o.type] + 0.1;
    let end = start + o.dur;
    const next = busy.find(([x]) => x > start && x < end);
    if (next) end = next[0];
    if (end - start < 0.9 || isBusy(start, start + 0.3)) continue;
    placed.push({ type: o.type, start, end, data: o.data });
    lastEnd[o.type] = end;
    if (o.type === "keyword") sfx.push({ t: start, kind: "pop" });
    if (o.type === "chip") sfx.push({ t: start, kind: "tick" });
    if (o.type === "cta") sfx.push({ t: start, kind: "pop" }, { t: start + 1.0, kind: "click" }, { t: start + 1.1, kind: "ding" });
  }

  // ---------- legendas: só com a facecam limpa (sem placa nem palavra-chave)
  const blockers = [...busy, ...placed.filter((p) => p.type === "keyword" || p.type === "cta").map((p) => [p.start, p.end])];
  /** @type {any[]} */ const caps = [];
  for (const c of plan.captions || []) {
    const mid = (c.start + c.end) / 2;
    if (blockers.some(([x, y]) => mid >= x && mid < y)) continue;
    const cut = blockers.find(([x]) => x > c.start && x < c.end);
    caps.push({ type: "caption", start: c.start, end: cut ? cut[0] : c.end, data: { words: c.words } });
  }

  // ---------- facecam: enquadramentos que mudam a cada corte/frase
  const FRAMES = [
    { z: 1.0, x: 0, y: 0 },
    { z: 1.24, x: 0.0, y: -0.07 },
    { z: 1.12, x: -0.05, y: -0.03 },
    { z: 1.32, x: 0.03, y: -0.09 },
    { z: 1.08, x: 0.05, y: -0.02 },
  ];
  const bounds = new Set([0]);
  for (const c of plan.cuts) bounds.add(round3(c.timeline));
  for (const p of plates) bounds.add(round3(p.end));
  const sorted = [...bounds].filter((b) => b < duration).sort((a, b) => a - b);
  /** @type {Array<{start: number, end: number, z: number, x: number, y: number}>} */
  const shots = [];
  let k = 0;
  sorted.forEach((b, i) => {
    const end = i + 1 < sorted.length ? sorted[i + 1] : duration;
    // planos longos ganham trocas extras (~3.2 s)
    const n = Math.max(1, Math.round((end - b) / 3.2));
    for (let j = 0; j < n; j++) {
      const a = b + ((end - b) * j) / n;
      const z = b + ((end - b) * (j + 1)) / n;
      if (z - a < 0.05) continue;
      k = (k + 2 + (j % 2)) % FRAMES.length;
      if (shots.length && FRAMES[k].z === shots[shots.length - 1].z) k = (k + 1) % FRAMES.length;
      shots.push({ start: round3(a), end: round3(z), ...FRAMES[k] });
    }
  });
  const punches = vfx
    .filter((v) => /ZOOM_PUNCH_IN/.test(v.name) && !v.approximate)
    .map((v) => ({ start: v.start, end: v.start + Math.min(1.4, v.duration || 1.4), dz: 0.16 }));
  for (const p of punches) sfx.push({ t: p.start, kind: "whoosh_short" });
  const ranges = (re) => vfx.filter((v) => re.test(v.name)).map((v) => [v.start, v.start + v.duration]);

  const items = [
    ...plates.map((p) => ({ ...p, z: 10 })),
    ...placed.map((p) => ({ ...p, z: 20 })),
    ...caps.map((c) => ({ ...c, z: 15 })),
    ...fx.map((f) => ({ ...f, z: f.type === "flash" ? 40 : 30 })),
  ].map((it) => ({ id: id(it.type), ...it }));

  return {
    fps,
    duration,
    items,
    shots,
    punches,
    // sépia/P&B do roteiro valem para imagens de arquivo (b-roll); na facecam só com opts.facecamColorFx
    filters: {
      desat: opts.facecamColorFx ? ranges(/DESATURATE/) : [],
      sepia: opts.facecamColorFx ? ranges(/SEPIA|FILM_GRAIN/) : [],
      shake: ranges(/CAMERA_SHAKE/),
    },
    fadeOut: ranges(/FADE_TO_BLACK/)[0] || null,
    sfx: sfx.filter((s) => s.t >= 0 && s.t < duration).sort((a, b) => a.t - b.t),
    stats: { plates: plates.length, overlays: placed.length, captions: caps.length, shots: shots.length },
  };
}

function round3(t) {
  return Math.round(t * 1000) / 1000;
}

module.exports = { direct, parseScore, parseNumber, headlineLines, clean };
