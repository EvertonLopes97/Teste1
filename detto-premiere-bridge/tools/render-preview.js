#!/usr/bin/env node
"use strict";

/**
 * Renderiza uma PRÉVIA do EDIT_PLAN com ffmpeg (fora do Premiere), para revisar
 * tempos, textos e efeitos antes de montar no Premiere.
 *
 *   node tools/render-preview.js EDIT_PLAN.json --video gravacao.mov --out previa.mp4 \
 *        [--width 1280] [--height 720] [--fonts ./fonts] [--from 0] [--to 120] [--crf 28]
 *
 * O que entra na prévia: cortes (trechos da mídia na ordem da timeline), textos dos
 * graphics por tipo, punch-in/zoom lento, P&B, sépia, letterbox, vinheta, flash,
 * fade, tremor, linha do tempo no rodapé, títulos de bloco e etiquetas de B-ROLL.
 * O que NÃO entra: b-roll real, trilha e SFX (não fazem parte da mídia enviada).
 */

const fs = require("fs");
const path = require("path");
const os = require("os");
const { spawnSync } = require("child_process");
const { filtroComplexo } = require("./motion/ffopts");

const COLORS = { gold: "0xD4AF37", celeste: "0x75AADB", red: "0xC8102E", navy: "0x0B1D3A" };

function args(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith("--")) out[argv[i].slice(2)] = argv[++i];
    else out._.push(argv[i]);
  }
  return out;
}

/** Fontes sem emoji e sem algumas setas: normaliza para glifos seguros. */
function sanitize(text) {
  return String(text)
    .replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}]/gu, "")
    .replace(/→/g, "›")
    .replace(/─+/g, "—")
    .replace(/\s+/g, " ")
    .trim();
}

/** Quebra em linhas de até `max` caracteres. */
function wrap(text, max) {
  const words = text.split(" ");
  const lines = [];
  let cur = "";
  for (const w of words) {
    if ((cur + " " + w).trim().length > max && cur) {
      lines.push(cur);
      cur = w;
    } else cur = (cur + " " + w).trim();
  }
  if (cur) lines.push(cur);
  return lines.join("\n");
}

const between = (a, b) => `between(t,${a.toFixed(3)},${b.toFixed(3)})`;

/**
 * Converte tempo da timeline do plano → tempo da prévia (quando --from/--to recortam).
 */
