#!/usr/bin/env node
"use strict";

/**
 * Edição dinâmica (estilo Reels/YouTube de futebol) a partir do EDIT_PLAN:
 *
 *   node tools/render-dynamic.js EDIT_PLAN.json --video gravacao.mov --out edicao.mp4 \
 *        --fonts ./fonts [--work ./tmp] [--workers 3] [--to 60] [--crf 23]
 *
 * Etapas: diretor (timeline dinâmica) → camada de motion graphics (Chromium) →
 * SFX sintetizados → composição ffmpeg. O plano precisa ter sido gerado com
 * --words (meta.segments e captions).
 */

const fs = require("fs");
const path = require("path");
const os = require("os");
const { direct } = require("./motion/director");
const { ensureFlags } = require("./motion/flags");
const { renderLayer } = require("./motion/render-layer");
const { writeSfxTrack } = require("./motion/sfx");
const { compose } = require("./motion/compose");

function args(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith("--")) out[argv[i].slice(2)] = argv[++i];
    else out._.push(argv[i]);
  }
  return out;
}

async function main() {
  const a = args(process.argv.slice(2));
  if (!a._[0] || !a.video || !a.out || !a.fonts) {
    console.error("uso: render-dynamic.js <EDIT_PLAN.json> --video <arquivo> --out <saida.mp4> --fonts <dir com Anton-Regular.ttf> [--work dir] [--workers 3] [--to s]");
    process.exit(2);
  }
  const t0 = Date.now();
  const log = (m) => console.error(`[${((Date.now() - t0) / 1000).toFixed(0).padStart(4)}s] ${m}`);
  const plan = JSON.parse(fs.readFileSync(a._[0], "utf-8"));
  const work = a.work || fs.mkdtempSync(path.join(os.tmpdir(), "detto-dyn-"));
  fs.mkdirSync(work, { recursive: true });

  const d = direct(plan);
  if (a.to) {
    // prévia parcial: corta a timeline
    const to = Number(a.to);
    d.duration = Math.min(d.duration, to);
    d.items = d.items.filter((i) => i.start < to).map((i) => ({ ...i, end: Math.min(i.end, to) }));
    d.sfx = d.sfx.filter((s) => s.t < to);
  }
  fs.writeFileSync(path.join(work, "direction.json"), JSON.stringify(d, null, 1));
  log(`diretor: ${d.stats.plates} placas, ${d.stats.overlays} sobreposições, ${d.stats.captions} legendas, ${d.stats.shots} enquadramentos, ${d.sfx.length} SFX`);

  const flagsDir = path.join(work, "flags");
  const codes = d.items.flatMap((i) => [i.data?.a?.flag, i.data?.b?.flag, ...(i.data?.rows || []).flatMap((r) => r.flags || [])]);
  const missing = await ensureFlags(codes, flagsDir);
  if (missing.length) log(`bandeiras indisponíveis: ${missing.join(", ")}`);

  const layer = await renderLayer({
    items: d.items,
    duration: d.duration,
    fps: d.fps,
    outDir: path.join(work, "layer"),
    fontsDir: a.fonts,
    flagsDir,
    workers: Number(a.workers || 3),
    onProgress: (done, total) => log(`gráficos: ${done}/${total} quadros`),
  });
  log(`camada de gráficos: ${layer.activeFrames}/${layer.totalFrames} quadros ativos`);

  const sfxWav = writeSfxTrack(d.sfx, d.duration, path.join(work, "sfx.wav"));
  log("SFX sintetizados");

  compose({ plan, direction: d, video: a.video, layerVideo: layer.video, sfxWav, out: a.out, tmpDir: work, crf: a.crf ? Number(a.crf) : 23, width: Number(a.width || 1280), height: Number(a.height || 720) });
  log(`pronto: ${a.out}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
