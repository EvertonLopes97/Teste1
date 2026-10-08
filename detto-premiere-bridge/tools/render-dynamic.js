#!/usr/bin/env node
"use strict";

/**
 * Edição dinâmica (estilo Reels/YouTube de futebol) a partir do EDIT_PLAN.
 *
 *   node tools/render-dynamic.js EDIT_PLAN.json --video gravacao.mov --out edicao.mp4 \
 *        --fonts ./fonts --face face.json [--work ./tmp] [--workers 4]
 *        [--format horizontal|vertical] [--cut N] [--from s --to s]
 *        [--no-images 1] [--crf 18] [--scale 1.5]
 *
 *   --face     rastreamento do rosto (tools/motion/facetrack.py); centraliza zooms e janelas
 *   --format   horizontal (1920x1080) ou vertical (1080x1920)
 *   --cut N    corte vertical N sugerido no roteiro ("9:16 #N"); implica --format vertical
 *
 * Etapas: fotos de apoio (Openverse, licenças livres) → diretor → quadros da gravação →
 * composição no Chromium (câmera + gráficos) → áudio (voz + SFX) → H.264.
 */

const fs = require("fs");
const path = require("path");
const os = require("os");
const crypto = require("crypto");
const { spawnSync } = require("child_process");
const { direct } = require("./motion/director");
const { ensureFlags } = require("./motion/flags");
const { findImages, creditsText } = require("./motion/media-search");
const { writeSfxTrack } = require("./motion/sfx");
const { renderComposite, extractCamFrames } = require("./motion/render-frames");
const { buildAudio } = require("./motion/audio");

function args(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith("--")) out[argv[i].slice(2)] = argv[++i];
    else out._.push(argv[i]);
  }
  return out;
}

/** Trechos (timeline) do corte vertical N, a partir dos markers "9:16 #N". */
function cutRanges(plan, n) {
  const ms = (plan.markers || []).filter((m) => new RegExp(`^9:16 #${n}\\b`).test(m.name));
  if (!ms.length) throw new Error(`corte vertical #${n} não existe no plano`);
  return ms.sort((a, b) => a.time - b.time).map((m) => [m.time, m.time + (m.duration || 0)]);
}

async function main() {
  const a = args(process.argv.slice(2));
  if (!a._[0] || !a.video || !a.out || !a.fonts) {
    console.error("uso: render-dynamic.js <EDIT_PLAN.json> --video <gravação> --out <saida.mp4> --fonts <dir> [--face face.json] [--format vertical] [--cut N] [--from s --to s]");
    process.exit(2);
  }
  const t0 = Date.now();
  const log = (m) => console.error(`[${((Date.now() - t0) / 1000).toFixed(0).padStart(5)}s] ${m}`);
  const plan = JSON.parse(fs.readFileSync(a._[0], "utf-8"));
  const work = a.work || fs.mkdtempSync(path.join(os.tmpdir(), "detto-dyn-"));
  fs.mkdirSync(work, { recursive: true });
  const format = a.cut ? "vertical" : a.format || "horizontal";
  const face = a.face ? JSON.parse(fs.readFileSync(a.face, "utf-8")) : null;
  if (!face) log("aviso: sem --face, zooms usam o centro da imagem");

  // 1. fotos de apoio (b-roll) com licença livre
  let images = {};
  if (!a["no-images"]) {
    const needs = ((plan.meta && plan.meta.segments) || [])
      .filter((s) => s.broll)
      .map((s) => {
        const m = (plan.markers || []).find((x) => /^B-ROLL/.test(x.name) && Math.abs(x.time - s.start) < 0.05);
        return { id: s.id, time: s.start, text: `${m ? m.comment : ""} ${s.block}` };
      });
    images = findImages(needs, { cacheDir: path.join(work, "media"), log });
    fs.writeFileSync(path.join(work, "creditos.txt"), creditsText(images));
    log(`fotos: ${Object.keys(images).length}/${needs.length} trechos com imagem (créditos em ${path.join(work, "creditos.txt")})`);
  }

  // 2. diretor
  const d = direct(plan, { images });
  fs.writeFileSync(path.join(work, "direction.json"), JSON.stringify(d, null, 1));
  log(`diretor: ${JSON.stringify(d.stats)}`);

  // 3. trechos a renderizar
  let ranges = [[0, d.duration]];
  if (a.cut) ranges = cutRanges(plan, a.cut);
  else if (a.from || a.to) ranges = [[Number(a.from || 0), Math.min(d.duration, Number(a.to || d.duration))]];
  const total = ranges.reduce((s, [x, y]) => s + (y - x), 0);
  log(`formato ${format}, ${ranges.map(([x, y]) => `${x.toFixed(1)}–${y.toFixed(1)}s`).join(" + ")} (${total.toFixed(1)}s)`);

  const flagsDir = path.join(work, "flags");
  await ensureFlags(d.items.flatMap((i) => [i.data?.a?.flag, i.data?.b?.flag, ...(i.data?.rows || []).flatMap((r) => r.flags || [])]), flagsDir);

  // 4. quadros da gravação (com jump cuts) e composição
  const camDir = path.join(work, "cam");
  extractCamFrames(plan, a.video, camDir, d.fps);
  log("quadros da gravação extraídos");
  // quadros já compostos são reaproveitados só se direção, formato e trechos forem os mesmos
  const key = crypto.createHash("sha1").update(JSON.stringify([d, format, ranges, a.scale || 1.5])).digest("hex").slice(0, 10);
  const framesDir = path.join(work, `frames_${format}${a.cut ? `_cut${a.cut}` : ""}_${key}`);
  const n = await renderComposite({
    plan,
    direction: d,
    camDir,
    outDir: framesDir,
    face,
    fontsDir: a.fonts,
    flagsDir,
    format,
    scale: Number(a.scale || 1.5),
    ranges,
    workers: Number(a.workers || 4),
    onProgress: (done, all) => log(`composição: ${done}/${all} quadros`),
  });
  log(`composição: ${n} quadros`);

  // 5. áudio
  const sfxWav = writeSfxTrack(d.sfx, d.duration, path.join(work, "sfx.wav"));
  const audio = buildAudio({ plan, duration: d.duration, video: a.video, sfxWav, out: path.join(work, `audio_${format}${a.cut ? `_cut${a.cut}` : ""}.wav`), tmpDir: work, ranges });
  log("áudio pronto");

  // 6. vídeo final
  const vf = [];
  const endsAtEnd = ranges[ranges.length - 1][1] >= d.duration - 0.05;
  if (d.fadeOut && endsAtEnd && !a.cut) vf.push(`fade=t=out:st=${(total - 1.5).toFixed(3)}:d=1.5`);
  const r = spawnSync(
    "ffmpeg",
    ["-y", "-v", "error", "-framerate", String(d.fps), "-start_number", "0", "-i", path.join(framesDir, "%06d.jpg"), "-i", audio,
     ...(vf.length ? ["-vf", vf.join(",")] : []),
     "-c:v", "libx264", "-preset", a.preset || "medium", "-crf", String(a.crf || 18), "-pix_fmt", "yuv420p", "-r", String(d.fps),
     "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", a.out],
    { stdio: "inherit" }
  );
  if (r.status !== 0) throw new Error("falha na codificação final");
  log(`pronto: ${a.out}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