function buildFilter(plan, opts) {
  const { W, H, fontsDir, tmp, from, to } = opts;
  const anton = path.join(fontsDir, "Anton-Regular.ttf");
  const body = opts.bodyFont;
  const dur = to - from;
  const local = (t) => t - from;
  const visible = (s, e) => e > from && s < to;
  const filters = [];
  let n = 0;
  const textFile = (text) => {
    const f = path.join(tmp, `t${n++}.txt`);
    fs.writeFileSync(f, text);
    return f;
  };
  const esc = (p) => p.replace(/\\/g, "/").replace(/:/g, "\\:").replace(/'/g, "\\'");
  const drawtext = (o) =>
    `drawtext=fontfile='${esc(o.font)}':textfile='${esc(textFile(o.text))}':expansion=none:fontsize=${o.size}:fontcolor=${o.color}` +
    `:x=${o.x}:y=${o.y}:line_spacing=6` +
    (o.box ? `:box=1:boxcolor=${o.box}:boxborderw=${o.pad || 14}` : "") +
    (o.border ? `:borderw=${o.border}:bordercolor=black` : "") +
    `:enable='${between(local(o.start), local(o.end))}'`;

  // ---------- montagem dos cortes (trechos da mídia na timeline)
  const cuts = (plan.cuts || []).filter((c) => !c.track || /^(V1|PRESENTER|1)$/i.test(String(c.track)));
  const segs = cuts
    .map((c) => ({ in: c.start, out: c.end, at: c.timeline }))
    .filter((c) => visible(c.at, c.at + (c.out - c.in)))
    .sort((a, b) => a.at - b.at);

  // ---------- efeitos de vídeo a partir dos vfx
  const vfx = (plan.vfx || []).filter((v) => visible(v.start, v.start + v.duration));
  const ranges = (re) => vfx.filter((v) => re.test(v.name)).map((v) => [local(v.start), local(v.start + v.duration)]);
  const anyOf = (rs) => (rs.length ? rs.map(([a, b]) => between(a, b)).join("+") : "0");

  const punch = ranges(/ZOOM_PUNCH_IN/);
  const slow = ranges(/SLOW_ZOOM/);
  const shake = ranges(/CAMERA_SHAKE/);
  const zParts = [`1`];
  if (punch.length) zParts.push(`0.13*(${anyOf(punch).replace(/\bt\b/g, "it")})`);
  for (const [a, b] of slow) zParts.push(`0.10*between(it,${a.toFixed(3)},${b.toFixed(3)})*(it-${a.toFixed(3)})/${(b - a).toFixed(3)}`);
  if (shake.length) zParts.push(`0.04*(${anyOf(shake).replace(/\bt\b/g, "it")})`);
  const z = zParts.join("+");
  const sx = shake.length ? `+10*sin(it*47)*(${anyOf(shake).replace(/\bt\b/g, "it")})` : "";
  const sy = shake.length ? `+8*cos(it*53)*(${anyOf(shake).replace(/\bt\b/g, "it")})` : "";

  const chain = [];
  // fundo desfocado para mídia vertical ou de proporção diferente
  chain.push(`split=2[bg][fg]`);
  const pre = [];
  pre.push(`[bg]scale=${W}:${H}:force_original_aspect_ratio=increase,crop=${W}:${H},boxblur=24:2,eq=brightness=-0.15[bgb]`);
  pre.push(`[fg]scale=${W}:${H}:force_original_aspect_ratio=decrease[fgs]`);
  pre.push(`[bgb][fgs]overlay=(W-w)/2:(H-h)/2,setsar=1`);

  const post = [];
  post.push(
    `zoompan=z='${z}':x='iw/2-(iw/zoom/2)${sx}':y='ih/2-(ih/zoom/2)${sy}':d=1:s=${W}x${H}:fps=${opts.fps}`
  );
  const desat = ranges(/DESATURATE/);
  if (desat.length) post.push(`hue=s=0:enable='${anyOf(desat)}'`);
  const sepia = ranges(/SEPIA|FILM_GRAIN/);
  if (sepia.length) post.push(`colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131:enable='${anyOf(sepia)}'`);
  const grain = ranges(/FILM_GRAIN/);
  if (grain.length) post.push(`noise=alls=14:allf=t:enable='${anyOf(grain)}'`);
  const glow = ranges(/GOLD_GLOW|CONFETTI/);
  if (glow.length) post.push(`eq=brightness=0.06:saturation=1.25:gamma_r=1.08:gamma_b=0.92:enable='${anyOf(glow)}'`);
  const vig = ranges(/VIGNETTE|BREATH/);
  if (vig.length) post.push(`vignette=PI/4:enable='${anyOf(vig)}'`);
  const lb = ranges(/LETTERBOX/);
  if (lb.length) {
    const bar = Math.round(H * 0.11);
    post.push(`drawbox=x=0:y=0:w=iw:h=${bar}:color=black:t=fill:enable='${anyOf(lb)}'`);
    post.push(`drawbox=x=0:y=ih-${bar}:w=iw:h=${bar}:color=black:t=fill:enable='${anyOf(lb)}'`);
  }

  // ---------- B-ROLL e títulos de bloco (a partir dos markers)
  for (const m of plan.markers || []) {
    const end = m.time + (m.duration || 3);
    if (!visible(m.time, end)) continue;
    if (/^B-ROLL:/.test(m.name)) {
      post.push(
        drawtext({
          font: body, size: Math.round(H * 0.028), color: "white", box: "black@0.55", pad: 8,
          x: "(w-text_w)/2", y: Math.round(H * 0.035), start: m.time, end,
          text: wrap(sanitize(`[B-ROLL V2] ${m.name.replace(/^B-ROLL:\s*/, "")}`), 70),
        })
      );
    } else if (m.color === "blue" && /BLOCO|ABERTURA|FECHAMENTO/.test(m.name)) {
      post.push(
        drawtext({
          font: anton, size: Math.round(H * 0.05), color: COLORS.gold, border: 3,
          x: "(w-text_w)/2", y: Math.round(H * 0.1), start: m.time, end: m.time + 3,
          text: sanitize(m.name),
        })
      );
    }
  }

  // ---------- graphics por tipo (empilha itens simultâneos do mesmo tipo)
  const active = {};
  const graphics = (plan.graphics || [])
    .filter((g) => g.type !== "generic" && g.type !== "timeline_bar" && visible(g.start, g.start + g.duration))
    .sort((a, b) => a.start - b.start);
  for (const g of graphics) {
    const end = g.start + g.duration;
    const list = (active[g.type] = (active[g.type] || []).filter((x) => x.end > g.start));
    const slot = list.length;
    list.push({ end });
    const text = sanitize(g.text);
    if (!text) continue;
    const S = (f) => Math.round(H * f);
    const base = { start: g.start, end };
    switch (g.type) {
      case "date_stamp":
        post.push(drawtext({ ...base, font: anton, size: S(0.045), color: COLORS.gold, box: "black@0.6", pad: 12, x: S(0.04), y: S(0.06) + slot * S(0.08), text: wrap(text, 30) }));
        break;
      case "counter":
        post.push(drawtext({ ...base, font: anton, size: S(0.06), color: COLORS.gold, border: 3, x: `w-text_w-${S(0.04)}`, y: S(0.06) + slot * S(0.09), text: wrap(text, 26) }));
        break;
      case "scoreboard":
        post.push(drawtext({ ...base, font: body, size: S(0.038), color: COLORS.navy, box: "white@0.93", pad: 16, x: "(w-text_w)/2", y: `h-text_h-${S(0.1) + slot * S(0.085)}`, text: wrap(text, 52) }));
        break;
      case "cta":
        post.push(drawtext({ ...base, font: anton, size: S(0.055), color: "white", box: `${COLORS.red}@0.9`, pad: 16, x: "(w-text_w)/2", y: S(0.2) + slot * S(0.1), text: wrap(text, 34) }));
        break;
      case "stat_card":
        post.push(drawtext({ ...base, font: anton, size: S(0.06), color: "white", box: `${COLORS.celeste}@0.85`, pad: 22, x: "(w-text_w)/2", y: S(0.32) + slot * S(0.12), text: wrap(text, 30) }));
        break;
      case "overlay":
        post.push(drawtext({ ...base, font: body, size: S(0.03), color: "white", box: "black@0.5", pad: 8, x: "(w-text_w)/2", y: S(0.42) + slot * S(0.07), text: wrap(`[GRÁFICO] ${text}`, 60) }));
        break;
      default:
        post.push(drawtext({ ...base, font: anton, size: S(0.075), color: COLORS.gold, border: 4, x: "(w-text_w)/2", y: S(0.66) + slot * S(0.1), text: wrap(text, 34) }));
    }
  }

  // ---------- linha do tempo no rodapé (anos a partir dos markers)
  const years = (plan.markers || [])
    .map((m) => ({ t: m.time, y: (m.name.match(/LINHA DO TEMPO → (\d{4})/) || [])[1] }))
    .filter((x) => x.y);
  const tlStart = ((plan.graphics || []).find((g) => g.type === "timeline_bar") || {}).start;
  if (typeof tlStart === "number" && tlStart < to) {
    const t0 = local(tlStart);
    const barY = H - Math.round(H * 0.03);
    post.push(`drawbox=x=0:y=${barY}:w=iw:h=${Math.max(3, Math.round(H * 0.006))}:color=white@0.35:t=fill:enable='gte(t,${t0.toFixed(3)})'`);
    post.push(`drawbox=x=0:y=${barY}:w='iw*min(1,(t+${from})/${(plan.cuts.at(-1).timeline + plan.cuts.at(-1).end - plan.cuts.at(-1).start).toFixed(3)})':h=${Math.max(3, Math.round(H * 0.006))}:color=${COLORS.gold}:t=fill:enable='gte(t,${t0.toFixed(3)})'`);
    const marks = [{ t: tlStart, y: "2005" }, ...years];
    marks.forEach((mk, i) => {
      const end = i + 1 < marks.length ? marks[i + 1].t : to + 1;
      if (!visible(mk.t, end)) return;
      post.push(drawtext({ font: anton, size: Math.round(H * 0.032), color: COLORS.gold, border: 2, x: Math.round(H * 0.03), y: barY - Math.round(H * 0.05), start: mk.t, end, text: `${mk.y}  —  2026` }));
    });
  }

  // ---------- flash inicial / fade final
  const flash = ranges(/FLASH/);
  if (flash.length && flash[0][0] <= 0.1) post.push(`fade=t=in:st=0:d=0.6:color=white`);
  const fadeOut = ranges(/FADE_TO_BLACK/);
  if (fadeOut.length) {
    const [a, b] = fadeOut[0];
    post.push(`fade=t=out:st=${Math.max(a, b - 2).toFixed(3)}:d=2`);
  }

  return { segs, pre, post, chain, dur };
}

/** Áudio: normaliza a voz e, se houver, aplica o bip opcional (type "bleep"). */
function audioChain(plan, from, to) {
  const bleeps = (plan.audio || []).filter((x) => x.type === "bleep" && x.start < to && x.start + x.duration > from);
  if (!bleeps.length) return [`[ca]loudnorm=I=-16:TP=-1.5:LRA=11[aout]`];
  const on = bleeps.map((b) => between(b.start - from, b.start - from + b.duration)).join("+");
  return [
    `[ca]volume=0:enable='${on}',loudnorm=I=-16:TP=-1.5:LRA=11[voz]`,
    `sine=f=1000:sample_rate=48000:d=${(to - from).toFixed(3)},volume=0.18,volume=0:enable='not(${on})'[bip]`,
    `[voz][bip]amix=inputs=2:duration=first:normalize=0[aout]`,
  ];
}

function main() {
  const a = args(process.argv.slice(2));
  if (!a._[0] || !a.video || !a.out) {
    console.error("uso: render-preview.js <EDIT_PLAN.json> --video <arquivo> --out <previa.mp4> [--width 1280] [--height 720] [--from s] [--to s] [--fonts dir] [--crf 28]");
    process.exit(2);
  }
  const plan = JSON.parse(fs.readFileSync(a._[0], "utf-8"));
  const fps = (plan.sequence && plan.sequence.fps) || 30;
  const W = Number(a.width || 1280);
  const H = Number(a.height || 720);
  const fontsDir = a.fonts || path.join(__dirname, "fonts");
  const bodyFont = fs.existsSync(path.join(fontsDir, "Montserrat-SemiBold.ttf"))
    ? path.join(fontsDir, "Montserrat-SemiBold.ttf")
    : (spawnSync("fc-match", ["-f", "%{file}", "Inter:style=SemiBold"]).stdout || "").toString() || "DejaVuSans.ttf";
  const last = plan.cuts.reduce((m, c) => Math.max(m, c.timeline + (c.end - c.start)), 0);
  const from = Number(a.from || 0);
  const to = Math.min(Number(a.to || last), last);
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "detto-preview-"));

  const f = buildFilter(plan, { W, H, fps, fontsDir, bodyFont, tmp, from, to });

  // trechos da mídia em uma única passada (select/aselect): memória constante mesmo
  // com dezenas de jump cuts (trim+concat abriria um ramo de decodificação por corte)
  const ranges = f.segs.map((s) => {
    const segStart = Math.max(s.at, from);
    const segEnd = Math.min(s.at + (s.out - s.in), to);
    const inP = s.in + (segStart - s.at);
    return [inP, inP + (segEnd - segStart)];
  });
  // vídeo por índice de frame (contagem exata) e áudio em blocos de 64 amostras:
  // sem isso o erro de cada corte se acumula e a sincronia labial escorrega no fim
  const vExpr = ranges.map(([a, b]) => `between(n,${Math.round(a * fps)},${Math.round(b * fps) - 1})`).join("+");
  const aExpr = ranges.map(([a, b]) => `between(t,${(Math.round(a * fps) / fps).toFixed(4)},${(Math.round(b * fps) / fps - 0.0001).toFixed(4)})`).join("+");
  const graph = [
    `[0:v]fps=${fps},select='${vExpr}',setpts=N/FRAME_RATE/TB,${f.chain.join(",")}`,
    ...f.pre.slice(0, 2),
    `${f.pre[2]},${f.post.join(",")}[vout]`,
    `[0:a]aresample=48000,asetnsamples=n=64:p=0,aselect='${aExpr}',asetpts=N/SR/TB,asetnsamples=n=1024:p=0[ca]`,
    ...audioChain(plan, from, to),
  ].join(";\n");
  const script = path.join(tmp, "filter.txt");
  fs.writeFileSync(script, graph);

  const ff = [
    "-y", "-hide_banner", "-loglevel", "error", "-nostats",
    "-i", a.video,
    ...filtroComplexo(script),
    "-map", "[vout]", "-map", "[aout]",
    "-t", (f.segs.reduce((n, sg) => n + Math.max(0, Math.min(sg.at + (sg.out - sg.in), to) - Math.max(sg.at, from)), 0)).toFixed(3),
    "-c:v", "libx264", "-preset", a.preset || "veryfast", "-crf", String(a.crf || 28), "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
    a.out,
  ];
  console.error(`prévia ${W}x${H} @${fps}fps, ${f.segs.length} cortes, ${f.post.length} filtros → ${a.out}`);
  const r = spawnSync("ffmpeg", ff, { stdio: "inherit" });
  if (r.status !== 0) {
    console.error(`ffmpeg falhou (filtro em ${script})`);
    process.exit(r.status || 1);
  }
  fs.rmSync(tmp, { recursive: true, force: true });
}

if (require.main === module) main();
module.exports = { buildFilter, sanitize, wrap };
