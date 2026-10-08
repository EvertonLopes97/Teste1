"use strict";

/**
 * Abre o palco (câmera + motion graphics) no Chromium via Playwright e captura quadros.
 */

const fs = require("fs");
const path = require("path");
const { pathToFileURL } = require("url");

function loadPlaywright() {
  for (const c of ["playwright", "/opt/node-tools/node_modules/playwright"]) {
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
 * @param {{fontsDir: string, flagsDir: string, format?: "horizontal"|"vertical", scale?: number}} opts
 *   scale: 1.5 → 1920x1080 (horizontal) ou 1080x1920 (vertical) a partir do palco 1280x720/720x1280
 */
async function openStage(opts) {
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({ executablePath: chromiumPath(), args: ["--font-render-hinting=none", "--allow-file-access-from-files"] });
  const format = opts.format || "horizontal";
  const viewport = format === "vertical" ? { width: 720, height: 1280 } : { width: 1280, height: 720 };
  const scale = opts.scale || 1;

  async function newPage() {
    const page = await browser.newPage({ viewport, deviceScaleFactor: scale });
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

  async function load(page, items) {
    await page.evaluate(({ list, format }) => window.STAGE.load(list, { format }), { list: items, format });
  }

  /** Só a camada de gráficos (sem câmera), PNG transparente. */
  async function frame(page, t, file) {
    const n = await page.evaluate((tt) => window.STAGE.render(tt), t);
    if (!n) return null;
    await waitImages(page);
    return page.screenshot({ omitBackground: true, type: "png", path: file });
  }

  /** Quadro final composto: câmera (cam.src = quadro da gravação) + gráficos. */
  async function composite(page, t, cam, file, quality = 92) {
    await page.evaluate(
      async ({ tt, cam }) => {
        await window.STAGE.setCam(cam.src);
        window.STAGE.render(tt, cam);
      },
      { tt: t, cam }
    );
    await waitImages(page);
    return page.screenshot({ type: "jpeg", quality, path: file });
  }

  async function waitImages(page) {
    await page.evaluate(() =>
      Promise.all(Array.from(document.images).map((i) => (i.complete ? 1 : new Promise((r) => (i.onload = i.onerror = r)))))
    );
  }

  return { browser, newPage, load, frame, composite, close: () => browser.close() };
}

module.exports = { openStage };
