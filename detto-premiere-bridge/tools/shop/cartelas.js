#!/usr/bin/env node
"use strict";

/**
 * CARTELAS DOS VÍDEOS DE TIKTOK SHOP — desenha no Chromium as peças de texto (gancho, fala, preço, vantagens,
 * CTA e a cartela final) como PNG com fundo TRANSPARENTE. O vídeo/foto do produto entra por baixo, no FFmpeg.
 *
 *   node tools/shop/cartelas.js <pedido.json>
 *
 * pedido.json: {"largura":1080,"altura":1920,"pecas":[{"saida":"c01.png","texto":"ACHEI O *MELHOR*","preco":"39,90",
 *                "selo":"ESGOTANDO","cta":"LINK NA *VITRINE*"}, {"saida":"fim.png","tipo":"fim","texto":"CORRE"}]}
 *
 * Peças estáticas de propósito: o movimento vem do zoom na foto e dos cortes (um PNG por cena gasta quase nada de
 * disco; a sequência quadro a quadro enchia o disco dele com 1080x1920 em alfa).
 */

const fs = require("fs");
const path = require("path");
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

async function main() {
  const pedidoF = process.argv[2];
  if (!pedidoF) {
    console.error("uso: node tools/shop/cartelas.js <pedido.json>");
    process.exit(2);
  }
  const pedido = JSON.parse(fs.readFileSync(pedidoF, "utf8"));
  const W = pedido.largura || 1080;
  const H = pedido.altura || 1920;
  const pecas = pedido.pecas || [];
  if (!pecas.length) {
    console.log("nada para desenhar");
    return;
  }

  const { chromium } = playwright();
  const navegador = await chromium.launch({ executablePath: chromiumPath(), args: ["--font-render-hinting=none"] });
  const pagina = await navegador.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  await pagina.goto(pathToFileURL(path.join(AQUI, "palco", "shop.html")).href);
  await pagina.addStyleTag({ content: `html,body,#palco{width:${W}px;height:${H}px}` });

  let n = 0;
  for (const p of pecas) {
    await pagina.evaluate((peca) => window.SHOP.monta(peca), p);
    const saida = path.resolve(path.dirname(pedidoF), p.saida);
    fs.mkdirSync(path.dirname(saida), { recursive: true });
    await pagina.screenshot({ path: saida, omitBackground: !p.fundo });
    n += 1;
  }
  await navegador.close();
  console.log(`${n} cartela(s) em ${path.dirname(path.resolve(pedidoF))}`);
}

main().catch((e) => {
  console.error(String((e && e.stack) || e));
  process.exit(1);
});
