"use strict";

/**
 * Diretor para o roteiro com MODOS (o formato do Everton):
 *
 *   [CAM]       câmera em tela cheia + legenda; textos/enquete/CTA por cima
 *   [CAM+MG]    gráfico ocupando a tela e a câmera pequena no canto (borda verde-limão)
 *   [MG+VO]     só o gráfico, com a voz por baixo
 *   [LANCE+VO]  sem o vídeo do lance: o gráfico do trecho (ou os cards de quem é citado)
 *
 * Cada componente (cards, campinho, placares...) entra no começo do trecho e cada
 * jogador/placar aparece na hora em que é FALADO (tempo real da transcrição).
 */

const { findAnchor, wordTokens } = require("./director");
const { close } = require("../roteiro/align");
const TEAMS = require("../roteiro/times.json").times;

const MIN_PLATE = 1.0;

function norm(s) {
  return String(s || "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9 ]+/g, " ")
    .trim();
}

/**
 * @param {any} plan
 * @param {{assets?: any}} [opts]
 */
function directModes(plan, opts = {}) {
  const fps = plan.sequence.fps;
  const last = plan.cuts.reduce((m, c) => Math.max(m, c.timeline + (c.end - c.start)), 0);
  const duration = Math.round(last * fps) / fps;
  const segments = (plan.meta && plan.meta.segments) || [];
  const vfx = plan.vfx || [];
  const assets = opts.assets || { players: {}, teams: {} };

  const words = [];
  for (const c of plan.captions || []) for (const w of c.words) words.push({ w: w.w, s: w.s, e: w.e, tok: wordTokens(w.w) });
  words.sort((a, b) => a.s - b.s);

  /** hora em que o nome é falado (sobrenome, nome ou nome completo; tolera erro de transcrição) */
  const nameTime = (name, from, to) => {
    const ks = norm(name).split(" ").filter((k) => k.length >= 3);
    if (!ks.length) return null;
    const keys = [...new Set([ks[ks.length - 1], ks[0]])].filter((k) => k.length >= 4 || ks.length === 1);
    for (const w of words) {
      if (w.s < from || w.s >= to) continue;
      const t = norm(w.w).replace(/ /g, "");
      if (!t) continue;
      if (keys.some((k) => t === k || close(t, k) || (k.length >= 5 && t.length >= 5 && (t.startsWith(k.slice(0, 5)) || k.startsWith(t.slice(0, 5)))))) return w.s;
    }
    // não falou o nome: onde ele estaria pela FALA do roteiro (mesmo lugar ou perto)
    const ap = aproximado(name);
    return ap !== null && ap >= from - 0.5 && ap < to ? ap : null;
  };
  const anchorT0 = (text, from, to) => (text ? findAnchor(words, text, from, to) : null);
  /** trecho atual: tempo "mais ou menos" de uma palavra do roteiro que ele falou diferente */
  let palavrasSeg = [];
  const aproximado = (text) => {
    const ks = norm(text).split(" ").filter((k) => k.length >= 3);
    if (!ks.length) return null;
    for (const p of palavrasSeg) {
      const t = norm(p.w).replace(/ /g, "");
      if (ks.some((k) => t === k || close(t, k))) return p.t;
    }
    return null;
  };
  const anchorT = (text, from, to) => anchorT0(text, from, to) ?? (text ? aproximado(text) : null);

  const photo = (name) => (assets.players && assets.players[name] && assets.players[name].photo) || "";
  const crestOf = (sigla) => (assets.teams && assets.teams[sigla] && assets.teams[sigla].crest) || "";
  const colorOf = (sigla) => (TEAMS.find((t) => t.sigla === sigla) || {}).cor || "";
  const dress = (c) => ({ ...c, photo: photo(c.name), crest: crestOf(c.sigla), color: colorOf(c.sigla) });

  /** @type {any[]} */ const plates = [];
  /** @type {any[]} */ const overlays = [];
  /** @type {any[]} */ const sfx = [];
  /** @type {any[]} */ const shakes = [];

  segments.forEach((seg, si) => {
    const S = seg.start;
    palavrasSeg = seg.palavras || [];
    // o campinho que continua nos trechos seguintes do bloco vai até o fim do último
    const comps = (seg.comps || []).filter((c) => !c.continues);
    const modo = seg.modo || "CAM";
    let E = si + 1 < segments.length ? segments[si + 1].start : duration;
    const kicker = String(seg.sub || seg.block || "")
      .replace(/^\d+\.\s*/, "")
      .split(/[:(—]/)[0]
      .trim()
      .toUpperCase();

    // lance sem o vídeo do lance: selos vão por cima da câmera (não vale tela parada só com um selo)
    if (modo === "LANCE+VO") for (const c of comps) if (c.type === "stamps" && !comps.some((x) => x.type === "cards" || x.type === "redcard")) c.place = "overlay";
    const plateComps = comps.filter((c) => c.place === "plate");
    const layoutFor = (c) => (c.type === "var" ? "full" : modo === "CAM+MG" || modo === "CAM" ? "camPip" : "full");

    // horários de entrada dos componentes de tela no trecho
    const starts = plateComps.map((c, i) => {
      if (i === 0) return S;
      const t = c.type === "cards" ? nameTime(c.data.cards[0].name, S, E) : anchorT(c.anchor, S, E);
      return t === null ? NaN : t - 0.15;
    });
    for (let i = 1; i < starts.length; i++) {
      if (plateComps[i - 1].short && (Number.isNaN(starts[i]) || starts[i] < starts[i - 1] + 1.8)) starts[i] = starts[i - 1] + 1.8;
      if (Number.isNaN(starts[i])) {
        let n = i + 1;
        while (n < starts.length && Number.isNaN(starts[n])) n++;
        const nt = n < starts.length ? starts[n] : E;
        starts[i] = starts[i - 1] + (nt - starts[i - 1]) / (n - i + 1);
      }
      starts[i] = Math.max(starts[i], starts[i - 1] + 1.2);
    }
    plateComps.forEach((c, i) => {
      const start = starts[i];
      let end = i + 1 < starts.length ? starts[i + 1] : E;
      if (c.type === "pitch") {
        const span = segments.findIndex((x, k) => k > si && !(x.comps || []).some((q) => q.type === "pitch" && q.continues));
        end = span > si ? segments[span].start : duration;
        if (span < 0) end = duration;
      }
      // VAR sozinho num trecho de câmera: só a "piscada" de entrada; depois volta a câmera
      if (c.type === "var" && (modo === "CAM" || plateComps.length === 1)) end = Math.min(end, start + 3.0);
      if (c.short) end = Math.min(end, start + 1.8);
      if (c.type === "redcard") end = Math.min(end, start + 4.5);
      if (end - start < MIN_PLATE) return;
      const p = { type: c.type, start, end, layout: layoutFor(c), data: JSON.parse(JSON.stringify(c.data)) };
      const d = p.data;
      const rel = (t) => (t === null ? undefined : Math.max(0, t - start));

      if (c.type === "cards") {
        d.kicker = kicker;
        d.mood = d.cards.every((x) => x.rating != null && x.rating < 6.5) ? "worst" : "";
        d.cards = d.cards.map((x) => ({ ...dress(x), at: rel(nameTime(x.name, start - 0.3, end)) }));
        // cards na ordem da fala; quem não foi achado entra logo depois do anterior
        let prev = 0.25;
        for (const x of d.cards) {
          if (x.at === undefined || x.at < prev - 0.05) x.at = prev;
          prev = x.at + 0.3;
        }
        for (const x of d.cards) {
          sfx.push({ t: start + x.at, kind: "pop" });
          if (x.rating != null) sfx.push({ t: start + x.at + 0.85, kind: "ding" });
          if (x.red) {
            sfx.push({ t: start + x.at + 0.55, kind: "hit" });
            shakes.push({ t: start + x.at + 0.6, amp: 6 });
          }
        }
        if (d.stat) for (let k = 0; k < Math.min(10, d.stat.to); k++) sfx.push({ t: start + 0.6 + (k * Math.min(2.4, (end - start) * 0.5)) / d.stat.to, kind: "tick" });
      } else if (c.type === "pitch") {
        const all = [...d.rows.flat(), ...(d.bench || [])];
        for (const x of all) Object.assign(x, dress(x), { at: rel(nameTime(x.name, start, end)) });
        d.rows = d.rows.map((r) => r.map((x) => all.find((y) => y.name === x.name) || x));
        for (const x of all) if (x.at !== undefined) sfx.push({ t: start + x.at, kind: x.rating >= 10 && !d.worst ? "boom" : "pop" });
        sfx.push({ t: start + 0.05, kind: "hit" });
      } else if (c.type === "scoregrid") {
        for (const g of d.groups)
          for (const m of g.games) {
            m.crestA = crestOf(m.siglaA);
            m.crestB = crestOf(m.siglaB);
            m.at = rel(anchorT(m.anchor, start - 0.3, end));
            if (m.at !== undefined) sfx.push({ t: start + m.at, kind: "tick" });
          }
      } else if (c.type === "scoreseq") {
        d.crestA = crestOf(d.siglaA);
        d.crestB = crestOf(d.siglaB);
      } else if (c.type === "duel") {
        d.a.crest = crestOf(d.a.sigla);
        d.b.crest = crestOf(d.b.sigla);
        sfx.push({ t: start + 0.2, kind: "riser" }, { t: start + 1.4, kind: "boom" });
      } else if (c.type === "var") {
        sfx.push({ t: start, kind: "glitch" }, { t: start + 0.3, kind: "tick" });
      } else if (c.type === "stamps") {
        d.items.forEach((it, k) => {
          const t = anchorT(it.text, start, end);
          it.at = t === null ? 0.3 + k * Math.min(1.2, (end - start - 0.6) / d.items.length) : t - start;
          sfx.push({ t: start + it.at + 0.12, kind: "hit" });
          if (it.kind === "bad") shakes.push({ t: start + it.at + 0.15, amp: 5 });
        });
      } else if (c.type === "bignum") {
        d.times = bigTimes(d, S, E, start);
        d.times.forEach((t) => {
          sfx.push({ t: start + t + 0.3, kind: "boom" });
          shakes.push({ t: start + t + 0.32, amp: 9 });
        });
      } else if (c.type === "redcard") {
        sfx.push({ t: start + 0.42, kind: "hit" });
        shakes.push({ t: start + 0.45, amp: 7 });
      } else if (c.type === "vinheta") {
        sfx.push({ t: start + 0.15, kind: "hit" });
      } else if (c.type === "fotos") {
        // imagens achadas na internet (jogadores.py → jogadores.json "imagens"); sem imagem, sem placa
        d.items = d.items
          .map((it) => ({ ...it, file: (assets.imagens && assets.imagens[it.query] && assets.imagens[it.query].file) || "", crest: crestOf(it.sigla), at: rel(it.anchor ? nameTime(it.anchor, start - 0.3, end) ?? anchorT(it.anchor, start - 0.3, end) : null) }))
          .filter((it) => it.file);
        if (!d.items.length) return;
        let prev = 0.2;
        for (const it of d.items) {
          if (it.at === undefined || it.at < prev - 0.05) it.at = prev;
          prev = it.at + 0.4;
          sfx.push({ t: start + it.at, kind: "pop" });
        }
      }
      if (c.type !== "var") sfx.push({ t: start, kind: "whoosh" });
      plates.push(p);
    });

    // sobreposições sobre a câmera
    for (const c of comps.filter((x) => x.place === "overlay")) {
      const d = JSON.parse(JSON.stringify(c.data));
      if (c.type === "headline") {
        let t0 = S + 0.4;
        (d.lines || []).forEach((l, k) => {
          const t = nameTime(l.text, S, E) ?? anchorT(l.text, S, E);
          const st = Math.max(t0, t !== null ? t - 0.1 : t0);
          overlays.push({ type: "keyword", start: st, end: Math.min(E, st + 1.4), data: { text: l.text, color: k === 1 ? "red" : "white" } });
          sfx.push({ t: st, kind: "pop" });
          t0 = st + 0.5;
        });
      } else if (c.type === "cta") {
        const t = findAnchor(words, "inscreve inscrever segue seguir comenta comentar compartilha curte like", S - 0.3, E + 0.3);
        const st = t !== null ? t - 0.12 : S + 0.5;
        overlays.push({ type: "cta", start: st, end: Math.min(E + 0.5, st + 2.8), data: { label: d.label, button: d.button, done: d.button === "CURTIR" ? "CURTIDO ✓" : undefined } });
        sfx.push({ t: st, kind: "pop" }, { t: st + 1.0, kind: "click" }, { t: st + 1.1, kind: "ding" });
      } else if (c.type === "poll") {
        const st = S + Math.min(1.0, (E - S) * 0.2);
        overlays.push({ type: "poll", start: st, end: Math.min(E, st + Math.max(4, Math.min(7, E - st))), data: d });
        sfx.push({ t: st, kind: "pop" });
      } else if (c.type === "bignum") {
        d.overlay = true;
        d.times = bigTimes(d, S, E, S);
        const st = S + Math.max(0, Math.min(...d.times) - 0.05);
        d.times = d.times.map((t) => t - (st - S));
        overlays.push({ type: "bignum", start: st, end: Math.min(E, st + Math.max(...d.times) + 1.6), data: d });
        d.times.forEach((t) => {
          sfx.push({ t: st + t + 0.3, kind: "boom" });
          shakes.push({ t: st + t + 0.32, amp: 9 });
        });
      } else if (c.type === "stamps") {
        d.overlay = true;
        // cada selo na hora em que é falado ("anulado", "não é pênalti")
        d.items.forEach((it, k) => {
          const t = anchorT(it.text, S, E);
          const st = t !== null ? t - 0.2 : S + 0.5 + k * 3.2;
          overlays.push({ type: "stamps", start: st, end: Math.min(E, st + 2.8), data: { overlay: true, items: [{ ...it, at: 0.1 }] } });
          sfx.push({ t: st + 0.22, kind: "hit" });
        });
      }
    }
  });

  /** três "10" caindo: um em cada palavra a partir de "três"/"10" na fala */
  function bigTimes(d, S, E, base) {
    const n = d.count || 1;
    const idx = words.findIndex((w) => w.s >= S && w.s < E && (w.tok.has(String(n)) || w.tok.has(String(d.text))));
    if (idx >= 0) {
      const out = [];
      for (let k = 0; k < n && words[idx + k] && words[idx + k].s < E; k++) out.push(Math.max(0, words[idx + k].s - base));
      while (out.length < n) out.push(out[out.length - 1] + 0.35);
      return out;
    }
    return Array.from({ length: n }, (_, k) => Math.max(0, S - base) + 0.3 + k * 0.4);
  }

  plates.sort((a, b) => a.start - b.start);
  // selos sobre a câmera: um de cada vez
  const st = overlays.filter((o) => o.type === "stamps").sort((a, b) => a.start - b.start);
  for (let i = 1; i < st.length; i++) {
    if (st[i].start < st[i - 1].end + 0.1) {
      const len = st[i].end - st[i].start;
      st[i].start = st[i - 1].end + 0.1;
      st[i].end = st[i].start + len;
    }
  }
  // sem sobreposição entre placas de trechos vizinhos
  for (let i = 1; i < plates.length; i++) if (plates[i].start < plates[i - 1].end) plates[i - 1].end = plates[i].start;

  // legendas só com a câmera em tela cheia
  const blockers = plates.filter((p) => p.layout === "full" || p.layout === "camPip").map((p) => [p.start, p.end]);
  const kw = overlays.filter((o) => o.type === "keyword" || o.type === "cta").map((o) => [o.start, o.end]);
  const caps = [];
  for (const c of plan.captions || []) {
    const mid = (c.start + c.end) / 2;
    if ([...blockers, ...kw].some(([x, y]) => mid >= x && mid < y)) continue;
    const cut = [...blockers, ...kw].find(([x]) => x > c.start && x < c.end);
    caps.push({ type: "caption", start: c.start, end: cut ? cut[0] : c.end, data: { words: c.words, side: false } });
  }

  // câmera: plano fixo; punch-ins nas deixas do EFEITO; aproximação lenta quando pedida
  const round3 = (t) => Math.round(t * 1000) / 1000;
  const shots = [{ start: 0, end: round3(duration), z: 1, c: 0, style: "base" }];
  const pushes = vfx
    .filter((v) => /SLOW_ZOOM|BREATH/.test(v.name) && v.start > 1)
    .map((v) => {
      const len = Math.min(v.duration || 4, 6);
      return { start: round3(v.start), end: round3(v.start + len), ramp: Math.min(3.5, len * 0.7), dz: 0.18 };
    });
  const punches = vfx
    .filter((v) => /ZOOM_PUNCH_IN/.test(v.name))
    .map((v) => ({ start: v.start, end: v.start + Math.min(1.4, v.duration || 1.4), dz: 0.2 }));
  for (const p of punches) sfx.push({ t: p.start, kind: "whoosh_short" });

  const items = [
    ...plates.map((p) => ({ type: p.type, start: p.start, end: p.end, layout: p.layout, data: p.data, z: 10 })),
    ...overlays.map((o) => ({ ...o, z: 20 })),
    ...caps.map((c) => ({ ...c, z: 15 })),
    { type: "watermark", start: 0, end: duration, data: { text: "@detto.galo" }, z: 30 },
  ].map((it, i) => ({ id: `${it.type}_${i}`, ...it }));

  return {
    fps,
    duration,
    items,
    shots,
    pushes,
    punches,
    shakes,
    fadeOut: vfx.filter((v) => /FADE_TO_BLACK/.test(v.name)).map((v) => [v.start, v.start + v.duration])[0] || null,
    sfx: sfx.filter((s) => s.t >= 0 && s.t < duration).sort((a, b) => a.t - b.t),
    stats: {
      modo: "roteiro com MODO",
      plates: plates.length,
      porTipo: plates.reduce((m, p) => ((m[p.type] = (m[p.type] || 0) + 1), m), {}),
      overlays: overlays.length,
      captions: caps.length,
      fotos: `${Object.values(assets.players || {}).filter((x) => x.photo).length} jogadores, ${Object.values(assets.teams || {}).filter((x) => x.crest).length} escudos`,
    },
  };
}

module.exports = { directModes };
