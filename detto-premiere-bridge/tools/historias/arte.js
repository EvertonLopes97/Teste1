#!/usr/bin/env node
"use strict";

/**
 * CAPAS DOS EPISÓDIOS e ARTE DE PERFIL da série — desenhadas no MESMO palco das cenas, para a grade do perfil ficar
 * com a cara do vídeo (é o que faz o perfil parecer uma série, como o @historiascomkaio).
 *
 *   node tools/historias/arte.js <pedido.json>
 *
 * O pedido.json traz uma lista de peças:
 *   {"pecas":[{"tipo":"capa","saida":"capa.jpg","cena":{...},"numero":3,"titulo":"O BUNKER","serie":"APOCALIPSE ZUMBI",
 *              "emoji":"🧟","grade":"capa_grade.jpg"},
 *             {"tipo":"perfil","saida":"perfil.png","cena":{...},"serie":"APOCALIPSE ZUMBI","sub":"NOVO EP TODO DIA"}]}
 *
 * A capa sai 1080x1920 (capa do reels) com tudo dentro do QUADRADO DO MEIO — que é o pedaço que o Instagram mostra
 * na grade. `grade` salva esse quadrado recortado (1080x1080), para conferir como vai ficar no perfil.
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

/** quebra o título em 2 ou 3 linhas parelhas e marca a ÚLTIMA em amarelo (o jeito das capas que viralizaram) */
function linhasTitulo(txt) {
  const ws = String(txt || "").toUpperCase().trim().split(/\s+/).filter(Boolean);
  if (!ws.length) return "";
  const n = ws.length <= 2 ? ws.length : ws.join("").length > 22 ? 3 : 2;
  const linhas = Array.from({ length: n }, () => []);
  const porLinha = Math.ceil(ws.length / n);
  ws.forEach((w, i) => linhas[Math.min(n - 1, Math.floor(i / porLinha))].push(w));
  return linhas
    .filter((l) => l.length)
    .map((l, i, arr) => (i === arr.length - 1 && arr.length > 1 ? `<em>${l.join(" ")}</em>` : l.join(" ")))
    .join("<br>");
}

/** o nome da série no rodapé: a última palavra sai colorida */
function nomeSerie(txt) {
  const ws = String(txt || "").toUpperCase().trim().split(/\s+/).filter(Boolean);
  if (ws.length < 2) return { b: ws.join(" "), i: "" };
  return { b: ws.slice(0, -1).join(" "), i: ws[ws.length - 1] };
}

async function main() {
  const pedido = JSON.parse(fs.readFileSync(process.argv[2], "utf-8"));
  const pecas = pedido.pecas || [];
  if (!pecas.length) throw new Error("o pedido não tem peças");
  const fontes = pedido.fontes || path.join(PONTE, "fonts");

  const { chromium } = playwright();
  const browser = await chromium.launch({ executablePath: chromiumPath(), args: ["--font-render-hinting=none", "--allow-file-access-from-files"] });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  await page.goto(pathToFileURL(path.join(AQUI, "palco", "arte.html")).href);
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

  for (const p of pecas) {
    const cena = { ...(p.cena || { cenario: "cidade", luz: "noite" }) };
    delete cena.escolha;          // a capa nunca leva a cartela A/B
    delete cena.relogio;
    delete cena.contador;
    delete cena.selo;
    delete cena.onomatopeia;
    await page.evaluate(({ c, tipo }) => {
      window.CENA.monta(c);
      window.CENA.anima(0.45, 1.2);
      window.CENA.legenda("");
      document.getElementById("marca").textContent = "";
      // na capa a ilustração desce: o alto da imagem é do EPISÓDIO / número / título
      const tr = tipo === "perfil" ? "scale(1.12) translateY(-4%)" : "scale(1.26) translateY(9%)";
      for (const id of ["fundo", "atores"]) {
        const el = document.getElementById(id);
        el.style.transformOrigin = "50% 50%";
        el.style.transform = tr;
      }
    }, { c: cena, tipo: p.tipo });
    const serie = nomeSerie(p.serie);
    await page.evaluate(
      ({ tipo, numero, titulo, serie, emoji, sub }) => {
        const arte = document.getElementById("arte");
        arte.className = tipo === "perfil" ? "perfil" : "capa";
        document.querySelector("#capa .num").textContent = numero == null ? "" : String(numero);
        document.querySelector("#capa .tit").innerHTML = titulo || "";
        document.querySelector("#rodape .emoji").textContent = emoji || "";
        document.querySelector("#rodape b").textContent = serie.b || "";
        document.querySelector("#rodape i").textContent = serie.i ? ` ${serie.i}` : "";
        document.querySelector("#perfil .pnome").innerHTML = serie.i ? `${serie.b}<br><em>${serie.i}</em>` : serie.b;
        document.querySelector("#perfil .psub").textContent = sub || "";
      },
      { tipo: p.tipo, numero: p.numero, titulo: linhasTitulo(p.titulo), serie, emoji: p.emoji, sub: p.sub }
    );
    fs.mkdirSync(path.dirname(p.saida), { recursive: true });
    const png = p.saida.toLowerCase().endsWith(".png");
    // a foto de perfil sai quadrada (1080x1080): é assim que o Instagram a recorta
    const quadro = p.tipo === "perfil" ? { clip: { x: 0, y: 420, width: 1080, height: 1080 } } : {};
    await page.screenshot({ path: p.saida, type: png ? "png" : "jpeg", ...(png ? {} : { quality: 92 }), ...quadro });
    // o quadrado do meio: é o que o Instagram mostra na grade do perfil
    if (p.grade) {
      fs.mkdirSync(path.dirname(p.grade), { recursive: true });
      await page.screenshot({ path: p.grade, type: "jpeg", quality: 92, clip: { x: 0, y: 420, width: 1080, height: 1080 } });
    }
    process.stdout.write(`${p.tipo}: ${p.saida}\n`);
  }
  await browser.close();
}

main().catch((e) => {
  console.error(String((e && e.stack) || e));
  process.exit(1);
});
