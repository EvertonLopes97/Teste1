"use strict";

/**
 * Renderiza a camada de motion graphics (PNG com alfa por quadro) e gera uma lista
 * ffconcat com os quadros vazios agrupados — o ffmpeg lê tudo como um único vídeo.
 */

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");
const { openStage } = require("./stage-browser");

/**
 * @param {{items: any[], duration: number, fps: number, outDir: string, fontsDir: string,
 *          flagsDir: string, workers?: number, onProgress?: (done: number, total: number) => void}} opts
 * @returns {Promise<{list: string, video: string, activeFrames: number, totalFrames: number}>}
 */
async function renderLayer(opts) {
  const { items, duration, fps, outDir } = opts;
  fs.mkdirSync(outDir, { recursive: true });
  const total = Math.round(duration * fps);

  // quadros com algum item ativo (mesma regra do palco: start <= t < end)
  const active = new Uint8Array(total);
  for (const it of items) {
    const a = Math.max(0, Math.ceil(it.start * fps - 1e-6));
    const b = Math.min(total, Math.ceil(it.end * fps - 1e-6));
    for (let f = a; f < b; f++) active[f] = 1;
  }
  const frames = [];
  for (let f = 0; f < total; f++) if (active[f]) frames.push(f);

  const blank = path.join(outDir, "blank.png");
  spawnSync("ffmpeg", ["-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black@0.0:s=1280x720,format=rgba", "-frames:v", "1", blank]);

  const name = (f) => path.join(outDir, `f_${String(f).padStart(6, "0")}.png`);
  const todo = frames.filter((f) => !fs.existsSync(name(f))); // retomável
  const workers = Math.max(1, Math.min(opts.workers || 3, todo.length || 1));
  const stage = await openStage({ fontsDir: opts.fontsDir, flagsDir: opts.flagsDir });
  let done = frames.length - todo.length;
  try {
    const chunk = Math.ceil(todo.length / workers);
    await Promise.all(
      Array.from({ length: workers }, async (_, w) => {
        const mine = todo.slice(w * chunk, (w + 1) * chunk);
        if (!mine.length) return;
        const page = await stage.newPage();
        await stage.load(page, items);
        for (const f of mine) {
          const buf = await stage.frame(page, f / fps, name(f));
          if (!buf) fs.copyFileSync(blank, name(f));
          done++;
          if (opts.onProgress && done % 300 === 0) opts.onProgress(done, frames.length);
        }
        await page.close();
      })
    );
  } finally {
    await stage.close();
  }

  // ffconcat: quadros ativos um a um; trechos vazios viram uma entrada com duração
  const lines = ["ffconcat version 1.0"];
  const d = 1 / fps;
  let f = 0;
  while (f < total) {
    if (active[f]) {
      lines.push(`file '${name(f)}'`, `duration ${d.toFixed(6)}`);
      f++;
    } else {
      let g = f;
      while (g < total && !active[g]) g++;
      lines.push(`file '${blank}'`, `duration ${((g - f) * d).toFixed(6)}`);
      f = g;
    }
  }
  lines.push(`file '${blank}'`); // a última entrada precisa se repetir sem duração
  const list = path.join(outDir, "layer.ffconcat");
  fs.writeFileSync(list, lines.join("\n") + "\n");

  // O Chromium grava quadros opacos como rgb24 e os demais como rgba; ler a lista
  // direto na composição faria o ffmpeg reconstruir o grafo a cada troca (zerando
  // contadores de quadro/amostra). Consolida antes em um vídeo rgba de formato fixo.
  const video = path.join(outDir, "layer.mkv");
  const r = spawnSync(
    "ffmpeg",
    ["-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", list,
     "-vf", `fps=${fps},format=rgba`, "-frames:v", String(total), "-c:v", "ffv1", "-pix_fmt", "bgra", video],
    { stdio: "inherit" }
  );
  if (r.status !== 0) throw new Error("falha ao consolidar a camada de gráficos");
  return { list, video, activeFrames: frames.length, totalFrames: total };
}

module.exports = { renderLayer };
