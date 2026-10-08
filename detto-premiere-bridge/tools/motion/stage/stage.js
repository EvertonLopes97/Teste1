/* global window, document */
"use strict";

/**
 * Motor de motion graphics determinístico: STAGE.render(t) desenha o estado exato
 * do tempo t (segundos). O renderizador captura quadro a quadro com o Chromium.
 *
 * Item: { id, type, start, end, data }
 */
(function () {
  const stage = document.getElementById("stage");
  /** @type {any[]} */
  let items = [];
  /** @type {Map<string, {el: HTMLElement, item: any}>} */
  const live = new Map();

  // ---------------------------------------------------------------- easing
  const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const prog = (t, a, d) => clamp((t - a) / d);
  const outCubic = (p) => 1 - Math.pow(1 - p, 3);
  const inCubic = (p) => p * p * p;
  const outBack = (p, s = 1.70158) => 1 + (s + 1) * Math.pow(p - 1, 3) + s * Math.pow(p - 1, 2);
  const outExpo = (p) => (p >= 1 ? 1 : 1 - Math.pow(2, -10 * p));

  /** saída comum: some nos últimos `d` segundos */
  const exitP = (lt, dur, d = 0.2) => inCubic(prog(lt, dur - d, d));

  function seeded(seed) {
    let s = seed >>> 0 || 1;
    return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
  }

  // ---------------------------------------------------------------- helpers DOM
  function h(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  /** fundo da placa vai no contêiner do layout (tela cheia ou card); o conteúdo fica em el */
  function plateBase(el, mood) {
    const wrap = el.__wrap || el;
    wrap.classList.add("plate");
    if (mood) wrap.classList.add(mood);
    const s = h("div", "streaks");
    wrap.insertBefore(s, wrap.firstChild);
    const b = h("div", "baseline");
    wrap.appendChild(b);
    return { streaks: s, baseline: b };
  }
  function animatePlate(refs, lt, dur) {
    refs.streaks.style.transform = `translateX(${(-lt * 60).toFixed(1)}px)`;
    refs.baseline.style.transform = `scaleX(${outCubic(prog(lt, 0.05, 0.5)).toFixed(3)})`;
  }
  function flag(code) {
    const d = h("div", "flag");
    if (code) d.style.backgroundImage = `url("${window.STAGE_ASSETS.flag(code)}")`;
    else d.style.background = "#22314f";
    return d;
  }
  let CANVAS_W = 1280; // largura do quadro de conteúdo em construção (cards são mais estreitos)
  function fitFont(text, max, min, perChar) {
    perChar = (perChar * CANVAS_W) / 1280;
    const longest = String(text)
      .split("\n")
      .reduce((m, l) => Math.max(m, l.length), 0);
    return Math.max(min, Math.min(max, Math.floor(perChar / Math.max(1, longest))));
  }

  // ---------------------------------------------------------------- tipos
  const TYPES = {
    era: {
      build(el, d) {
        const r = plateBase(el, d.mood);
        r.year = h("div", "era-year anton", d.year);
        r.title = h("div", "era-title anton", d.title || "");
        r.tl = h("div", "tl");
        r.fill = h("div", "fill");
        r.dot = h("div", "dot");
        const a = h("div", "lbl anton", "2005");
        a.style.left = "-20px";
        const b = h("div", "lbl anton", "2026");
        b.style.right = "-20px";
        r.tl.append(r.fill, r.dot, a, b);
        el.append(r.year, r.title, r.tl);
        return r;
      },
      update(r, d, lt, dur) {
        animatePlate(r, lt, dur);
        const e = outExpo(prog(lt, 0, 0.45));
        r.year.style.transform = `translateY(${(70 * (1 - e)).toFixed(1)}px) scale(${(1.35 - 0.35 * e).toFixed(3)})`;
        r.year.style.filter = `blur(${(12 * (1 - e)).toFixed(1)}px)`;
        r.year.style.opacity = String(e);
        const t2 = outCubic(prog(lt, 0.2, 0.35));
        r.title.style.opacity = String(t2);
        r.title.style.transform = `translateY(${(30 * (1 - t2)).toFixed(1)}px)`;
        const span = 2026 - 2005;
        const from = ((d.prevYear || 2005) - 2005) / span;
        const to = ((Number(d.year) || 2005) - 2005) / span;
        const m = outCubic(prog(lt, 0.25, 0.8));
        const pos = (from + (to - from) * m) * 100;
        r.fill.style.width = `${pos.toFixed(2)}%`;
        r.dot.style.left = `${pos.toFixed(2)}%`;
      },
    },

    score: {
      build(el, d) {
        const r = plateBase(el, d.mood);
        r.comp = h("div", "score-comp");
        if (d.comp) r.comp.appendChild(h("span", "pill", d.comp));
        r.a = h("div", "team");
        r.a.style.left = "60px";
        r.a.append(flag(d.a.flag), h("div", "name anton", d.a.name));
        r.b = h("div", "team");
        r.b.style.right = "60px";
        r.b.append(flag(d.b.flag), h("div", "name anton", d.b.name));
        r.num = h("div", "score-num anton");
        r.num.append(document.createTextNode(String(d.sa)), h("span", "x", "x"), document.createTextNode(String(d.sb)));
        r.sub = h("div", "score-sub", d.sub || "");
        r.date = h("div", "score-date");
        if (d.date) r.date.appendChild(h("span", "pill dark", d.date));
        el.append(r.comp, r.a, r.b, r.num, r.sub, r.date);
        return r;
      },
      update(r, d, lt, dur) {
        animatePlate(r, lt, dur);
        const ea = outCubic(prog(lt, 0.0, 0.35));
        r.a.style.transform = `translateX(${(-420 * (1 - ea)).toFixed(1)}px)`;
        r.b.style.transform = `translateX(${(420 * (1 - ea)).toFixed(1)}px)`;
        r.a.style.opacity = r.b.style.opacity = String(ea);
        const ps = prog(lt, 0.3, 0.3);
        const s = 0.2 + 0.8 * outBack(ps, 2.2);
        const shake = lt > 0.45 && lt < 0.75 ? Math.sin(lt * 90) * 8 * (1 - prog(lt, 0.45, 0.3)) : 0;
        r.num.style.transform = `translate(${shake.toFixed(1)}px, ${(-shake / 2).toFixed(1)}px) scale(${s.toFixed(3)})`;
        r.num.style.opacity = String(clamp(ps * 3));
        const ec = outCubic(prog(lt, 0.1, 0.3));
        r.comp.style.transform = `translateY(${(-80 * (1 - ec)).toFixed(1)}px)`;
        r.comp.style.opacity = String(ec);
        const eb = outCubic(prog(lt, 0.55, 0.3));
        r.sub.style.opacity = r.date.style.opacity = String(eb);
        r.date.style.transform = `translateY(${(40 * (1 - eb)).toFixed(1)}px)`;
      },
    },

    number: {
      build(el, d) {
        const r = plateBase(el, d.mood);
        if (d.top) {
          r.top = h("div", "score-comp");
          r.top.appendChild(h("span", "pill gold", d.top));
          el.appendChild(r.top);
        }
        r.num = h("div", `big-num anton${d.mood === "loss" ? " red" : ""}`);
        r.num.style.fontSize = `${fitFont(d.display, 330, 150, 1500)}px`;
        r.label = h("div", "big-label anton", d.label || "");
        r.label.style.fontSize = `${fitFont(d.label || "", 64, 40, 1700)}px`;
        el.append(r.num, r.label);
        return r;
      },
      update(r, d, lt, dur) {
        animatePlate(r, lt, dur);
        const c = outCubic(prog(lt, 0.1, 0.7));
        let txt = d.display;
        if (typeof d.num === "number" && d.num >= 2) {
          const v = Math.round(d.num * c);
          txt = `${d.prefix || ""}${d.thousands ? v.toLocaleString("pt-BR") : v}${d.suffix || ""}`;
        }
        r.num.textContent = txt;
        const p = outBack(prog(lt, 0, 0.35), 1.6);
        r.num.style.transform = `scale(${(0.6 + 0.4 * p).toFixed(3)})`;
        r.num.style.opacity = String(clamp(prog(lt, 0, 0.15)));
        const el2 = outCubic(prog(lt, 0.3, 0.35));
        r.label.style.opacity = String(el2);
        r.label.style.transform = `translateY(${(40 * (1 - el2)).toFixed(1)}px)`;
        if (r.top) r.top.style.opacity = String(outCubic(prog(lt, 0.15, 0.3)));
      },
    },

    headline: {
      build(el, d) {
        const r = plateBase(el, d.mood);
        r.wrap = h("div", "headline-plate");
        r.lines = (d.lines || []).map((l) => {
          const e = h("div", `hl-line anton${l.box ? " box" : ""}`, l.text);
          e.style.fontSize = `${fitFont(l.text, 104, 52, 1900)}px`;
          r.wrap.appendChild(e);
          return e;
        });
        el.appendChild(r.wrap);
        return r;
      },
      update(r, d, lt, dur) {
        animatePlate(r, lt, dur);
        r.lines.forEach((e, i) => {
          const p = outBack(prog(lt, 0.05 + i * 0.16, 0.3), 1.8);
          const rot = e.classList.contains("box") ? -2 : 0;
          e.style.opacity = String(clamp(prog(lt, 0.05 + i * 0.16, 0.12)));
          e.style.transform = `rotate(${rot}deg) scale(${(1.25 - 0.25 * p).toFixed(3)})`;
        });
      },
    },

    list: {
      build(el, d) {
        const r = plateBase(el, d.mood);
        r.title = h("div", "list-title anton", d.title || "");
        el.appendChild(r.title);
        const rows = d.rows.slice(0, 6);
        const gap = rows.length > 5 ? 80 : 92;
        r.rows = rows.map((row, i) => {
          const e = h("div", `row${row.loss ? " loss" : ""}`);
          e.style.top = `${180 + i * gap}px`;
          for (const f of row.flags || []) {
            const m = h("div", "mini");
            m.style.backgroundImage = `url("${window.STAGE_ASSETS.flag(f)}")`;
            e.appendChild(m);
          }
          e.appendChild(h("div", "txt anton", row.text));
          if (row.note) e.appendChild(h("div", "note", row.note));
          el.appendChild(e);
          return e;
        });
        return r;
      },
      update(r, d, lt, dur) {
        animatePlate(r, lt, dur);
        const et = outCubic(prog(lt, 0, 0.3));
        r.title.style.opacity = String(et);
        r.title.style.transform = `translateX(${(-60 * (1 - et)).toFixed(1)}px)`;
        const step = Math.min(0.32, Math.max(0.12, (dur - 1.2) / Math.max(1, r.rows.length)));
        r.rows.forEach((e, i) => {
          const p = outCubic(prog(lt, 0.25 + i * step, 0.3));
          e.style.opacity = String(p);
          e.style.transform = `translateX(${(900 * (1 - p)).toFixed(1)}px)`;
        });
      },
    },

    bars: {
      build(el, d) {
        const r = plateBase(el, d.mood);
        r.title = h("div", "list-title anton", d.title || "");
        r.wrap = h("div", "bars");
        const max = Math.max(...d.bars.map((b) => b.value));
        r.bars = d.bars.map((b) => {
          const e = h("div", `bar${b.gray ? " gray" : ""}`);
          e.dataset.h = String((b.value / max) * 330);
          const v = h("div", "v anton", "0");
          e.append(v, h("div", "n anton", b.name));
          r.wrap.appendChild(e);
          return { e, v, value: b.value };
        });
        el.append(r.title, r.wrap);
        return r;
      },
      update(r, d, lt, dur) {
        animatePlate(r, lt, dur);
        r.title.style.opacity = String(outCubic(prog(lt, 0, 0.3)));
        r.bars.forEach((b, i) => {
          const p = outCubic(prog(lt, 0.25 + i * 0.25, 0.8));
          b.e.style.height = `${(Number(b.e.dataset.h) * p).toFixed(1)}px`;
          b.v.textContent = String(Math.round(b.value * p));
        });
      },
    },

    redcard: {
      build(el, d) {
        const r = plateBase(el, "loss");
        r.card = h("div", "redcard");
        r.label = h("div", "redcard-label anton", d.label || "EXPULSO!");
        el.append(r.card, r.label);
        return r;
      },
      update(r, d, lt, dur) {
        animatePlate(r, lt, dur);
        const p = outBack(prog(lt, 0, 0.45), 1.4);
        const spin = (1 - outCubic(prog(lt, 0, 0.45))) * 540;
        const shake = lt > 0.45 && lt < 0.8 ? Math.sin(lt * 80) * 10 * (1 - prog(lt, 0.45, 0.35)) : 0;
        r.card.style.transform = `translate(${shake.toFixed(1)}px, ${(-500 * (1 - p)).toFixed(1)}px) perspective(800px) rotateY(${spin.toFixed(1)}deg) rotate(-8deg)`;
        const lp = outBack(prog(lt, 0.45, 0.3), 2.2);
        r.label.style.transform = `scale(${(0.3 + 0.7 * lp).toFixed(3)})`;
        r.label.style.opacity = String(clamp(prog(lt, 0.45, 0.1)));
      },
    },

    photo: {
      build(el, d) {
        const r = {};
        r.frame = h("div", "photo-frame");
        r.img = h("img", "photo-img");
        r.img.src = window.STAGE_ASSETS.file(d.file);
        r.frame.appendChild(r.img);
        if (d.label) r.frame.appendChild(h("div", "photo-label anton", d.label));
        el.append(r.frame, h("div", "photo-credit", `Foto: ${d.credit}`));
        return r;
      },
      update(r, d, lt, dur) {
        // Ken Burns: aproximação lenta e leve deriva
        const p = clamp(lt / dur);
        r.img.style.transform = `scale(${(1.04 + 0.1 * p).toFixed(4)}) translate(${(-1.5 * p).toFixed(2)}%, ${(-1 * p).toFixed(2)}%)`;
      },
    },

    keyword: {
      build(el, d) {
        const r = {};
        r.k = h("div", `keyword anton ${d.color || ""}`, d.text);
        r.k.style.fontSize = `${fitFont(d.text, 150, 64, 1900)}px`;
        el.appendChild(r.k);
        return r;
      },
      update(r, d, lt, dur) {
        const p = outBack(prog(lt, 0, 0.22), 2.4);
        const x = exitP(lt, dur, 0.15);
        const s = (1.9 - 0.9 * p) * (1 - 0.15 * x);
        r.k.style.transform = `rotate(-3deg) scale(${s.toFixed(3)})`;
        r.k.style.opacity = String(clamp(prog(lt, 0, 0.06)) * (1 - x));
      },
    },

    chip: {
      build(el, d) {
        const r = {};
        r.c = h("div", "chip");
        r.c.append(h("div", "ico", d.icon || "●"), h("div", "t anton", d.text));
        el.appendChild(r.c);
        return r;
      },
      update(r, d, lt, dur) {
        const p = outCubic(prog(lt, 0, 0.3));
        const x = exitP(lt, dur, 0.25);
        r.c.style.transform = `translateX(${(-560 * (1 - p) - 560 * x).toFixed(1)}px)`;
      },
    },

    cta: {
      build(el, d) {
        const r = {};
        r.w = h("div", "cta");
        r.lbl = h("div", "lbl anton", d.label || "");
        r.btn = h("div", "btn", d.button || "SEGUIR");
        r.w.append(r.lbl, document.createElement("br"), r.btn);
        r.hand = h("div", "hand");
        r.hand.innerHTML =
          '<svg viewBox="0 0 64 64" width="70" height="70"><path d="M24 6c3 0 5 2 5 5v17l2-1c3-1 6 0 7 3l1 2 2-1c3-1 6 1 6 4v1l2-1c3 0 5 2 5 5v9c0 8-6 14-14 14H30c-5 0-9-3-11-7l-8-15c-1-3 0-5 3-6 2-1 5 0 6 2l2 4V11c0-3 2-5 5-5z" fill="#fff" stroke="#000" stroke-width="3" stroke-linejoin="round"/></svg>';
        r.w.appendChild(r.hand);
        el.appendChild(r.w);
        return r;
      },
      update(r, d, lt, dur) {
        const p = outBack(prog(lt, 0, 0.3), 2);
        const x = exitP(lt, dur, 0.2);
        r.w.style.transform = `scale(${(p * (1 - 0.2 * x)).toFixed(3)})`;
        r.w.style.opacity = String(1 - x);
        const hm = outCubic(prog(lt, 0.45, 0.5));
        r.hand.style.left = `${(900 - 260 * hm).toFixed(1)}px`;
        r.hand.style.top = `${(240 - 120 * hm).toFixed(1)}px`;
        r.hand.style.opacity = String(clamp(prog(lt, 0.4, 0.1)) * (1 - prog(lt, 1.6, 0.3)));
        const click = lt > 1.0 && lt < 1.12;
        r.btn.style.transform = `scale(${click ? 0.9 : 1})`;
        const done = lt >= 1.1;
        r.btn.classList.toggle("done", done);
        r.btn.textContent = done ? d.done || "SEGUINDO ✓" : d.button || "SEGUIR";
      },
    },

    caption: {
      build(el, d) {
        const r = {};
        r.c = h("div", "caption");
        r.spans = d.words.map((w, i) => {
          if (i) r.c.appendChild(document.createTextNode(" "));
          const s = h("span", w.hl ? "hl" : "", w.w);
          r.c.appendChild(s);
          return s;
        });
        el.appendChild(r.c);
        return r;
      },
      update(r, d, lt, dur, t) {
        const p = outBack(prog(lt, 0, 0.12), 2);
        r.c.style.transform = `scale(${(0.85 + 0.15 * p).toFixed(3)})`;
        d.words.forEach((w, i) => {
          const s = r.spans[i];
          const visible = t >= w.s - 0.03;
          const on = t >= w.s - 0.03 && t < Math.max(w.e, w.s + 0.12);
          s.style.visibility = visible ? "visible" : "hidden";
          s.classList.toggle("on", on);
          s.style.transform = on ? "scale(1.07)" : "scale(1)";
        });
      },
    },

    flash: {
      build(el) {
        el.classList.add("flash");
        return {};
      },
      update(r, d, lt, dur, t, el) {
        el.style.opacity = String(1 - outCubic(prog(lt, 0, dur)));
      },
    },

    letterbox: {
      build(el) {
        el.classList.add("letterbox");
        const a = h("div", "b");
        a.style.top = "0";
        const b = h("div", "b");
        b.style.bottom = "0";
        el.append(a, b);
        return { a, b };
      },
      update(r, d, lt, dur) {
        const p = outCubic(prog(lt, 0, 0.4)) * (1 - outCubic(prog(lt, dur - 0.3, 0.3)));
        r.a.style.transform = `translateY(${(-84 * (1 - p)).toFixed(1)}px)`;
        r.b.style.transform = `translateY(${(84 * (1 - p)).toFixed(1)}px)`;
      },
    },

    confetti: {
      build(el, d) {
        el.classList.add("confetti");
        const rnd = seeded(d.seed || 7);
        const colors = ["#d4af37", "#e9ff3b", "#ffffff", "#75aadb"];
        const parts = [];
        for (let i = 0; i < 90; i++) {
          const p = h("i");
          p.style.background = colors[i % colors.length];
          el.appendChild(p);
          parts.push({ p, x: rnd() * 1280, d: rnd() * 0.8, v: 260 + rnd() * 320, r: rnd() * 720, sway: 20 + rnd() * 40 });
        }
        return { parts };
      },
      update(r, d, lt, dur) {
        for (const q of r.parts) {
          const tt = Math.max(0, lt - q.d);
          const y = -40 + tt * q.v;
          const x = q.x + Math.sin(tt * 3 + q.r) * q.sway;
          q.p.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) rotate(${(q.r + tt * 400).toFixed(0)}deg)`;
          q.p.style.opacity = String(1 - prog(lt, dur - 0.4, 0.4));
        }
      },
    },
  };

  // ---------------------------------------------------------------- layouts
  // coordenadas em px CSS do palco (1280x720 horizontal, 720x1280 vertical)
  const LAYOUTS = {
    horizontal: {
      W: 1280, H: 720,
      win: { x: 800, y: 96, w: 440, h: 528 },        // câmera em janela (camWindow)
      pcArea: { x: 24, y: 40, w: 756, h: 640 },        // área do conteúdo ao lado da janela
      card: { x: 44, y: 92, w: 560, h: 536 },          // gráfico em card (gfxCard)
      photo: { x: 56, y: 70, w: 560, h: 560 },         // foto em quadro (photoCard)
      side: { x: 0.66, y: 0.42, z: 1.3 },              // rosto deslocado quando há card ao lado
      face: { x: 0.5, y: 0.42 },
      faceInWin: 0.40,                                 // largura do rosto na janela (fração)
    },
    vertical: {
      W: 720, H: 1280,
      win: { x: 40, y: 70, w: 640, h: 600 },
      pcArea: { x: 40, y: 700, w: 640, h: 540 },
      card: { x: 30, y: 700, w: 660, h: 500 },
      photo: { x: 60, y: 690, w: 600, h: 520 },
      side: { x: 0.5, y: 0.28, z: 1.35 },
      face: { x: 0.5, y: 0.4 },
      faceInWin: 0.42,
    },
  };
  let L = LAYOUTS.horizontal;
  const SRC = { w: 1920, h: 1080 };
  const lerp = (a, b, k) => a + (b - a) * k;
  /** envelope de entrada/saída de um layout (0 → 1 → 0) */
  const envelope = (lt, dur) => outCubic(prog(lt, 0, 0.38)) * (1 - inCubic(prog(lt, dur - 0.3, 0.3)));

  const camWrap = h("div", "camwrap");
  const camImg = h("img", "cam");
  camWrap.appendChild(camImg);
  stage.appendChild(camWrap);

  function placeLayout(rec, k, lt, dur) {
    const { el, item } = rec;
    const pc = rec.pc;
    if (item.layout === "full") {
      // estilo tela cheia: só o gráfico, a câmera fica por trás (voz ao fundo)
      el.style.opacity = String(clamp(k * 1.8));
      el.style.transform = `scale(${(1.06 - 0.06 * k).toFixed(4)})`;
      if (pc) {
        const sc = Math.min(L.W / rec.pcW, L.H / 720);
        pc.style.transform = `translate(${((L.W - rec.pcW * sc) / 2).toFixed(1)}px, ${((L.H - 720 * sc) / 2).toFixed(1)}px) scale(${sc.toFixed(4)})`;
      }
    } else if (item.layout === "camWindow") {
      el.style.cssText = "";
      el.style.zIndex = String(item.z || 0);
      el.style.opacity = String(clamp(k * 1.4));
      if (pc) {
        const A = L.pcArea;
        const sc = Math.min(A.w / rec.pcW, A.h / 720);
        const x = A.x + (A.w - rec.pcW * sc) / 2;
        const y = A.y + (A.h - 720 * sc) / 2;
        pc.style.transform = `translate(${(x - 160 * (1 - k)).toFixed(1)}px, ${y.toFixed(1)}px) scale(${sc.toFixed(4)})`;
        pc.style.opacity = String(k);
      }
    } else {
      const box = item.layout === "photoCard" ? L.photo : L.card;
      const e = k;
      el.style.left = `${box.x}px`;
      el.style.top = `${box.y}px`;
      el.style.width = `${box.w}px`;
      el.style.height = `${box.h}px`;
      el.style.right = el.style.bottom = "auto";
      el.style.opacity = String(clamp(e * 1.6));
      const fromX = L.W > L.H ? -140 : 0;
      const fromY = L.W > L.H ? 0 : 160;
      el.style.transform = `translate(${(fromX * (1 - e)).toFixed(1)}px, ${(fromY * (1 - e)).toFixed(1)}px) rotate(${((1 - e) * -5 + (item.layout === "photoCard" ? -2 : 0)).toFixed(2)}deg) scale(${(0.92 + 0.08 * e).toFixed(3)})`;
      if (pc) {
        const sc = Math.min(box.w / rec.pcW, box.h / 720);
        pc.style.transform = `translate(${((box.w - rec.pcW * sc) / 2).toFixed(1)}px, ${((box.h - 720 * sc) / 2).toFixed(1)}px) scale(${sc.toFixed(4)})`;
      }
    }
  }

  /**
   * Câmera virtual: retângulo (tela cheia ↔ janela), zoom e enquadramento (original ↔ rosto no centro).
   * cam = { z, c, sx, sy, face: {cx, cy, w} } (rosto normalizado na imagem original)
   */
  function placeCamera(cam, kWin, kSide) {
    const full = { x: 0, y: 0, w: L.W, h: L.H };
    const r = {
      x: lerp(full.x, L.win.x, kWin),
      y: lerp(full.y, L.win.y, kWin),
      w: lerp(full.w, L.win.w, kWin),
      h: lerp(full.h, L.win.h, kWin),
    };
    camWrap.style.left = `${r.x.toFixed(2)}px`;
    camWrap.style.top = `${r.y.toFixed(2)}px`;
    camWrap.style.width = `${r.w.toFixed(2)}px`;
    camWrap.style.height = `${r.h.toFixed(2)}px`;
    camWrap.style.zIndex = kWin > 0.001 ? "12" : "1";
    camWrap.classList.toggle("framed", kWin > 0.001);
    camWrap.style.setProperty("--k", kWin.toFixed(3));

    const s0 = Math.max(r.w / SRC.w, r.h / SRC.h);
    const face = cam.face || { cx: 0.5, cy: 0.42, w: 0.17 };
    // na janela, o zoom garante o rosto bem enquadrado; com card ao lado, zoom mínimo para deslocar o rosto
    const zWin = clamp((L.faceInWin * r.w) / (face.w * SRC.w * s0), 1, 2.4);
    let z = lerp(cam.z, Math.max(cam.z, zWin), kWin);
    z = lerp(z, Math.max(z, L.side.z), kSide * (1 - kWin));
    const imgW = SRC.w * s0 * z;
    const imgH = SRC.h * s0 * z;
    const tx = lerp(L.face.x, L.side.x, kSide * (1 - kWin));
    const ty = lerp(L.face.y, L.side.y, kSide * (1 - kWin));
    // c: 0 = enquadramento original (zoom pelo centro da imagem), 1 = rosto centralizado;
    // janela e card sempre enquadram o rosto
    const c = Math.max(cam.c ?? 1, kWin, kSide);
    const clampX = (v) => Math.min(0, Math.max(r.w - imgW, v));
    const clampY = (v) => Math.min(0, Math.max(r.h - imgH, v));
    let left = lerp((r.w - imgW) / 2, clampX(tx * r.w - face.cx * imgW), c) + (cam.sx || 0);
    let top = lerp((r.h - imgH) / 2, clampY(ty * r.h - face.cy * imgH), c) + (cam.sy || 0);
    left = clampX(left);
    top = clampY(top);
    camImg.style.width = `${imgW.toFixed(2)}px`;
    camImg.style.height = `${imgH.toFixed(2)}px`;
    camImg.style.transform = `translate(${left.toFixed(2)}px, ${top.toFixed(2)}px)`;
  }

  // ---------------------------------------------------------------- API
  function load(list, opts) {
    const format = (opts && opts.format) || "horizontal";
    L = LAYOUTS[format];
    document.body.className = `format-${format}`;
    items = list.slice().sort((a, b) => a.start - b.start || (a.z || 0) - (b.z || 0));
    for (const { el } of live.values()) el.remove();
    live.clear();
  }

  function setCam(src) {
    if (camImg.getAttribute("src") === src) return Promise.resolve();
    camImg.src = src;
    return camImg.decode().catch(() => {});
  }

  function render(t, cam) {
    const active = new Set();
    let kWin = 0;
    let kSide = 0;
    let shiftCaption = 0;
    for (const it of items) {
      if (t < it.start || t >= it.end) continue;
      active.add(it.id);
      let rec = live.get(it.id);
      if (!rec) {
        const el = h("div", `item type-${it.type}${it.layout ? ` layout-${it.layout}` : ""}`);
        el.style.zIndex = String(it.z || 0);
        let target = el;
        let pc = null;
        let pcW = 1280;
        // tela cheia no horizontal usa o quadro 1280 direto; no vertical, o conteúdo é reduzido para caber
        if (it.layout && it.type !== "photo" && (it.layout !== "full" || L.W < L.H)) {
          // quadro de conteúdo mais estreito nos cards/janelas: textos maiores
          const narrow = it.layout === "gfxCard" || it.layout === "full";
          pcW = narrow ? 900 : 1000;
          pc = h("div", `pc${narrow ? " narrow" : ""}`);
          pc.style.width = `${pcW}px`;
          pc.__wrap = el;
          el.appendChild(pc);
          target = pc;
        }
        CANVAS_W = pcW;
        const refs = TYPES[it.type].build(target, it.data);
        CANVAS_W = 1280;
        stage.appendChild(el);
        rec = { el, item: it, refs, pc, pcW };
        live.set(it.id, rec);
      }
      const lt = t - it.start;
      const dur = it.end - it.start;
      if (it.layout) {
        const k = envelope(lt, dur);
        if (it.layout === "camWindow") kWin = Math.max(kWin, k);
        else if (it.layout !== "full") kSide = Math.max(kSide, k);
        placeLayout(rec, k, lt, dur);
      }
      if (it.type === "caption" && it.data.side) shiftCaption = 1;
      TYPES[it.type].update(rec.refs, it.data, lt, dur, t, rec.el);
    }
    for (const [id, rec] of live) {
      if (!active.has(id)) {
        rec.el.remove();
        live.delete(id);
      }
    }
    stage.classList.toggle("side-active", kSide > 0.5 && shiftCaption === 1);
    if (cam) placeCamera(cam, kWin, kSide);
    return active.size;
  }

  window.STAGE = { load, render, setCam, types: Object.keys(TYPES) };
})();
