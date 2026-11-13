"use strict";

/**
 * Teste VISUAL: desenha quadros fixos do palco (cards, carta FUT, texto 3D, etiqueta, legenda, placar...) e compara
 * com as imagens aprovadas em test/visual/ref_*.png. Se um gráfico mudar de lugar, sumir ou quebrar, falha
 * ANTES de renderizar um vídeo inteiro.
 *
 *   npm test                       → compara
 *   ATUALIZA_VISUAL=1 npm test     → aprova o visual atual (grava as referências novas)
 *
 * Sem Playwright/Chromium instalado, o teste é pulado.
 */

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const path = require("path");
const { pathToFileURL } = require("url");

const DIR = path.join(__dirname, "visual");
const PONTE = path.join(__dirname, "..");
const LIMITE = 6; // diferença média por canal (0–255) aceita: fonte/antialias de outra máquina

let openStage = null;
try {
  require.resolve("playwright");
  ({ openStage } = require("../tools/motion/stage-browser"));
} catch (_) {
  openStage = null;
}

const face = { cx: 0.525, cy: 0.42, w: 0.16 };
const card = (name, team, sigla, rating) => ({ name, team, sigla, rating, photo: "", crest: "", color: "" });

/** cenas fixas: [nome, formato, tempo, itens] */
const CENAS = [
  ["cards", "horizontal", 1.2, [{ id: "c", type: "cards", start: 0, end: 4, layout: "camPip", z: 10, data: { kicker: "DESTAQUES", cards: [{ ...card("Tiago Volpi", "Bragantino", "RBB", 10), at: 0.2 }, { ...card("Vitor Hugo", "Atlético-MG", "CAM", 8.4), at: 0.5 }], notes: ["GOL DE EMPATE"] } }]],
  ["carta", "horizontal", 1.8, [{ id: "f", type: "carta", start: 0, end: 4, z: 20, data: { overlay: true, cards: [card("Gabigol", "Santos", "SAN", 4.2)], times: [0.05] } }]],
  ["texto3d", "vertical", 1.2, [{ id: "t", type: "texto3d", start: 0, end: 4, z: 20, data: { text: "VERGONHA", cor: "vermelho" } }]],
  ["etiqueta_legenda", "horizontal", 1.0, [
    { id: "r", type: "rastreio", start: 0, end: 4, z: 20, data: { kind: "etiqueta", text: "EU NO DOMINGO", sub: "ASSISTINDO DE CASA" } },
    { id: "l", type: "caption", start: 0, end: 4, z: 15, data: { words: [{ w: "O", s: 0.1, e: 0.3 }, { w: "GABIGOL", s: 0.3, e: 0.8, hl: true }, { w: "CHUTOU", s: 0.8, e: 1.4 }], side: false } },
  ]],
  ["placar_vertical", "vertical", 1.5, [{ id: "p", type: "scoreseq", start: 0, end: 4, layout: "camPip", z: 10, data: { a: "Atlético-MG", b: "Santos", siglaA: "CAM", siglaB: "SAN", steps: [[0, 1], [1, 1], [2, 1]], comp: "BRASILEIRÃO" } }]],
];

test("visual: quadros fixos do palco iguais às referências aprovadas", { skip: !openStage && "sem Playwright" }, async () => {
  const camSrc = pathToFileURL(path.join(DIR, "cam.jpg")).href;
  const atualiza = process.env.ATUALIZA_VISUAL === "1";
  const falhas = [];
  for (const formato of ["horizontal", "vertical"]) {
    const cenas = CENAS.filter((c) => c[1] === formato);
    if (!cenas.length) continue;
    const stage = await openStage({ fontsDir: path.join(PONTE, "fonts"), flagsDir: DIR, format: formato, scale: 1 });
    try {
      const page = await stage.newPage();
      for (const [nome, , t, itens] of cenas) {
        await stage.load(page, [...itens, { id: "wm", type: "watermark", start: 0, end: 9, data: { text: "@detto.galo" }, z: 30 }]);
        const novo = path.join(DIR, `novo_${nome}.png`);
        await page.evaluate(async ({ src, t, face }) => {
          await window.STAGE.setCam(src);
          window.STAGE.render(t, { src, z: 1, c: 0, sx: 0, sy: 0, face, faceT: face });
        }, { src: camSrc, t, face });
        await page.evaluate(() => Promise.all(Array.from(document.images).map((i) => (i.complete ? 1 : new Promise((r) => (i.onload = i.onerror = r))))));
        await page.screenshot({ path: novo, type: "png" });
        const ref = path.join(DIR, `ref_${nome}.png`);
        if (atualiza || !fs.existsSync(ref)) {
          fs.renameSync(novo, ref);
          continue;
        }
        // compara no próprio Chromium (canvas): diferença média e % de pixels muito diferentes
        const r = await page.evaluate(async ({ a, b }) => {
          const carrega = (u) => new Promise((ok, erro) => {
            const i = new Image();
            i.onload = () => ok(i);
            i.onerror = erro;
            i.src = u;
          });
          const [ia, ib] = await Promise.all([carrega(a), carrega(b)]);
          if (ia.width !== ib.width || ia.height !== ib.height) return { media: 999, muito: 1 };
          const px = (img) => {
            const c = document.createElement("canvas");
            c.width = img.width;
            c.height = img.height;
            const x = c.getContext("2d");
            x.drawImage(img, 0, 0);
            return x.getImageData(0, 0, c.width, c.height).data;
          };
          const pa = px(ia);
          const pb = px(ib);
          let soma = 0;
          let muito = 0;
          for (let k = 0; k < pa.length; k += 4) {
            const d = (Math.abs(pa[k] - pb[k]) + Math.abs(pa[k + 1] - pb[k + 1]) + Math.abs(pa[k + 2] - pb[k + 2])) / 3;
            soma += d;
            if (d > 60) muito++;
          }
          const n = pa.length / 4;
          return { media: soma / n, muito: muito / n };
        }, { a: pathToFileURL(novo).href, b: pathToFileURL(ref).href });
        if (r.media > LIMITE || r.muito > 0.03) falhas.push(`${nome}: diferença média ${r.media.toFixed(1)}, ${(r.muito * 100).toFixed(1)}% dos pixels mudaram (veja test/visual/novo_${nome}.png)`);
        else fs.rmSync(novo, { force: true });
      }
    } finally {
      await stage.close();
    }
  }
  assert.deepEqual(falhas, []);
});
