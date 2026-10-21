#!/usr/bin/env node
"use strict";

/**
 * Desenha as thumbs virais (1280x720) do viral.py no Chromium: você + quadro do vídeo + assunto.
 *   node tools/thumb/viral.js <pasta>/thumbs.json
 * 3 versões: TV (quadro numa "tela" inclinada, seta), CHEIA (quadro de fundo, texto do lado), DIVIDIDA (quadro | você, faixa).
 */

const fs = require("fs");
const path = require("path");
const { pathToFileURL } = require("url");

function playwright() {
  for (const c of ["playwright", path.join(__dirname, "..", "..", "node_modules", "playwright"), "/opt/node-tools/node_modules/playwright"]) {
    try {
      return require(c);
    } catch (_) {
      /* próximo */
    }
  }
  throw new Error("Playwright não encontrado (rode npm install na pasta detto-premiere-bridge)");
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

function textoHtml(texto, destaque) {
  const ws = String(texto).split(/\s+/).filter(Boolean);
  const alvo = String(destaque || "").toUpperCase().replace(/[^\p{L}\d]/gu, "");
  let marcou = false;
  return ws
    .map((w) => {
      const hit = !marcou && alvo && w.replace(/[^\p{L}\d]/gu, "") === alvo;
      if (hit) marcou = true;
      return hit ? `<span class="hl">${esc(w)}</span>` : esc(w);
    })
    .join(" ");
}

const CSS = (s) => `
@font-face { font-family: "Anton"; src: url("${url(path.join(s.fontes, "Anton-Regular.ttf"))}"); }
@font-face { font-family: "Inter"; font-weight: 800 900; src: url("${url(path.join(s.fontes, "Inter-ExtraBold.otf"))}"); }
* { box-sizing: border-box; margin: 0; }
body { width: 1280px; height: 720px; overflow: hidden; background: #000; }
.t { position: relative; width: 1280px; height: 720px; overflow: hidden; font-family: Anton, sans-serif; }
.bg { position: absolute; inset: -40px; background-size: cover; background-position: center; }
.borrado { filter: blur(16px) brightness(.42) saturate(1.35); }
.nitido { inset: 0; filter: brightness(.85) saturate(1.25) contrast(1.08); }
.luz { position: absolute; width: 900px; height: 900px; border-radius: 50%; filter: blur(30px); }
.vinheta { position: absolute; inset: 0; background: radial-gradient(ellipse at 50% 45%, transparent 45%, rgba(0,0,0,.7) 100%); }
.voce { position: absolute; bottom: 0; filter: drop-shadow(6px 0 0 #fff) drop-shadow(-6px 0 0 #fff) drop-shadow(0 -6px 0 #fff) drop-shadow(0 6px 0 #fff) drop-shadow(0 18px 40px rgba(0,0,0,.75)); }
.voce.caixa { border: 10px solid #fff; border-radius: 26px; box-shadow: 0 18px 50px rgba(0,0,0,.8); object-fit: cover; }
.tela { position: absolute; background-size: cover; background-position: center; border: 10px solid #fff; border-radius: 18px;
        box-shadow: 0 24px 60px rgba(0,0,0,.85), 0 0 0 4px rgba(0,0,0,.6); }
.txt { position: absolute; color: #fff; line-height: .95; text-transform: uppercase; -webkit-text-stroke: 11px #000; paint-order: stroke fill;
       text-shadow: 0 10px 0 #000, 0 14px 30px rgba(0,0,0,.6); letter-spacing: 1px; }
.txt .hl { color: ${s.cor}; }
.faixa { position: absolute; left: -20px; right: -20px; padding: 14px 50px 8px; background: ${s.cor}; color: #111; text-align: center; transform: rotate(-2deg); box-shadow: 0 10px 0 #000; }
.faixa .t2 { font-size: 100px; line-height: 1; }
.selo { position: absolute; font-family: Anton; color: #fff; background: ${s.selo_cor}; padding: 6px 22px 4px; font-size: 54px; transform: rotate(-4deg); box-shadow: 0 7px 0 #000; letter-spacing: 1px; }
.extra { position: absolute; border-radius: 50%; background: #111 center/cover; border: 8px solid #fff; box-shadow: 0 12px 30px rgba(0,0,0,.7); }
.marca { position: absolute; font-family: Inter; font-weight: 900; font-size: 22px; color: #fff; background: rgba(0,0,0,.72); padding: 6px 14px; border-radius: 8px; letter-spacing: 1px; }
.seta { position: absolute; }
`;

const SETA = (cor) =>
  `<svg viewBox="0 0 200 120" width="100%" height="100%"><path d="M10 70 C70 70 110 60 150 30" fill="none" stroke="#fff" stroke-width="30" stroke-linecap="round"/><path d="M10 70 C70 70 110 60 150 30" fill="none" stroke="${cor}" stroke-width="18" stroke-linecap="round"/><path d="M128 8 L190 18 L160 72 Z" fill="${cor}" stroke="#fff" stroke-width="8" stroke-linejoin="round"/></svg>`;

function voceHtml(v, lado, altura, extra = "") {
  if (!v) return "";
  if (v.recortado) return `<img class="voce" src="${url(v.png)}" style="${lado};height:${altura}px;${extra}">`;
  const h = Math.round(altura * 0.74);
  return `<img class="voce caixa" src="${url(v.png)}" style="${lado};bottom:40px;width:${h}px;height:${h}px;${extra}">`;
}

function versoes(s) {
  const q = (i) => s.quadros[i % s.quadros.length];
  const v = (i) => (s.voces.length ? s.voces[i % s.voces.length] : null);
  const T = textoHtml(s.texto, s.destaque);
  const selo = (estilo) => (s.selo ? `<div class="selo" style="${estilo}">${esc(s.selo)}</div>` : "");
  const extra = (i, estilo) => (s.extras[i] ? `<div class="extra" style="${estilo};background-image:url('${url(s.extras[i])}')"></div>` : "");
  const marca = s.marca ? `<div class="marca" style="left:24px;bottom:22px">${esc(s.marca)}</div>` : "";
  const setaCor = s.estilo === "noticia" ? "#FF2D2D" : s.cor;
  return [
    // 1 TV: o quadro numa tela inclinada à esquerda, você à direita, seta apontando a tela
    `<div class="bg borrado" style="background-image:url('${url(q(0))}')"></div>
     <div class="luz" style="right:-260px;top:-160px;background:radial-gradient(circle,${s.luz},transparent 65%)"></div><div class="vinheta"></div>
     <div class="tela" style="left:34px;top:226px;width:720px;height:405px;transform:rotate(-3deg);background-image:url('${url(q(0))}')"></div>
     ${selo("left:20px;top:200px")}
     ${extra(0, "left:600px;top:500px;width:190px;height:190px")}
     ${voceHtml(v(0), "right:-30px", 720)}
     <div class="seta" style="left:700px;top:420px;width:200px;height:120px;transform:scaleX(-1) rotate(-8deg)">${SETA(setaCor)}</div>
     <div class="txt fit" data-w="820" data-h="200" style="left:36px;top:14px;font-size:130px">${T}</div>
     ${marca}`,
    // 2 CHEIA: o quadro de fundo (nítido), escurecido à esquerda, texto gigante à esquerda, você à direita
    `<div class="bg nitido" style="background-image:url('${url(q(1))}')"></div>
     <div style="position:absolute;inset:0;background:linear-gradient(90deg,rgba(0,0,0,.88) 0%,rgba(0,0,0,.55) 45%,rgba(0,0,0,0) 75%)"></div>
     <div class="luz" style="right:-300px;top:-200px;background:radial-gradient(circle,${s.luz},transparent 65%)"></div>
     ${voceHtml(v(1), "right:-20px", 700)}
     ${extra(0, "left:540px;bottom:30px;width:170px;height:170px")}
     ${selo("left:36px;top:34px")}
     <div class="txt fit" data-w="680" data-h="${s.selo ? 470 : 560}" style="left:36px;top:${s.selo ? 130 : 50}px;font-size:170px">${T}</div>
     ${marca}`,
    // 3 DIVIDIDA: quadro à esquerda (corte diagonal), você à direita, faixa com o texto embaixo
    `<div class="bg borrado" style="background-image:url('${url(q(2))}')"></div>
     <div class="luz" style="right:-200px;top:-150px;background:radial-gradient(circle,${s.luz},transparent 65%)"></div>
     <div style="position:absolute;left:0;top:0;width:760px;height:720px;background:url('${url(q(2))}') center/cover;clip-path:polygon(0 0,100% 0,80% 100%,0 100%);filter:saturate(1.25) contrast(1.06)"></div>
     <div style="position:absolute;left:0;top:0;width:760px;height:720px;clip-path:polygon(100% 0,101.5% 0,81.5% 100%,80% 100%);background:#fff"></div>
     ${voceHtml(v(2), "right:10px", 680, "bottom:90px")}
     ${extra(1, "left:30px;bottom:170px;width:170px;height:170px") || extra(0, "left:30px;bottom:170px;width:170px;height:170px")}
     ${selo("left:30px;top:34px")}
     <div class="faixa" style="bottom:34px"><div class="t2 txt2 fit" data-w="1180" data-h="112">${esc(s.texto)}</div></div>`,
  ].slice(0, Math.max(1, s.n || 3));
}

async function main() {
  const spec = JSON.parse(fs.readFileSync(process.argv[2], "utf-8"));
  const { chromium } = playwright();
  const browser = await chromium.launch({ executablePath: chromiumPath(), args: ["--allow-file-access-from-files"] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  const html = path.join(spec.saida, "_thumb.html");
  const saidas = [];
  for (const [i, corpo] of versoes(spec).entries()) {
    fs.writeFileSync(html, `<!doctype html><html><head><meta charset="utf-8"><style>${CSS(spec)}</style></head><body><div class="t">${corpo}</div></body></html>`);
    await page.goto(url(html), { waitUntil: "load" });
    await page.evaluate(() => document.fonts.ready);
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
    await page.screenshot({ path: f, type: "jpeg", quality: 90 });
    saidas.push(f);
  }
  fs.writeFileSync(html, `<body style="margin:0;background:#111;display:grid;grid-template-columns:1fr 1fr;gap:6px;width:1280px">${saidas.map((f) => `<img src="${url(f)}" style="width:637px">`).join("")}</body>`);
  await page.goto(url(html), { waitUntil: "load" });
  await page.screenshot({ path: path.join(spec.saida, "thumbs.jpg"), type: "jpeg", quality: 85, fullPage: true });
  await browser.close();
  fs.rmSync(html, { force: true });
  console.log(saidas.join("\n"));
}

main().catch((e) => {
  console.error(String((e && e.stack) || e));
  process.exit(1);
});
