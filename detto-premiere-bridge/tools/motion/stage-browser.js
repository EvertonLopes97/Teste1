"use strict";

/**
 * Abre o palco de motion graphics no Chromium (Playwright) e captura quadros PNG
 * com fundo transparente.
 */

const fs = require("fs");
const path = require("path");
const { pathToFileURL } = require("url");

function loadPlaywright() {
  const candidates = ["playwright", "/opt/node-tools/node_modules/playwright"];
  for (const c of candidates) {
    try {
      return require(c);
    } catch (_) {
      /* tenta o próximo */
    }
  }
  throw new Error("Playwright não encontrado (npm i -D playwright ou instalação global).");
}

function chromiumPath() {
  const base = process.env.PLAYWRIGHT_BROWSERS_PATH || "/opt/pw-browsers";
  try {
    const dir = fs.readdirSync(base).find((d) => /^chromium-\d+$/.test(d));
    if (dir) {
      const exe = path.join(base, dir, "chrome-linux", "chrome");
      if (fs.existsSync(exe)) return exe;
    }
  } catch (_) {
    /* usa o padrão do Playwright */
  }
  return undefined;
}

/**
 * @param {{fontsDir: string, flagsDir: string, width?: number, height?: number}} opts
 */
async function openStage(opts) {
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({ executablePath: chromiumPath(), args: ["--font-render-hinting=none"] });
  const width = opts.width || 1280;
  const height = opts.height || 720;
  const scale = width / 1280;

  async function newPage() {
    const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: scale });
    await page.goto(pathToFileURL(path.join(__dirname, "stage", "stage.html")).href);
    const anton = path.join(opts.fontsDir, "Anton-Regular.ttf");
    await page.evaluate(
      ({ anton, flagsDir }) => {
        document.getElementById("fonts").textContent = `@font-face { font-family: "Anton"; src: url("${anton}"); }`;
        window.STAGE_ASSETS.flagsDir = flagsDir;
      },
      { anton: pathToFileURL(anton).href, flagsDir: pathToFileURL(opts.flagsDir).href }
    );
    await page.evaluate(() => document.fonts.load('100px "Anton"'));
    return page;
  }

  /**
   * @param {any} page
   * @param {any[]} items
   */
  async function load(page, items) {
    await page.evaluate((list) => window.STAGE.load(list), items);
  }

  /**
   * Desenha o tempo t e captura. Retorna null se nada estiver ativo.
   * @param {any} page @param {number} t @param {string} [file]
   */
  async function frame(page, t, file) {
    const n = await page.evaluate((tt) => window.STAGE.render(tt), t);
    if (!n) return null;
    // aguarda imagens (bandeiras) do quadro atual
    await page.evaluate(() => Promise.all(Array.from(document.images).map((i) => (i.complete ? 1 : new Promise((r) => (i.onload = i.onerror = r))))));
    const buf = await page.screenshot({ omitBackground: true, type: "png", path: file });
    return buf;
  }

  return { browser, newPage, load, frame, close: () => browser.close() };
}

module.exports = { openStage };
