/* global window, document */
"use strict";

/**
 * Componentes do roteiro com MODOS (cards de jogador, campinho, placares da rodada, VAR,
 * aspas, enquete, vinheta, selos, números grandes). Cada um é desenhado numa caixa
 * (box.w x box.h) que pode ser a tela inteira (MG+VO), a área ao lado da câmera
 * pequena (CAM+MG) ou o palco todo por cima da câmera (sobreposição).
 *
 * Identidade visual: grafite #111418 com textura de grama, verde-limão #B6FF3B
 * (melhores), vermelho #FF3B3B (piores), amarelo #FFD23B (VAR / alerta).
 */
(function () {
  window.STAGE_PLUGINS = window.STAGE_PLUGINS || [];
  window.STAGE_PLUGINS.push(function (u) {
    const { h, prog, outCubic, outBack, clamp, inCubic } = u;
    const LIME = "#B6FF3B";
    const RED = "#FF3B3B";
    const file = (p) => (p ? window.STAGE_ASSETS.file(p) : "");

    /** cor da nota (escala SofaScore) */
    function noteColor(r) {
      if (r == null || Number.isNaN(r)) return "#5b6470";
      if (r >= 9) return "#2f6bff";
      if (r >= 8) return "#0b8f4d";
      if (r >= 7) return "#22c55e";
      if (r >= 6.5) return "#e8b100";
      if (r >= 6) return "#f2711c";
      return "#e5322d";
    }
    const fmt = (r) => (r == null ? "" : r >= 10 ? "10" : r.toFixed(1).replace(".", ","));
    const initials = (n) =>
      String(n || "?")
        .split(/\s+/)
        .map((w) => w[0])
        .join("")
        .slice(0, 2)
        .toUpperCase();

    /** fundo das placas (grafite + grama) */
    function bg(el, mood) {
      const wrap = el.__wrap || el;
      wrap.classList.add("plate2");
      if (mood) wrap.classList.add(mood);
    }
    function kicker(el, text, mood) {
      if (!text) return null;
      const k = h("div", `kicker anton${mood === "worst" ? " red" : ""}`, text);
      el.appendChild(k);
      return k;
    }
    function face(c, size, round) {
      const d = h("div", `face${round ? " round" : ""}`);
      d.style.width = d.style.height = `${size}px`;
      if (c.photo) {
        const i = h("img");
        i.src = file(c.photo);
        d.appendChild(i);
      } else {
        const s = h("div", "ini anton", initials(c.name));
        s.style.fontSize = `${Math.round(size * 0.38)}px`;
        d.appendChild(s);
      }
      return d;
    }
    function crest(c, size) {
      const d = h("div", "crest");
      d.style.width = d.style.height = `${size}px`;
      if (c.crest) {
        const i = h("img");
        i.src = file(c.crest);
        d.appendChild(i);
      } else if (c.sigla) {
        const s = h("div", "sig anton", c.sigla);
        s.style.fontSize = `${Math.round(size * 0.34)}px`;
        d.appendChild(s);
      } else d.style.display = "none";
      return d;
    }
    function badge(r, size) {
      const b = h("div", "badge anton", fmt(r));
      b.style.background = noteColor(r);
      b.style.fontSize = `${Math.round(size * 0.5)}px`;
      b.style.minWidth = `${size * 1.25}px`;
      b.style.height = `${size}px`;
      b.style.lineHeight = `${size}px`;
      return b;
    }
    /** entrada com quique, a partir de `at` (s) */
    const pop = (lt, at, d = 0.42) => outBack(prog(lt, at, d), 1.9);
    const fade = (lt, at, d = 0.15) => clamp(prog(lt, at, d));

    const T = {};

    // ---------------------------------------------------------------- cards de jogador
    T.cards = {
      fit: true,
      build(el, d, box) {
        bg(el, d.mood);
        const r = { cards: [], box };
        r.k = kicker(el, d.kicker, d.mood);
        const n = d.cards.length;
        const portrait = box.h > box.w * 1.1;
        const perRow = portrait ? (n <= 2 ? n : Math.ceil(n / 2)) : Math.min(n, n > 4 ? Math.ceil(n / 2) : n);
        const rows = Math.ceil(n / perRow);
        const extra = d.stat && n === 1 ? 1 : 0;
        const gap = 26;
        const maxW = (box.w - 70 - (perRow + extra - 1) * gap) / (perRow + extra);
        const maxH = (box.h - 120 - (d.notes && d.notes.length ? 70 : 0) - (rows - 1) * gap) / rows / 1.42;
        const cw = Math.max(120, Math.min(portrait ? 460 : 300, maxW, maxH)); // no 9:16 o card ocupa a tela
        const ch = cw * 1.42;
        const totalW = (perRow + extra) * cw + (perRow + extra - 1) * gap;
        const totalH = rows * ch + (rows - 1) * gap;
        const x0 = (box.w - totalW) / 2;
        const y0 = Math.max(70, (box.h - totalH - (d.notes && d.notes.length ? 70 : 0)) / 2 + 20);
        d.cards.forEach((c, i) => {
          const row = Math.floor(i / perRow);
          const inRow = Math.min(perRow, n - row * perRow);
          const rx = x0 + ((perRow - inRow) * (cw + gap)) / 2;
          const e = h("div", `pcard${c.red ? " red" : ""}${c.rating != null && c.rating < 6.5 ? " low" : ""}`);
          e.style.left = `${rx + (i % perRow) * (cw + gap)}px`;
          e.style.top = `${y0 + row * (ch + gap)}px`;
          e.style.width = `${cw}px`;
          e.style.height = `${ch}px`;
          const ph = h("div", "ph");
          if (c.color) ph.style.background = `linear-gradient(180deg, ${c.color}cc, #0c0f13 92%)`;
          ph.appendChild(face(c, cw * 0.86, false));
          e.appendChild(ph);
          const cr = crest(c, cw * 0.26);
          cr.classList.add("tl");
          e.appendChild(cr);
          const nm = h("div", "nm anton", String(c.name).toUpperCase());
          nm.style.fontSize = `${Math.max(16, Math.min(cw * 0.15, (cw * 1.55) / Math.max(4, String(c.name).length)))}px`;
          e.appendChild(nm);
          const tm = h("div", "tm", c.team || "");
          tm.style.fontSize = `${Math.max(11, cw * 0.065)}px`;
          e.appendChild(tm);
          let b = null;
          if (c.rating != null) {
            b = badge(c.rating, cw * 0.24);
            b.classList.add("br");
            e.appendChild(b);
          }
          if (c.tags) {
            const tg = h("div", "tags", c.tags);
            tg.style.fontSize = `${cw * 0.1}px`;
            e.appendChild(tg);
          }
          let rc = null;
          if (c.red) {
            rc = h("div", "minired");
            rc.style.width = `${cw * 0.2}px`;
            rc.style.height = `${cw * 0.28}px`;
            e.appendChild(rc);
          }
          let cap = null;
          if (c.captain) {
            cap = h("div", "capt anton", "C");
            e.appendChild(cap);
          }
          el.appendChild(e);
          r.cards.push({ e, b, rc, c });
        });
        if (extra) {
          const s = h("div", "statbox");
          s.style.left = `${x0 + cw + gap}px`;
          s.style.top = `${y0}px`;
          s.style.width = `${cw}px`;
          s.style.height = `${ch}px`;
          r.statNum = h("div", "sn anton", "0");
          r.statNum.style.fontSize = `${cw * 0.6}px`;
          const sl = h("div", "sl anton", d.stat.label);
          sl.style.fontSize = `${cw * 0.13}px`;
          s.append(r.statNum, sl);
          el.appendChild(s);
          r.stat = s;
        }
        r.notes = (d.notes || []).slice(0, 2).map((t, i) => {
          const p = h("div", "note-pill anton", t);
          p.style.top = `${Math.min(box.h - 66, y0 + totalH + 24)}px`;
          el.appendChild(p);
          return p;
        });
        if (d.link) {
          r.link = h("div", "link-pill anton", d.link);
          r.link.style.top = `${y0 + totalH / 2 - 26}px`;
          el.appendChild(r.link);
        }
        return r;
      },
      update(r, d, lt, dur) {
        if (r.k) r.k.style.opacity = String(fade(lt, 0, 0.25));
        let last = 0;
        r.cards.forEach((x, i) => {
          const at = x.c.at != null ? x.c.at : 0.25 + i * 0.35;
          last = Math.max(last, at);
          const p = pop(lt, at);
          x.e.style.opacity = String(fade(lt, at, 0.12));
          x.e.style.transform = `translateY(${(140 * (1 - p)).toFixed(1)}px) scale(${(0.8 + 0.2 * p).toFixed(3)})`;
          if (x.b) {
            const q = outCubic(prog(lt, at + 0.25, 0.6));
            const v = x.c.rating * q;
            x.b.textContent = q >= 1 ? fmt(x.c.rating) : x.c.rating >= 10 ? String(Math.round(v)) : v.toFixed(1).replace(".", ",");
            x.b.style.transform = `scale(${(0.6 + 0.4 * outBack(prog(lt, at + 0.2, 0.3), 2.4)).toFixed(3)})`;
          }
          if (x.rc) {
            const q = outBack(prog(lt, at + 0.55, 0.3), 2.6);
            x.rc.style.opacity = String(fade(lt, at + 0.55, 0.08));
            x.rc.style.transform = `rotate(14deg) scale(${(2.4 - 1.4 * q).toFixed(3)})`;
            x.e.classList.toggle("glitch", lt > at + 0.05 && lt < at + 0.35 && Math.floor(lt * 30) % 2 === 0);
          }
        });
        if (r.stat) {
          const q = outCubic(prog(lt, 0.6, Math.min(2.4, dur * 0.5)));
          r.statNum.textContent = String(Math.round(d.stat.from + (d.stat.to - d.stat.from) * q));
          r.stat.style.opacity = String(fade(lt, 0.45, 0.2));
        }
        r.notes.forEach((p, i) => {
          const at = last + 0.7 + i * 0.35;
          const q = outBack(prog(lt, at, 0.35), 2);
          p.style.opacity = String(fade(lt, at, 0.1));
          p.style.transform = `translateX(-50%) translateX(${(i - (r.notes.length - 1) / 2) * 0}px) scale(${(0.6 + 0.4 * q).toFixed(3)})`;
          if (r.notes.length > 1) p.style.marginLeft = `${(i - 0.5) * 380}px`;
        });
        if (r.link) {
          const q = outBack(prog(lt, last + 0.6, 0.35), 2);
          r.link.style.opacity = String(fade(lt, last + 0.6, 0.1));
          r.link.style.transform = `translateX(-50%) scale(${(0.5 + 0.5 * q).toFixed(3)})`;
        }
      },
    };

    // ---------------------------------------------------------------- campinho
    T.pitch = {
      fit: true,
      build(el, d, box) {
        bg(el, d.worst ? "worst" : "");
        const r = { players: [] };
        r.title = h("div", `pitch-title anton${d.worst ? " red" : ""}`, d.title || "");
        r.title.style.fontSize = `${Math.min(64, box.w / 14)}px`;
        el.appendChild(r.title);
        const portrait = box.h > box.w;
        const benchW = d.bench && d.bench.length ? (portrait ? 0 : box.w * 0.16) : 0;
        // campo inclinado (perspectiva) — mesmas contas no CSS e na projeção dos jogadores
        const P = 1600;
        const TH = (25 * Math.PI) / 180;
        const availW = box.w - benchW - 40;
        const availH = box.h - 116 - (portrait && d.bench && d.bench.length ? 130 : 10);
        const rows = d.rows || [];
        const R = rows.length;
        const V0 = 0.1;
        const V1 = 0.88;
        const projY = (v, fh) => {
          const zz = (0.5 - v) * fh * Math.sin(TH);
          return (v - 0.5) * fh * Math.cos(TH) * (P / (P + zz));
        };
        const vOf = (ri) => (R === 1 ? 0.5 : V0 + (ri / (R - 1)) * (V1 - V0));
        const maxRow = Math.max(4, ...rows.map((x) => x.length));
        // o maior campo em que as linhas de jogadores cabem (o gramado pode passar da borda de baixo)
        let FW = availW * (portrait ? 0.98 : 0.94);
        let FH = portrait ? FW * 1.45 : FW * 0.95;
        let size = 50;
        for (let k = 0; k < 80; k++) {
          const ys = rows.map((_, i) => projY(vOf(i), FH));
          const gap = R > 1 ? Math.min(...ys.slice(1).map((y, i) => y - ys[i])) : 200;
          size = Math.max(40, Math.min(110, gap / 1.75, FW / (maxRow * 1.6)));
          const top = Math.min(projY(0, FH), (ys[0] ?? 0) - size * 0.6);
          const bot = (ys[ys.length - 1] ?? 0) + size * 1.15;
          if (bot - top <= availH) break;
          FW *= 0.96;
          FH *= 0.96;
        }
        const cx = 20 + availW / 2;
        const ys0 = rows.map((_, i) => projY(vOf(i), FH));
        const top0 = Math.min(projY(0, FH), (ys0[0] ?? 0) - size * 0.6);
        const bot0 = (ys0[ys0.length - 1] ?? 0) + size * 1.15;
        const cy = 108 + availH / 2 - (top0 + bot0) / 2;
        const field = h("div", `field${d.worst ? " worst" : ""}`);
        field.style.width = `${FW}px`;
        field.style.height = `${FH}px`;
        field.style.left = `${cx - FW / 2}px`;
        field.style.top = `${cy - FH / 2}px`;
        field.style.transform = `perspective(${P}px) rotateX(${(TH * 180) / Math.PI}deg)`;
        field.innerHTML = '<i class="ln half"></i><i class="ln circ"></i><i class="ln box top"></i><i class="ln box bot"></i><i class="ln sbox top"></i><i class="ln sbox bot"></i>';
        el.appendChild(field);
        r.field = field;
        const project = (u, v) => {
          const zz = (0.5 - v) * FH * Math.sin(TH);
          const sc = P / (P + zz);
          return { x: cx + (u - 0.5) * FW * sc, y: cy + projY(v, FH), s: sc };
        };
        rows.forEach((row, ri) => {
          const v = vOf(ri);
          row.forEach((c, ci) => {
            const u = (ci + 1) / (row.length + 1);
            const p = project(u, v);
            const m = minicard(c, size * p.s, d.worst);
            m.style.left = `${p.x}px`;
            m.style.top = `${p.y}px`;
            m.style.zIndex = String(10 + ri);
            el.appendChild(m);
            r.players.push({ m, c, order: (R - 1 - ri) * 10 + ci });
          });
        });
        if (d.bench && d.bench.length) {
          const b = h("div", "bench");
          if (portrait) {
            b.style.left = `${box.w / 2 - 160}px`;
            b.style.top = `${box.h - 175}px`;
            b.style.width = "320px";
          } else {
            b.style.left = `${box.w - benchW - 10}px`;
            b.style.top = `${cy - 120}px`;
            b.style.width = `${benchW}px`;
          }
          b.appendChild(h("div", "bench-t anton", "BANCO"));
          el.appendChild(b);
          d.bench.forEach((c) => {
            const m = minicard(c, size * 0.9, d.worst);
            m.style.position = "relative";
            m.style.left = m.style.top = "auto";
            m.style.margin = "8px auto 0";
            b.appendChild(m);
            r.players.push({ m, c, order: 999, bench: true });
          });
          r.bench = b;
        }
        return r;
      },
      update(r, d, lt, dur) {
        const e = outCubic(prog(lt, 0, 0.5));
        r.field.style.opacity = String(e);
        r.field.style.marginTop = `${(-120 * (1 - e)).toFixed(1)}px`;
        const tq = outBack(prog(lt, 0.15, 0.4), 1.8);
        r.title.style.opacity = String(fade(lt, 0.15, 0.15));
        r.title.style.transform = `translateX(-50%) scale(${(0.7 + 0.3 * tq).toFixed(3)})`;
        // quem não tem tempo na fala entra em ordem: goleiro → defesa → meio → ataque
        const timed = r.players.filter((x) => x.c.at == null).sort((a, b) => a.order - b.order);
        timed.forEach((x, i) => (x.auto = 0.7 + i * Math.min(0.45, (dur * 0.6) / Math.max(1, timed.length))));
        for (const x of r.players) {
          const at = x.c.at != null ? x.c.at : x.auto;
          const q = outBack(prog(lt, at, 0.45), 1.6);
          x.m.style.opacity = String(fade(lt, at, 0.1));
          if (d.worst) x.m.style.transform = `translate(-50%, -50%) translateY(${(-160 * (1 - q)).toFixed(1)}px) rotate(${(180 * (1 - outCubic(prog(lt, at, 0.35)))).toFixed(1)}deg)`;
          else x.m.style.transform = `translate(-50%, -50%) translateY(${(-120 * (1 - q)).toFixed(1)}px) scale(${(0.6 + 0.4 * q).toFixed(3)})`;
          if (x.bench) x.m.style.transform = x.m.style.transform.replace("translate(-50%, -50%) ", "");
          const ring = x.m.querySelector(".fire");
          if (ring) ring.style.opacity = String(0.55 + 0.45 * Math.sin(lt * 9 + x.order));
        }
        if (r.bench) r.bench.style.opacity = String(fade(lt, 0.5, 0.3));
        // fim: o campo brilha
        r.field.classList.toggle("glow", !d.worst && lt > dur - 1.2);
      },
    };
    function minicard(c, size, worst) {
      const m = h("div", `mini${c.red ? " red" : ""}`);
      const f = face(c, size, true);
      if (c.rating >= 10 && !worst) f.appendChild(h("i", "fire"));
      m.appendChild(f);
      const cr = crest(c, size * 0.36);
      cr.classList.add("mc");
      m.appendChild(cr);
      if (c.rating != null) {
        const b = badge(c.rating, size * 0.32);
        b.classList.add("mb");
        m.appendChild(b);
      }
      const nm = h("div", "mn anton", String(c.name).toUpperCase());
      nm.style.fontSize = `${Math.max(12, size * 0.2)}px`;
      m.appendChild(nm);
      if (c.captain) m.appendChild(h("div", "capt anton", "C"));
      if (c.red) {
        const rc = h("div", "minired");
        rc.style.width = `${size * 0.2}px`;
        rc.style.height = `${size * 0.28}px`;
        m.appendChild(rc);
      }
      return m;
    }

    // ---------------------------------------------------------------- placares da rodada
    T.scoregrid = {
      fit: true,
      build(el, d, box) {
        bg(el);
        const r = { rows: [] };
        r.title = h("div", "pitch-title anton", d.title || "");
        r.title.style.fontSize = `${Math.min(54, box.w / 16)}px`;
        el.appendChild(r.title);
        const groups = d.groups || [];
        const portrait = box.h > box.w;
        const cols = portrait ? 1 : Math.min(2, groups.length);
        const total = groups.reduce((n, g) => n + g.games.length + (g.label ? 1 : 0), 0);
        const colW = (box.w - 60 - (cols - 1) * 30) / cols;
        const maxRows = portrait ? total : Math.max(...groups.map((g) => g.games.length + (g.label ? 1 : 0)));
        const rowH = Math.min(96, (box.h - 130) / maxRows);
        groups.forEach((g, gi) => {
          const col = portrait ? 0 : gi % cols;
          let y = 100 + (portrait ? groups.slice(0, gi).reduce((n, x) => n + x.games.length + (x.label ? 1 : 0), 0) * rowH : 0);
          const x = 30 + col * (colW + 30);
          if (g.label) {
            const l = h("div", "grp anton", g.label);
            l.style.left = `${x}px`;
            l.style.top = `${y}px`;
            l.style.width = `${colW}px`;
            l.style.fontSize = `${rowH * 0.4}px`;
            el.appendChild(l);
            r.rows.push({ e: l, at: g.games[0] ? g.games[0].at : null, label: true });
            y += rowH;
          }
          g.games.forEach((m) => {
            const e = h("div", "game");
            e.style.left = `${x}px`;
            e.style.top = `${y}px`;
            e.style.width = `${colW}px`;
            e.style.height = `${rowH - 10}px`;
            const cs = rowH * 0.62;
            const na = String(m.a || m.siglaA).toUpperCase();
            const nb = String(m.b || m.siglaB).toUpperCase();
            const ta = h("div", "gt a anton", na);
            const tb = h("div", "gt b anton", nb);
            ta.style.fontSize = tb.style.fontSize = `${Math.min(rowH * 0.42, (colW * 0.29) / (Math.max(na.length, nb.length) * 0.62))}px`;
            const sc = h("div", "gs anton", `${m.sa}  x  ${m.sb}`);
            sc.style.fontSize = `${rowH * 0.5}px`;
            e.append(crest({ crest: m.crestA, sigla: m.siglaA }, cs), ta, sc, tb, crest({ crest: m.crestB, sigla: m.siglaB }, cs));
            el.appendChild(e);
            r.rows.push({ e, at: m.at });
            y += rowH;
          });
        });
        return r;
      },
      update(r, d, lt, dur) {
        r.title.style.opacity = String(fade(lt, 0, 0.2));
        r.title.style.transform = "translateX(-50%)";
        const n = r.rows.length;
        r.rows.forEach((x, i) => {
          const at = x.at != null ? (x.label ? Math.max(0, x.at - 0.25) : x.at) : 0.3 + i * Math.min(0.9, (dur - 1) / n);
          const q = outCubic(prog(lt, at, 0.3));
          x.e.style.opacity = String(q);
          // "card flip": a placa vira ao cair
          const hl = !x.label && lt >= at && lt < at + 1.0 ? 1.05 : 1;
          x.e.style.transform = `perspective(700px) rotateX(${(90 * (1 - q)).toFixed(1)}deg) scale(${hl})`;
          x.e.classList.toggle("hot", !x.label && lt >= at && lt < at + 1.0);
        });
      },
    };

    // ---------------------------------------------------------------- placar que muda (0x2 → 1x2 → 2x2)
    T.scoreseq = {
      fit: true,
      build(el, d, box) {
        bg(el);
        const r = {};
        const s = Math.min(box.w / 5.5, box.h / 3.2);
        const w = h("div", "seq");
        w.style.top = `${box.h * 0.22}px`;
        r.a = crest({ crest: d.crestA, sigla: d.siglaA }, s);
        r.b = crest({ crest: d.crestB, sigla: d.siglaB }, s);
        r.num = h("div", "seq-num anton", "");
        r.num.style.fontSize = `${s * 0.95}px`;
        w.append(r.a, r.num, r.b);
        el.appendChild(w);
        const names = h("div", "seq-names anton", `${d.a}  ×  ${d.b}`);
        names.style.top = `${box.h * 0.22 + s + 30}px`;
        names.style.fontSize = `${s * 0.25}px`;
        el.appendChild(names);
        r.names = names;
        return r;
      },
      update(r, d, lt, dur) {
        const steps = d.steps || [];
        const times = d.times || steps.map((_, i) => 0.3 + (i * Math.max(1, dur * 0.7)) / Math.max(1, steps.length));
        let k = 0;
        times.forEach((t, i) => {
          if (lt >= t) k = i;
        });
        const st = steps[k] || [0, 0];
        r.num.textContent = `${st[0]} x ${st[1]}`;
        const since = lt - (times[k] || 0);
        r.num.style.transform = `scale(${(1 + 0.25 * Math.exp(-since * 7)).toFixed(3)})`;
        const e = outCubic(prog(lt, 0, 0.35));
        r.a.style.transform = `translateX(${(-300 * (1 - e)).toFixed(1)}px)`;
        r.b.style.transform = `translateX(${(300 * (1 - e)).toFixed(1)}px)`;
        r.names.style.opacity = String(fade(lt, 0.3, 0.3));
      },
    };

    // ---------------------------------------------------------------- duelo de pontos
    T.duel = {
      fit: true,
      build(el, d, box) {
        bg(el);
        const r = {};
        const s = Math.min(box.w / 6, box.h / 3.6);
        const mk = (t, side) => {
          const c = h("div", `duel-side ${side}`);
          c.style.width = `${s * 1.6}px`;
          c.appendChild(crest({ crest: t.crest, sigla: t.sigla }, s));
          const barBox = h("div", "duel-bar");
          barBox.style.height = `${box.h * 0.32}px`;
          const fill = h("i");
          barBox.appendChild(fill);
          const v = h("div", "duel-v anton", "0");
          v.style.fontSize = `${s * 0.55}px`;
          c.append(barBox, v);
          return { c, fill, v };
        };
        r.A = mk(d.a, "l");
        r.B = mk(d.b, "r");
        r.A.c.style.left = `${box.w * 0.18}px`;
        r.B.c.style.right = `${box.w * 0.18}px`;
        el.append(r.A.c, r.B.c);
        r.bolt = h("div", "bolt");
        r.bolt.innerHTML = '<svg viewBox="0 0 200 60" preserveAspectRatio="none"><polyline points="0,30 40,10 70,45 110,8 140,46 170,15 200,30" fill="none" stroke="#FFD23B" stroke-width="6" stroke-linejoin="round"/></svg>';
        r.bolt.style.top = `${box.h * 0.2}px`;
        el.appendChild(r.bolt);
        r.label = h("div", "duel-label anton", d.label || "");
        r.label.style.top = `${box.h * 0.48}px`;
        r.label.style.fontSize = `${Math.min(90, box.w / 11)}px`;
        el.appendChild(r.label);
        return r;
      },
      update(r, d, lt) {
        const max = Math.max(d.a.pts, d.b.pts) || 1;
        for (const [S, t, delay] of [[r.A, d.a, 0.2], [r.B, d.b, 0.35]]) {
          const q = outCubic(prog(lt, delay, 1.1));
          S.fill.style.height = `${((t.pts / max) * 100 * q).toFixed(1)}%`;
          S.v.textContent = String(Math.round(t.pts * q));
          S.c.style.opacity = String(fade(lt, 0, 0.25));
        }
        r.bolt.style.opacity = String(lt > 1.3 ? 0.6 + 0.4 * Math.abs(Math.sin(lt * 23)) : 0);
        const lq = outBack(prog(lt, 1.4, 0.35), 2.2);
        r.label.style.opacity = String(fade(lt, 1.4, 0.1) * (0.75 + 0.25 * Math.abs(Math.sin(lt * 6))));
        r.label.style.transform = `translateX(-50%) scale(${(0.4 + 0.6 * lq).toFixed(3)})`;
      },
    };

    // ---------------------------------------------------------------- tela de VAR
    T.var = {
      fit: true,
      build(el, d, box) {
        bg(el, "var");
        const r = {};
        const w = Math.min(box.w * 0.78, box.h * 1.25);
        const m = h("div", "var-mon");
        m.style.width = `${w}px`;
        m.style.height = `${w * 0.58}px`;
        m.style.left = `${(box.w - w) / 2}px`;
        m.style.top = `${(box.h - w * 0.58) / 2}px`;
        r.big = h("div", "var-big anton", "VAR");
        r.big.style.fontSize = `${w * 0.26}px`;
        r.sub = h("div", "var-sub anton", d.label || "CHECKING...");
        r.sub.style.fontSize = `${w * 0.06}px`;
        m.append(h("i", "scan"), r.big, r.sub);
        el.appendChild(m);
        r.m = m;
        return r;
      },
      update(r, d, lt) {
        const q = outBack(prog(lt, 0, 0.3), 1.6);
        r.m.style.transform = `scale(${(0.7 + 0.3 * q).toFixed(3)})`;
        r.m.style.opacity = String(fade(lt, 0, 0.08));
        r.big.style.opacity = String(Math.floor(lt * 3.2) % 2 === 0 ? 1 : 0.35);
        const dots = ".".repeat(1 + (Math.floor(lt * 4) % 3));
        if (/CHECKING/.test(d.label || "")) r.sub.textContent = `CHECKING${dots}`;
        r.m.style.filter = Math.floor(lt * 30) % 13 === 5 ? "contrast(1.5) brightness(1.25)" : "none";
      },
    };

    // ---------------------------------------------------------------- aspas
    T.quote = {
      fit: true,
      build(el, d, box) {
        bg(el);
        const r = {};
        r.mark = h("div", "q-mark anton", "“");
        r.mark.style.fontSize = `${box.h * 0.45}px`;
        el.appendChild(r.mark);
        r.txt = h("div", "q-txt anton");
        const len = String(d.text).length;
        r.txt.style.fontSize = `${Math.max(34, Math.min(80, (box.w * 2.2) / Math.sqrt(len * 6)))}px`;
        r.words = String(d.text)
          .split(/\s+/)
          .map((w) => {
            const s = h("span", "", `${w} `);
            r.txt.appendChild(s);
            return s;
          });
        el.appendChild(r.txt);
        r.au = h("div", "q-au anton", d.author ? `— ${d.author}` : "");
        el.appendChild(r.au);
        return r;
      },
      update(r, d, lt, dur) {
        r.mark.style.opacity = String(fade(lt, 0, 0.2) * 0.9);
        r.mark.style.transform = `scale(${(0.6 + 0.4 * outBack(prog(lt, 0, 0.4), 2)).toFixed(3)})`;
        const step = Math.min(0.12, (dur * 0.5) / Math.max(1, r.words.length));
        r.words.forEach((s, i) => {
          const q = outCubic(prog(lt, 0.25 + i * step, 0.2));
          s.style.opacity = String(q);
        });
        r.au.style.opacity = String(fade(lt, 0.3 + r.words.length * step, 0.3));
      },
    };

    // ---------------------------------------------------------------- enquete (sobre a câmera)
    T.poll = {
      fit: true,
      overlay: true,
      build(el, d, box) {
        const r = {};
        const portrait = box.h > box.w;
        const p = h("div", "poll");
        p.style.width = `${portrait ? box.w - 80 : 440}px`;
        if (portrait) {
          p.style.left = "40px";
          p.style.top = "90px";
        } else {
          p.style.left = "36px";
          p.style.top = "60px";
        }
        r.q = h("div", "poll-q anton", d.question || "");
        p.appendChild(r.q);
        const yesno = d.options.length === 2 && /^SIM$/i.test(d.options[0]);
        r.opts = d.options.map((o, i) => {
          const e = h("div", `poll-o${yesno ? (i === 0 ? " yes" : " no") : ""}`);
          const n = h("div", "pn anton", yesno ? (i === 0 ? "✓" : "✕") : String(i + 1));
          e.append(n, h("div", "pt anton", o), h("i", "bar"));
          p.appendChild(e);
          return e;
        });
        r.c = h("div", "poll-c anton", "COMENTA!");
        p.appendChild(r.c);
        el.appendChild(p);
        r.p = p;
        return r;
      },
      update(r, d, lt, dur) {
        const q = outBack(prog(lt, 0, 0.35), 1.8);
        const x = inCubic(prog(lt, dur - 0.3, 0.3));
        r.p.style.opacity = String(fade(lt, 0, 0.1) * (1 - x));
        r.p.style.transform = `translateX(${(-80 * (1 - q)).toFixed(1)}px) scale(${(0.85 + 0.15 * q).toFixed(3)})`;
        r.opts.forEach((o, i) => {
          const e = outCubic(prog(lt, 0.3 + i * 0.25, 0.3));
          o.style.opacity = String(e);
          o.querySelector(".bar").style.transform = `scaleX(${outCubic(prog(lt, 0.5 + i * 0.25, 0.9)).toFixed(3)})`;
        });
        r.c.style.transform = `scale(${(1 + 0.06 * Math.sin(lt * 7)).toFixed(3)})`;
        r.c.style.opacity = String(fade(lt, 0.9, 0.2));
      },
    };

    // ---------------------------------------------------------------- vinheta de bloco
    T.vinheta = {
      fit: true,
      build(el, d, box) {
        bg(el);
        const r = {};
        r.bar = h("div", "vin-bar");
        el.appendChild(r.bar);
        r.t = h("div", "vin-t anton", d.title || "");
        r.t.style.fontSize = `${Math.min(box.h * 0.3, (box.w * 1.5) / Math.max(4, String(d.title).length))}px`;
        el.appendChild(r.t);
        return r;
      },
      update(r, d, lt) {
        const b = outCubic(prog(lt, 0, 0.35));
        r.bar.style.transform = `translateY(-50%) skewX(-12deg) scaleX(${b.toFixed(3)})`;
        const q = outBack(prog(lt, 0.12, 0.4), 2.2);
        r.t.style.opacity = String(fade(lt, 0.12, 0.1));
        r.t.style.transform = `translate(-50%, -50%) scale(${(1.8 - 0.8 * q).toFixed(3)})`;
      },
    };

    // ---------------------------------------------------------------- selos / carimbos
    T.stamps = {
      fit: true,
      build(el, d, box) {
        if (!d.overlay) bg(el);
        const r = { items: [] };
        const n = d.items.length;
        const portrait = box.h > box.w;
        d.items.forEach((it, i) => {
          const s = h("div", `stamp ${it.kind} anton`, it.text);
          s.style.fontSize = `${Math.min(70, (box.w * (portrait ? 1.2 : 0.9)) / Math.max(8, it.text.length) / (portrait ? 1 : Math.max(1, n * 0.6)))}px`;
          if (portrait || n === 1) {
            s.style.left = "50%";
            s.style.top = `${(box.h * (i + 1)) / (n + 1)}px`;
          } else {
            s.style.left = `${(box.w * (i + 1)) / (n + 1)}px`;
            s.style.top = `${box.h * 0.5 + (i % 2 ? 60 : -60)}px`;
          }
          el.appendChild(s);
          r.items.push({ s, it });
        });
        return r;
      },
      update(r, d, lt, dur) {
        r.items.forEach((x, i) => {
          const at = x.it.at != null ? x.it.at : 0.2 + i * Math.min(1.2, (dur - 0.6) / r.items.length);
          const q = outCubic(prog(lt, at, 0.18));
          x.s.style.opacity = String(q);
          x.s.style.transform = `translate(-50%, -50%) rotate(${i % 2 ? 6 : -6}deg) scale(${(2.2 - 1.2 * q).toFixed(3)})`;
        });
      },
    };

    // ---------------------------------------------------------------- números grandes caindo
    T.bignum = {
      fit: true,
      build(el, d, box) {
        if (!d.overlay) bg(el);
        const r = { nums: [] };
        const n = d.count || 1;
        const size = Math.min(box.h * (d.overlay ? 0.3 : 0.42), (box.w * 0.85) / (n * 1.1));
        for (let i = 0; i < n; i++) {
          const e = h("div", `bnum anton${d.color ? ` ${d.color}` : ""}${d.fire ? " fire" : ""}`, d.text);
          e.style.fontSize = `${size}px`;
          // sobre a câmera: "batem no chão" nos lados e embaixo, longe do rosto
          const xs = n === 3 ? [0.16, 0.5, 0.84] : n === 2 ? [0.18, 0.82] : null;
          e.style.left = `${box.w * (d.overlay && xs ? xs[i] : (i + 1) / (n + 1))}px`;
          e.style.top = `${d.overlay ? Math.min(box.h - size * (xs && i === 1 ? 0.5 : 0.72), box.h * 0.8) : box.h * 0.5}px`;
          el.appendChild(e);
          r.nums.push(e);
        }
        return r;
      },
      update(r, d, lt, dur) {
        r.nums.forEach((e, i) => {
          const at = d.times && d.times[i] != null ? d.times[i] : 0.15 + i * 0.4;
          const p = prog(lt, at, 0.32);
          const fall = p < 1 ? -900 * (1 - p * p) : 0;
          const squash = lt > at + 0.32 && lt < at + 0.45 ? 0.85 : 1;
          const x = d.overlay ? inCubic(prog(lt, dur - 0.3, 0.3)) : 0;
          e.style.opacity = String((lt >= at ? 1 : 0) * (1 - x));
          e.style.transform = `translate(-50%, -50%) translateY(${fall.toFixed(1)}px) scaleY(${squash}) rotate(${d.spin ? (lt * 40).toFixed(1) : 0}deg)`;
        });
      },
    };

    // ---------------------------------------------------------------- fotos da internet (camisas, VISUAL)
    T.fotos = {
      fit: true,
      build(el, d, box) {
        bg(el, "vitrine");
        const r = { items: [], seq: !!d.seq };
        const portrait = box.h > box.w * 1.1;
        const labelH = 64;
        const fichaW = d.ficha && !d.seq && d.items.length === 1 ? (portrait ? 0 : box.w * 0.34) : 0;
        const fichaH = d.ficha && !d.seq && d.items.length === 1 && portrait ? 330 : 0;
        // sequência (rodada rápida): uma camisa grande por vez; senão todas lado a lado
        const n = d.seq ? 1 : d.items.length;
        const cols = portrait ? (n > 3 ? 2 : 1) : n;
        const rows = Math.ceil(n / cols);
        const gap = 26;
        const areaW = box.w - fichaW;
        const areaH = box.h - fichaH;
        const fw = Math.min((areaW - 70 - (cols - 1) * gap) / cols, portrait ? box.w - 100 : 760);
        const fh = Math.min((areaH - 90 - rows * labelH - (rows - 1) * gap) / rows, fw * (n === 1 ? (portrait ? 1.15 : 0.82) : 1.2));
        const x0 = (areaW - (cols * fw + (cols - 1) * gap)) / 2;
        const y0 = (areaH - (rows * (fh + labelH) + (rows - 1) * gap)) / 2 + 10;
        d.items.forEach((it, i) => {
          const k = d.seq ? 0 : i;
          const cx = x0 + (k % cols) * (fw + gap);
          const cy = y0 + Math.floor(k / cols) * (fh + labelH + gap);
          const f = h("div", `foto-frame${d.kenburns ? " kb" : ""}${it.file ? "" : " sem-foto"}`);
          Object.assign(f.style, { left: `${cx}px`, top: `${cy}px`, width: `${fw}px`, height: `${fh}px` });
          if (it.file) {
            const fundo = h("img", "fundo");
            fundo.src = file(it.file);
            f.appendChild(fundo);
          }
          const img = h("img");
          img.src = file(it.file || it.crest);
          f.appendChild(img);
          el.appendChild(f);
          let lb = null;
          if (it.label) {
            lb = h("div", "foto-label anton");
            if (it.crest || it.sigla) lb.appendChild(crest({ crest: it.crest, sigla: it.sigla }, labelH * 0.7));
            lb.appendChild(h("span", "", it.label));
            Object.assign(lb.style, { left: `${cx - 40}px`, top: `${cy + fh + 10}px`, width: `${fw + 80}px`, fontSize: `${Math.min(32, ((fw + 80) * 1.7) / Math.max(10, it.label.length))}px` });
            el.appendChild(lb);
          }
          r.items.push({ f, img, lb, it });
        });
        if (fichaW || fichaH) {
          const fc = h("div", "ficha");
          if (portrait) Object.assign(fc.style, { left: "40px", right: "40px", top: `${box.h - fichaH - 10}px`, height: `${fichaH}px` });
          else Object.assign(fc.style, { left: `${areaW}px`, width: `${fichaW - 50}px`, top: `${box.h * 0.2}px` });
          const nomes = ["CLUBE", "FORNECEDORA", "LANÇAMENTO", "INSPIRAÇÃO"];
          r.ficha = d.ficha.map((t, i) => {
            const l = h("div", "fl");
            l.append(h("span", "fk", nomes[i] || ""), h("span", "fv anton", t));
            fc.appendChild(l);
            return l;
          });
          el.appendChild(fc);
        }
        return r;
      },
      update(r, d, lt, dur) {
        let atual = 0;
        if (r.seq) r.items.forEach((x, i) => { if (lt >= (x.it.at ?? i * 4) - 0.05) atual = i; });
        r.items.forEach((x, i) => {
          const at = x.it.at != null ? x.it.at : 0.2 + i * 0.4;
          if (r.seq) {
            // "arara": a camisa da vez entra pela direita e a anterior sai pela esquerda
            const on = i === atual;
            const q = outCubic(prog(lt, at, 0.35));
            const next = r.items[i + 1];
            const sai = next && i < atual ? outCubic(prog(lt, next.it.at ?? 0, 0.35)) : 0;
            x.f.style.opacity = String(on || sai < 1 ? Math.min(q, 1 - sai) : 0);
            x.f.style.transform = `translateX(${(500 * (1 - q) - 600 * sai).toFixed(1)}px) perspective(900px) rotateY(${(-25 * (1 - q) + 25 * sai).toFixed(1)}deg)`;
            if (x.lb) {
              x.lb.style.opacity = String(on ? fade(lt, at + 0.2, 0.15) : 0);
              x.lb.style.transform = `translateY(${(14 * (1 - outCubic(prog(lt, at + 0.2, 0.25)))).toFixed(1)}px)`;
            }
          } else {
            // cabide: entra de cima balançando
            const q = outBack(prog(lt, at, 0.5), 1.6);
            const ang = Math.sin((lt - at) * 5) * 6 * Math.exp(-(lt - at) * 2.2) * (lt > at ? 1 : 0);
            x.f.style.opacity = String(fade(lt, at, 0.12));
            x.f.style.transformOrigin = "50% -40px";
            x.f.style.transform = `translateY(${(-160 * (1 - q)).toFixed(1)}px) rotate(${ang.toFixed(2)}deg)`;
            if (x.lb) {
              x.lb.style.opacity = String(fade(lt, at + 0.25, 0.2));
              x.lb.style.transform = `translateY(${(20 * (1 - outCubic(prog(lt, at + 0.25, 0.3)))).toFixed(1)}px)`;
            }
          }
          // zoom lento (Ken Burns)
          const kb = d.kenburns ? 0.12 : 0.05;
          x.img.style.transform = `scale(${(1 + kb * clamp((lt - at) / Math.max(1, dur))).toFixed(4)})`;
        });
        if (r.ficha) r.ficha.forEach((l, i) => {
          const q = outCubic(prog(lt, 0.5 + i * 0.45, 0.35));
          l.style.opacity = String(q);
          l.style.transform = `translateX(${(60 * (1 - q)).toFixed(1)}px)`;
        });
      },
    };

    // ---------------------------------------------------------------- placa de nota (jurado de TV)
    T.nota = {
      fit: true,
      build(el, d, box) {
        bg(el);
        const r = {};
        const s = Math.min(box.w, box.h) * 0.55;
        r.p = h("div", "nota-placa");
        Object.assign(r.p.style, { width: `${s * 0.8}px`, height: `${s}px`, left: `${(box.w - s * 0.8) / 2}px`, top: `${(box.h - s) / 2}px` });
        r.lb = h("div", "nota-lb anton", d.label || "NOTA");
        r.lb.style.fontSize = `${s * 0.09}px`;
        r.v = h("div", "nota-v anton", d.value);
        r.v.style.fontSize = `${s * (String(d.value).length > 2 ? 0.42 : 0.56)}px`;
        r.p.append(r.lb, r.v);
        el.appendChild(r.p);
        return r;
      },
      update(r, d, lt) {
        // gira e mostra o número
        const q = outCubic(prog(lt, 0, 0.7));
        r.p.style.transform = `perspective(900px) rotateY(${(540 * (1 - q)).toFixed(1)}deg) scale(${(0.6 + 0.4 * outBack(prog(lt, 0, 0.5), 1.6)).toFixed(3)})`;
        r.p.style.opacity = String(fade(lt, 0, 0.1));
        r.v.style.opacity = String(fade(lt, 0.55, 0.15));
      },
    };

    // ---------------------------------------------------------------- corrida de barras (enquete)
    T.barras = {
      fit: true,
      build(el, d, box) {
        bg(el);
        const r = { rows: [] };
        const rows = d.rows.slice(0, 10);
        const max = Math.max(...rows.map((x) => x.value));
        // abaixo da marca d'água (e da coroa); no vertical as linhas ocupam a altura toda
        const portrait = box.h > box.w * 1.1;
        const livre = box.h - 120 - (d.fonte ? 80 : 40);
        const rh = Math.min(portrait ? 135 : 78, livre / rows.length);
        const top = 120 + Math.max(0, (livre - rh * rows.length) / 2);
        // 9:16: nome e valor em cima, barra larga embaixo (a tela é estreita)
        const lw = portrait ? box.w * 0.6 : box.w * 0.24;
        const vf = portrait ? Math.min(rh * 0.3, 40) : Math.min(rh * 0.5, 40); // fonte do valor
        const vw = vf * 3.4; // "29,4%"
        const bw = portrait ? box.w - 80 - rh * 0.5 : box.w - lw - 80 - 32 - vw;
        rows.forEach((x, i) => {
          const row = h("div", `bar-row${portrait ? " empilhada" : ""}`);
          Object.assign(row.style, { top: `${top + i * rh}px`, height: `${rh - 10}px`, left: "40px", right: "40px" });
          const lb = h("div", "bar-lb anton", x.label);
          Object.assign(lb.style, { width: `${lw}px`, flexShrink: "0" });
          lb.style.fontSize = `${Math.min(rh * (portrait ? 0.3 : 0.5), (lw * 1.7) / Math.max(6, x.label.length))}px`;
          const tr = h("div", "bar-tr");
          Object.assign(tr.style, { width: `${bw}px`, flexShrink: "0" });
          if (portrait) Object.assign(tr.style, { order: "3", height: `${rh * 0.36}px` });
          const fill = h("i");
          tr.appendChild(fill);
          const cr = crest({ crest: x.crest, sigla: x.sigla }, rh * (portrait ? 0.5 : 0.8));
          cr.classList.add("bar-cr");
          tr.appendChild(cr);
          const v = h("div", "bar-v anton", "0");
          Object.assign(v.style, { fontSize: `${vf}px`, minWidth: `${vw}px` });
          row.append(lb, tr, v);
          el.appendChild(row);
          r.rows.push({ row, tr, fill, cr, v, x, w: (x.value / max) * (bw - rh * (portrait ? 0.55 : 0.9)) });
        });
        if (d.fonte) {
          const f = h("div", "bar-fonte", d.fonte);
          el.appendChild(f);
        }
        if (d.coroa && r.rows[0]) {
          r.coroa = h("div", "bar-coroa", "👑");
          r.rows[0].tr.appendChild(r.coroa);
        }
        return r;
      },
      update(r, d, lt, dur) {
        const tempo = Math.min(3.5, dur * 0.6);
        r.rows.forEach((x, i) => {
          const at = x.x.at != null ? x.x.at : 0.2 + i * 0.15;
          const q = outCubic(prog(lt, at, tempo));
          x.row.style.opacity = String(fade(lt, at, 0.2));
          x.fill.style.width = `${(x.w * q).toFixed(1)}px`;
          x.cr.style.left = `${(x.w * q).toFixed(1)}px`;
          x.v.textContent = `${(x.x.value * q).toFixed(1).replace(".", ",")}%`;
          const pisca = x.x.destaque && lt > at + tempo ? 0.6 + 0.4 * Math.abs(Math.sin(lt * 6)) : 1;
          x.fill.style.opacity = String(pisca);
        });
        if (r.coroa) {
          const q = outBack(prog(lt, tempo + 0.4, 0.4), 2);
          r.coroa.style.opacity = String(fade(lt, tempo + 0.4, 0.1));
          r.coroa.style.transform = `translateY(${(-40 * (1 - q)).toFixed(1)}px) scale(${q.toFixed(3)})`;
          r.coroa.style.left = r.rows[0].cr.style.left;
        }
      },
    };

    // ---------------------------------------------------------------- gancho escrito (início dos cortes 9:16)
    T.gancho = {
      fit: true,
      overlay: true,
      build(el, d, box) {
        const r = { linhas: [] };
        const w = h("div", "gancho");
        w.style.top = `${box.h * 0.1}px`;
        const palavras = String(d.text || "").toUpperCase().split(/\s+/).filter(Boolean);
        const porLinha = Math.max(2, Math.ceil(palavras.length / Math.ceil(palavras.length / 3)));
        for (let i = 0; i < palavras.length; i += porLinha) {
          const l = h("div", `gl anton${(i / porLinha) % 2 ? " alt" : ""}`, palavras.slice(i, i + porLinha).join(" "));
          l.style.fontSize = `${Math.min(84, (box.w * 1.5) / Math.max(6, l.textContent.length))}px`;
          w.appendChild(l);
          r.linhas.push(l);
        }
        el.appendChild(w);
        return r;
      },
      update(r, d, lt, dur) {
        const x = inCubic(prog(lt, dur - 0.25, 0.25));
        r.linhas.forEach((l, i) => {
          const q = outBack(prog(lt, i * 0.18, 0.3), 2.2);
          l.style.opacity = String(fade(lt, i * 0.18, 0.08) * (1 - x));
          l.style.transform = `rotate(${i % 2 ? 2 : -2}deg) scale(${(0.5 + 0.5 * q).toFixed(3)})`;
        });
      },
    };

    // ---------------------------------------------------------------- selo fixo @detto.galo
    T.watermark = {
      overlay: true,
      fit: true,
      build(el, d) {
        const w = h("div", "wm anton", d.text || "@detto.galo");
        el.appendChild(w);
        return { w };
      },
      update() {},
    };

    return T;
  });
})();
