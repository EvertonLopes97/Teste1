#!/usr/bin/env node
"use strict";

/**
 * Desenha as 4 thumbs (1280x720) a partir do thumbs.json do thumb.py, no Chromium (mesma fonte Anton do vídeo).
 *   node tools/thumb/thumb.js <pasta>/thumbs.json
 */

const fs = require("fs");
const path = require("path");
const { pathToFileURL } = require("url");

function playwright() {
  for (const c of ["playwright", "/opt/node-tools/node_modules/playwright"]) {
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

const url = (f) => (f ? pathToFileURL(f).href : "");
const esc = (s) => String(s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

/** texto com a palavra de destaque marcada */
function textoHtml(texto, destaque) {
  const ws = String(texto).split(/\s+/).filter(Boolean);
  const alvo = String(destaque || "").toUpperCase();
  let marcou = false;
  return ws
    .map((w) => {
      const hit = !marcou && alvo && w.replace(/[^\p{L}\d]/gu, "") === alvo.replace(/[^\p{L}\d]/gu, "");
      if (hit) marcou = true;
      return hit ? `<span class="hl">${esc(w)}</span>` : esc(w);
    })
    .join(" ");
}

const CSS = (fontes) => `
@font-face { font-family: "Anton"; src: url("${url(path.join(fontes, "Anton-Regular.ttf"))}"); }
@font-face { font-family: "Inter"; font-weight: 800 900; src: url("${url(path.join(fontes, "Inter-ExtraBold.otf"))}"); }
* { box-sizing: border-box; margin: 0; }
body { width: 1280px; height: 720px; overflow: hidden; background: #000; }
.t { position: relative; width: 1280px; height: 720px; overflow: hidden; font-family: Anton, sans-serif; }
.bg { position: absolute; inset: -40px; background-size: cover; background-position: center; filter: blur(14px) brightness(.45) saturate(1.3); }
.bg.ia { inset: 0; filter: brightness(.7) saturate(1.2); }
.luz { position: absolute; width: 900px; height: 900px; border-radius: 50%; filter: blur(30px); }
.vinheta { position: absolute; inset: 0; background: radial-gradient(ellipse at 50% 45%, transparent 45%, rgba(0,0,0,.75) 100%); }
.voce { position: absolute; bottom: 0; filter: drop-shadow(0 0 0 #fff) drop-shadow(6px 0 0 #fff) drop-shadow(-6px 0 0 #fff) drop-shadow(0 6px 0 #fff) drop-shadow(0 -6px 0 #fff) drop-shadow(0 18px 40px rgba(0,0,0,.7)); }
.jog { position: absolute; bottom: 0; filter: drop-shadow(5px 0 0 #fff) drop-shadow(-5px 0 0 #fff) drop-shadow(0 -5px 0 #fff) drop-shadow(0 16px 30px rgba(0,0,0,.7)); }
.txt { position: absolute; color: #fff; line-height: .95; text-transform: uppercase; -webkit-text-stroke: 10px #000; paint-order: stroke fill;
       text-shadow: 0 10px 0 #000, 0 14px 30px rgba(0,0,0,.6); letter-spacing: 1px; }
.txt .hl { color: #FFE600; }
.faixa { position: absolute; left: 0; right: 0; padding: 14px 40px 6px; background: #FFE600; color: #111; text-align: center; transform: rotate(-2deg); }
.faixa .txt2 { font-size: 92px; line-height: 1; }
.seta { position: absolute; }
.circ { position: absolute; border: 10px solid #FF2D2D; border-radius: 50%; box-shadow: 0 0 0 4px #fff, 0 0 30px rgba(255,45,45,.8); }
.selo { position: absolute; font-family: Inter; font-weight: 900; color: #111; background: #B6FF3B; padding: 6px 16px; font-size: 30px; transform: rotate(-4deg); box-shadow: 0 6px 0 #000; }
`;

const SETA = (cor = "#FF2D2D") =>
  `<svg viewBox="0 0 200 120" width="100%" height="100%"><path d="M10 70 C70 70 110 60 150 30" fill="none" stroke="#fff" stroke-width="30" stroke-linecap="round"/><path d="M10 70 C70 70 110 60 150 30" fill="none" stroke="${cor}" stroke-width="18" stroke-linecap="round"/><path d="M128 8 L190 18 L160 72 Z" fill="${cor}" stroke="#fff" stroke-width="8" stroke-linejoin="round"/></svg>`;

/** as 4 versões */
function versoes(s) {
  const c = (i) => s.cortes[i % s.cortes.length];
  const fundo = (i) => (s.fundo ? `<div class="bg ia" style="background-image:url('${url(s.fundo)}')"></div>` : `<div class="bg" style="background-image:url('${url(c(i).quadro)}')"></div>`);
  const jog = s.jogador && s.jogador.foto ? s.jogador : null;
  const T = textoHtml(s.texto, s.destaque);
  const palavras = String(s.texto).split(/\s+/).length;
  return [
    // 1: você à direita, texto gigante à esquerda, jogador embaixo à esquerda com círculo
    `${fundo(0)}<div class="luz" style="right:-200px;top:-100px;background:radial-gradient(circle,rgba(255,59,59,.85),transparent 65%)"></div><div class="vinheta"></div>
     <img class="voce" src="${url(c(0).recorte)}" style="right:-10px;height:${palavras > 3 ? 700 : 740}px">
     ${jog ? `<img class="jog" src="${url(jog.foto)}" style="left:40px;height:330px"><div class="circ" style="left:10px;bottom:20px;width:330px;height:330px"></div>` : ""}
     <div class="txt fit" data-w="700" data-h="${jog ? 330 : 560}" style="left:40px;top:30px;font-size:150px">${T}</div>`,
    // 2: você à esquerda, jogador à direita com seta apontando
    `${fundo(1)}<div class="luz" style="left:-250px;top:-80px;background:radial-gradient(circle,rgba(182,255,59,.75),transparent 65%)"></div><div class="vinheta"></div>
     <img class="voce" src="${url(c(1).recorte)}" style="left:-20px;height:720px">
     ${jog ? `<img class="jog" src="${url(jog.foto)}" style="right:30px;height:470px"><div class="seta" style="left:560px;top:300px;width:230px;height:140px">${SETA()}</div>` : `<div class="seta" style="left:620px;top:330px;width:260px;height:160px;transform:scaleX(-1)">${SETA()}</div>`}
     <div class="txt fit" data-w="${jog ? 640 : 700}" data-h="260" style="right:40px;top:30px;text-align:right;font-size:140px">${T}</div>`,
    // 3: faixa amarela embaixo, você grande no centro, jogador de um lado
    `${fundo(2)}<div class="luz" style="left:190px;top:-150px;background:radial-gradient(circle,rgba(255,230,0,.55),transparent 65%)"></div><div class="vinheta"></div>
     ${jog ? `<img class="jog" src="${url(jog.foto)}" style="left:10px;height:560px;bottom:110px">` : ""}
     <img class="voce" src="${url(c(2).recorte)}" style="left:${jog ? 520 : 330}px;height:700px">
     <div class="faixa" style="bottom:40px"><div class="txt2 fit" data-w="1180" data-h="110">${esc(s.texto)}</div></div>`,
    // 4: só você (reação), texto em cima, duas setas
    `${fundo(3)}<div class="luz" style="left:190px;top:-50px;background:radial-gradient(circle,rgba(255,59,59,.7),transparent 65%)"></div><div class="vinheta"></div>
     <img class="voce" src="${url(c(3).recorte)}" style="left:50%;transform:translateX(-50%);height:640px">
     <div class="seta" style="left:120px;top:330px;width:250px;height:150px;transform:rotate(15deg)">${SETA("#FFE600")}</div>
     <div class="seta" style="right:120px;top:330px;width:250px;height:150px;transform:scaleX(-1) rotate(15deg)">${SETA("#FFE600")}</div>
     ${jog ? `<div class="selo" style="right:40px;bottom:40px">${esc(jog.nome.toUpperCase())}</div>` : ""}
     <div class="txt fit" data-w="1200" data-h="210" style="left:40px;right:40px;top:16px;text-align:center;font-size:150px">${T}</div>`,
  ];
}

async function main() {
  const spec = JSON.parse(fs.readFileSync(process.argv[2], "utf-8"));
  const { chromium } = playwright();
  const browser = await chromium.launch({ executablePath: chromiumPath(), args: ["--allow-file-access-from-files"] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  const saidas = [];
  for (const [i, corpo] of versoes(spec).entries()) {
    // arquivo de verdade (file://): a página em branco não deixa abrir as imagens locais
    const html = path.join(spec.saida, "_thumb.html");
    fs.writeFileSync(html, `<!doctype html><html><head><meta charset="utf-8"><style>${CSS(spec.fontes)}</style></head><body><div class="t">${corpo}</div></body></html>`);
    await page.goto(url(html), { waitUntil: "load" });
    await page.evaluate(() => document.fonts.ready);
    // texto do tamanho que cabe na caixa
    await page.evaluate(() => {
      for (const el of document.querySelectorAll(".fit")) {
        const W = Number(el.dataset.w);
        const H = Number(el.dataset.h);
        el.style.maxWidth = `${W}px`;
        let fs = parseFloat(getComputedStyle(el).fontSize);
        while ((el.scrollWidth > W + 2 || el.offsetHeight > H) && fs > 40) {
          fs -= 4;
          el.style.fontSize = `${fs}px`;
        }
      }
    });
    const f = path.join(spec.saida, `thumb_${i + 1}.jpg`);
    await page.screenshot({ path: f, type: "jpeg", quality: 92 });
    saidas.push(f);
  }
  // as 4 lado a lado para comparar
  await page.setViewportSize({ width: 1280, height: 720 });
  const html = path.join(spec.saida, "_thumb.html");
  fs.writeFileSync(html, `<body style="margin:0;background:#111;display:grid;grid-template-columns:1fr 1fr;gap:6px;width:1280px">${saidas.map((f) => `<img src="${url(f)}" style="width:637px">`).join("")}</body>`);
  await page.goto(url(html), { waitUntil: "load" });
  await page.screenshot({ path: path.join(spec.saida, "thumbs.jpg"), type: "jpeg", quality: 85, fullPage: true });
  await browser.close();
  fs.rmSync(html, { force: true });
  console.log(saidas.join("\n"));
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
