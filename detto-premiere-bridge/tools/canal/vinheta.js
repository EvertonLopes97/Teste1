#!/usr/bin/env node
"use strict";

/**
 * VINHETA DE ABERTURA dos vídeos horizontais do YouTube — desenhada por código, com a identidade do canal.
 *
 *   node tools/canal/vinheta.js --canal noticias --nome "DETTO GALO NOTÍCIAS" --out vinheta.mp4
 *   node tools/canal/vinheta.js --canal vlog --nome "EVERTON LOPES" --out vinheta.mp4 [--dur 3 --fps 30]
 *
 * NOTÍCIAS: listras escuras, faixas amarelas entrando, "DG" gigante com zoom, selo PLANTÃO piscando e uma
 * passada de luz — a cara de telejornal do canal (a mesma do banner e da thumb).
 * VLOG/GAMEPLAY: luz lima de um lado e roxa do outro (as duas metades do canal), o nome entrando com um
 * risco lima por baixo.
 *
 * Sai um MP4 com áudio (whoosh + impacto), na resolução e no fps que o vídeo do canal usa.
 */

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");
const { pathToFileURL } = require("url");

const AQUI = __dirname;
const PONTE = path.join(AQUI, "..", "..");

function playwright() {
  for (const c of ["playwright", path.join(PONTE, "node_modules", "playwright"), "/opt/node-tools/node_modules/playwright"]) {
    try {
      return require(c);
    } catch (_) {
      /* próximo */
    }
  }
  throw new Error("Playwright não encontrado (npm install na pasta detto-premiere-bridge)");
}

function chromiumPath() {
  const base = process.env.PLAYWRIGHT_BROWSERS_PATH || "/opt/pw-browsers";
  try {
    const dir = fs.readdirSync(base).find((d) => /^chromium-\d+$/.test(d));
    const exe = dir && path.join(base, dir, "chrome-linux", "chrome");
    if (exe && fs.existsSync(exe)) return exe;
  } catch (_) {
    /* padrão */
  }
  return undefined;
}

const arg = (nome, padrao = "") => {
  const i = process.argv.indexOf(nome);
  return i > 0 && process.argv[i + 1] ? process.argv[i + 1] : padrao;
};

/** o áudio da vinheta: whoosh subindo + impacto no segundo em que o nome trava */
function audio(dur, batida, saida) {
  const g = [
    `anoisesrc=color=brown:duration=${batida.toFixed(2)}:amplitude=0.5[w]`,
    `[w]afade=t=in:st=0:d=${(batida * 0.8).toFixed(2)},highpass=f=300,volume=0.5[wo]`,
    `sine=frequency=70:duration=${(dur - batida).toFixed(2)}[b]`,
    `[b]afade=t=out:st=0.25:d=${Math.max(0.3, dur - batida - 0.25).toFixed(2)},adelay=${Math.round(batida * 1000)}|${Math.round(batida * 1000)},volume=1.2[bo]`,
    `[wo][bo]amix=inputs=2:normalize=0,aformat=channel_layouts=stereo,aresample=48000,loudnorm=I=-16:TP=-1.5[a]`,
  ].join(";");
  const r = spawnSync("ffmpeg", ["-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
    "-filter_complex", g, "-map", "[a]", "-t", String(dur), saida], { encoding: "utf-8" });
  return r.status === 0 && fs.existsSync(saida) ? saida : null;
}

async function main() {
  const canal = arg("--canal", "noticias");
  const nome = arg("--nome", canal === "vlog" ? "EVERTON LOPES" : "DETTO GALO NOTÍCIAS");
  const saida = arg("--out", "vinheta.mp4");
  const dur = Number(arg("--dur", "3"));
  const fps = Number(arg("--fps", "30"));
  const W = Number(arg("--largura", "1920"));
  const H = Number(arg("--altura", "1080"));
  const trabalho = arg("--work", path.join(path.dirname(saida), "tmp_vinheta"));
  const fontes = arg("--fonts", path.join(PONTE, "fonts"));
  fs.mkdirSync(trabalho, { recursive: true });

  const { chromium } = playwright();
  const browser = await chromium.launch({ executablePath: chromiumPath(), args: ["--font-render-hinting=none", "--allow-file-access-from-files"] });
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  await page.goto(pathToFileURL(path.join(AQUI, "vinheta", "vinheta.html")).href);
  const anton = path.join(fontes, "Anton-Regular.ttf");
  const inter = path.join(fontes, "Inter-ExtraBold.otf");
  await page.evaluate(
    ({ a, it }) => {
      document.getElementById("fonts").textContent =
        `@font-face{font-family:"Anton";src:url("${a}")}` + (it ? `@font-face{font-family:"Inter";font-weight:800 900;src:url("${it}")}` : "");
    },
    { a: pathToFileURL(anton).href, it: fs.existsSync(inter) ? pathToFileURL(inter).href : "" }
  );
  await page.evaluate(() => Promise.all([document.fonts.load('100px "Anton"'), document.fonts.load('800 20px "Inter"').catch(() => null)]));
  await page.evaluate(({ c, n, w, h, se, su }) => window.VIN.monta(c, n, w, h, se, su),
    { c: canal, n: nome, w: W, h: H, se: arg("--selo", "@"), su: arg("--sub", "@") });

  const total = Math.ceil(dur * fps);
  for (let q = 0; q < total; q++) {
    await page.evaluate((t) => window.VIN.quadro(t), q / fps / dur);
    await page.screenshot({ path: path.join(trabalho, `v${String(q).padStart(4, "0")}.jpg`), type: "jpeg", quality: 92 });
  }
  await browser.close();

  const som = audio(dur, dur * 0.45, path.join(trabalho, "som.m4a"));
  const cmd = ["-v", "error", "-y", "-framerate", String(fps), "-i", path.join(trabalho, "v%04d.jpg")];
  if (som) cmd.push("-i", som);
  cmd.push("-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", String(fps));
  if (som) cmd.push("-c:a", "aac", "-b:a", "192k", "-shortest");
  cmd.push("-movflags", "+faststart", saida);
  const r = spawnSync("ffmpeg", cmd, { encoding: "utf-8" });
  for (const f of fs.readdirSync(trabalho)) fs.unlinkSync(path.join(trabalho, f));
  fs.rmdirSync(trabalho);
  if (r.status !== 0 || !fs.existsSync(saida)) throw new Error(`ffmpeg: ${(r.stderr || "").slice(-400)}`);
  process.stdout.write(`vinheta: ${saida} (${dur}s, ${W}x${H}, ${fps} fps)\n`);
}

main().catch((e) => {
  console.error(String((e && e.stack) || e));
  process.exit(1);
});
