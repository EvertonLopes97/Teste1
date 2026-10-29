#!/usr/bin/env node
"use strict";

/**
 * FOLHA DE CONFERÊNCIA DA ARTE — um quadro de CADA cena, em segundos, sem renderizar o episódio inteiro.
 *
 *   node tools/historias/folha.js <job>/roteiro.json --out <job>/folha.jpg [--cena 7]
 *
 * É o jeito de olhar o desenho (enquadramento, tamanho do assunto, luz) antes de gastar voz e render.
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
  throw new Error("Playwright não encontrado");
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

function arg(nome, padrao) {
  const i = process.argv.indexOf(nome);
  return i > 0 && process.argv[i + 1] ? process.argv[i + 1] : padrao;
}

(async () => {
  const roteiro = JSON.parse(fs.readFileSync(process.argv[2], "utf-8"));
  const saida = arg("--out", path.join(path.dirname(process.argv[2]), "folha.jpg"));
  const so = arg("--cena", "");
  const tmp = path.join(path.dirname(saida), "_folha");
  fs.mkdirSync(tmp, { recursive: true });
  const cenas = (roteiro.cenas || []).filter((_, i) => !so || String(i + 1) === so);

  const { chromium } = playwright();
  const browser = await chromium.launch({ executablePath: chromiumPath(), args: ["--font-render-hinting=none", "--allow-file-access-from-files"] });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  await page.goto(pathToFileURL(path.join(AQUI, "palco", "cena.html")).href);
  const anton = path.join(PONTE, "fonts", "Anton-Regular.ttf");
  const inter = path.join(PONTE, "fonts", "Inter-ExtraBold.otf");
  await page.evaluate(
    ({ a, it, m }) => {
      document.getElementById("fonts").textContent =
        `@font-face{font-family:"Anton";src:url("${a}")}` + (it ? `@font-face{font-family:"Inter";font-weight:800 900;src:url("${it}")}` : "");
      document.getElementById("marca").textContent = m || "";
    },
    { a: pathToFileURL(anton).href, it: fs.existsSync(inter) ? pathToFileURL(inter).href : "", m: roteiro.marca || "" }
  );
  await page.evaluate(() => Promise.all([document.fonts.load('100px "Anton"'), document.fonts.load('800 20px "Inter"').catch(() => null)]));

  const arqs = [];
  for (const [i, c] of cenas.entries()) {
    await page.evaluate((x) => window.CENA.monta(x), c);
    await page.evaluate((x) => window.CENA.anima(0.5, 2.4 + x), i);
    // a legenda real vem da voz; aqui mostramos a 1ª parte da narração só para conferir o lugar dela
    const leg = String(c.narracao || "").split(/\s+/).slice(0, 3).join(" ");
    await page.evaluate((x) => window.CENA.legenda(x), c.escolha ? "" : leg);
    const f = path.join(tmp, `c${String(i + 1).padStart(2, "0")}.jpg`);
    await page.screenshot({ path: f, type: "jpeg", quality: 88 });
    arqs.push(f);
  }
  await browser.close();

  // monta a folha com o FFmpeg (4 colunas)
  const cols = Math.min(4, arqs.length);
  const linhas = Math.ceil(arqs.length / cols);
  const entradas = arqs.flatMap((a) => ["-i", a]);
  const filtro =
    arqs.map((_, i) => `[${i}:v]scale=270:480,drawtext=text='${i + 1}':x=10:y=8:fontsize=34:fontcolor=white:box=1:boxcolor=black@0.7:boxborderw=6[v${i}]`).join(";") +
    ";" + arqs.map((_, i) => `[v${i}]`).join("") + `xstack=inputs=${arqs.length}:layout=${arqs
      .map((_, i) => `${(i % cols) * 276}_${Math.floor(i / cols) * 486}`)
      .join("|")}:fill=black[out]`;
  const g = path.join(tmp, "grafo.txt");
  fs.writeFileSync(g, filtro);
  const r = spawnSync("ffmpeg", ["-v", "error", ...entradas, "-filter_complex_script", g, "-map", "[out]", "-y", saida], { encoding: "utf-8" });
  if (r.status !== 0) {
    process.stdout.write(`(não montei a folha: ${String(r.stderr).slice(-300)}; os quadros estão em ${tmp})\n`);
  } else {
    process.stdout.write(`${arqs.length} cena(s) -> ${saida}\n`);
  }
})();
