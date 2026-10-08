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
  function plateBase(el, mood) {
    el.classList.add("plate");
    if (mood) el.classList.add(mood);
    const s = h("div", "streaks");
    el.appendChild(s);
    const b = h("div", "baseline");
    el.appendChild(b);
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
  function fitFont(text, max, min, perChar) {
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

  // ---------------------------------------------------------------- API
  function load(list) {
    items = list.slice().sort((a, b) => a.start - b.start || (a.z || 0) - (b.z || 0));
    for (const { el } of live.values()) el.remove();
    live.clear();
  }

  function render(t) {
    const active = new Set();
    for (const it of items) {
      if (t < it.start || t >= it.end) continue;
      active.add(it.id);
      let rec = live.get(it.id);
      if (!rec) {
        const el = h("div", `item type-${it.type}`);
        el.style.zIndex = String(it.z || 0);
        const refs = TYPES[it.type].build(el, it.data);
        stage.appendChild(el);
        rec = { el, item: it, refs };
        live.set(it.id, rec);
      }
      const lt = t - it.start;
      const dur = it.end - it.start;
      TYPES[it.type].update(rec.refs, it.data, lt, dur, t, rec.el);
      // saída padrão das placas: corte seco (estilo das referências); demais tratam a própria saída
    }
    for (const [id, rec] of live) {
      if (!active.has(id)) {
        rec.el.remove();
        live.delete(id);
      }
    }
    return active.size;
  }

  window.STAGE = { load, render, types: Object.keys(TYPES) };
})();
