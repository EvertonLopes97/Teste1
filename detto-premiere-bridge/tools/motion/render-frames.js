"use strict";

/**
 * Renderização final quadro a quadro: cada quadro da gravação (já com os jump cuts)
 * vira a "câmera" do palco, que compõe câmera + gráficos no mesmo quadro. Assim a
 * câmera pode virar janela com moldura, os gráficos podem virar cards e tudo fica
 * sincronizado ao quadro.
 */

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");
const { pathToFileURL } = require("url");
const { openStage } = require("./stage-browser");
const { cameraAt } = require("./director");

/** Extrai os quadros mantidos (timeline) da gravação: cam/000000.jpg … */
function extractCamFrames(plan, video, dir, fps) {
  const total = Math.round(plan.cuts.reduce((m, c) => Math.max(m, c.timeline + (c.end - c.start)), 0) * fps);
  fs.mkdirSync(dir, { recursive: true });
  const have = fs.readdirSync(dir).filter((f) => f.endsWith(".jpg")).length;
  if (have >= total) return total;
  const sel = plan.cuts
    .slice()
    .sort((a, b) => a.timeline - b.timeline)
    .map((c) => `between(n,${Math.round(c.start * fps)},${Math.round(c.end * fps) - 1})`)
    .join("+");
  const script = path.join(dir, "..", "camselect.filter");
  fs.writeFileSync(script, `fps=${fps},select='${sel}',setpts=N/FRAME_RATE/TB`);
  const r = spawnSync("ffmpeg", ["-y", "-v", "error", "-i", video, "-filter_script:v", script, "-an", "-q:v", "2", "-start_number", "0", "-frames:v", String(total), path.join(dir, "%06d.jpg")], { stdio: "inherit" });
  if (r.status !== 0) throw new Error("falha ao extrair quadros da gravação");
  return total;
}

/** Posição do rosto no tempo da timeline (interpola o rastreamento feito na gravação). */
function makeFaceAt(plan, face) {
  const cuts = plan.cuts.slice().sort((a, b) => a.timeline - b.timeline);
  const pts = (face && face.points) || [];
  const step = face && face.fps ? 1 / face.fps : 0.2;
  return (t) => {
    if (!pts.length) return { cx: 0.5, cy: 0.42, w: 0.17 };
    const c = cuts.find((x) => t >= x.timeline && t < x.timeline + (x.end - x.start)) || cuts[cuts.length - 1];
    const src = c.start + (t - c.timeline);
    const i = Math.max(0, Math.min(pts.length - 2, Math.floor(src / step)));
    const a = pts[i];
    const b = pts[i + 1];
    const k = Math.max(0, Math.min(1, (src - a.t) / Math.max(1e-6, b.t - a.t)));
    return { cx: a.cx + (b.cx - a.cx) * k, cy: a.cy + (b.cy - a.cy) * k, w: a.w + (b.w - a.w) * k };
  };
}

/**
 * @param {{plan: any, direction: any, camDir: string, outDir: string, face: any, fontsDir: string,
 *          flagsDir: string, format?: string, scale?: number, ranges: Array<[number, number]>,
 *          fps?: number, workers?: number, quality?: number, onProgress?: (done: number, total: number) => void}} o
 *   fps: quadros por segundo da saída (padrão: o da gravação). Em 60 com gravação a 30, gráficos e
 *        movimentos de câmera saem a 60 reais e cada quadro da gravação é usado duas vezes.
 * @returns {Promise<number>} quadros gravados (outDir/000000.jpg …)
 */
async function renderComposite(o) {
  const d = o.direction;
  const camFps = d.fps; // quadros extraídos da gravação (cam/000000.jpg …)
  const fps = o.fps || camFps;
  const camCount = fs.readdirSync(o.camDir).filter((f) => f.endsWith(".jpg")).length;
  const faceAt = makeFaceAt(o.plan, o.face);
  fs.mkdirSync(o.outDir, { recursive: true });
  /** @type {Array<{out: number, f: number}>} */
  const jobs = [];
  let out = 0;
  for (const [a, b] of o.ranges) {
    for (let f = Math.round(a * fps); f < Math.round(b * fps); f++) jobs.push({ out: out++, f });
  }
  const file = (n) => path.join(o.outDir, `${String(n).padStart(6, "0")}.jpg`);
  const todo = jobs.filter((j) => !fs.existsSync(file(j.out))); // retomável
  const stage = await openStage({ fontsDir: o.fontsDir, flagsDir: o.flagsDir, format: o.format, scale: o.scale || 1.5 });
  let done = jobs.length - todo.length;
  try {
    const workers = Math.max(1, Math.min(o.workers || 4, todo.length || 1));
    const chunk = Math.ceil(todo.length / workers);
    await Promise.all(
      Array.from({ length: workers }, async (_, w) => {
        const mine = todo.slice(w * chunk, (w + 1) * chunk);
        if (!mine.length) return;
        const page = await stage.newPage();
        await stage.load(page, d.items);
        for (const j of mine) {
          const t = j.f / fps;
          const cf = Math.min(camCount - 1, Math.floor(t * camFps + 1e-6));
          const cam = { src: pathToFileURL(path.join(o.camDir, `${String(cf).padStart(6, "0")}.jpg`)).href, ...cameraAt(d, t), face: faceAt(t) };
          await stage.composite(page, t, cam, file(j.out), o.quality || 92);
          done++;
          if (o.onProgress && done % (fps * 20) === 0) o.onProgress(done, jobs.length);
        }
        await page.close();
      })
    );
  } finally {
    await stage.close();
  }
  return jobs.length;
}

module.exports = { renderComposite, extractCamFrames, makeFaceAt };
