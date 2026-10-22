#!/usr/bin/env node
"use strict";

/**
 * Renderiza o vídeo de UM EPISÓDIO de história (9:16, 1080x1920) a partir do roteiro.json.
 *
 *   node tools/historias/render.js <job>/roteiro.json --voz <job>/voz.wav --words <job>/words.json --out <job>/episodio.mp4
 *
 * Cada cena é desenhada por código no Chromium (tools/historias/palco), com movimento lento de câmera, e a legenda
 * vem da transcrição da própria narração (palavra a palavra, como nos virais). Sem imagem gerada por IA: o visual
 * fica IGUAL em todos os episódios da série, que é o que segura o público.
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

/** opção de filtro-em-arquivo conforme a versão do FFmpeg (igual ao tools/ffcompat.py) */
let MAJOR = null;
function filtroComplexo(arq) {
  if (MAJOR === null) {
    const r = spawnSync("ffmpeg", ["-version"], { encoding: "utf-8" });
    const m = /ffmpeg version n?(\d+)/.exec(r.stdout || "");
    MAJOR = m ? Number(m[1]) : 7;
  }
  return MAJOR >= 7 ? ["-/filter_complex", arq] : ["-filter_complex_script", arq];
}

const arg = (nome, padrao = "") => {
  const i = process.argv.indexOf(nome);
  return i > 0 && process.argv[i + 1] ? process.argv[i + 1] : padrao;
};

/** as legendas: 2 a 4 palavras por vez, a partir das palavras com tempo da narração */
function blocosLegenda(words, maxPal = 4, maxSeg = 2.2) {
  const out = [];
  let atual = [];
  for (const w of words) {
    atual.push(w);
    const dur = atual[atual.length - 1].e - atual[0].s;
    const fim = /[.!?,;:]$/.test(w.w);
    if (atual.length >= maxPal || dur >= maxSeg || fim) {
      out.push({ s: atual[0].s, e: atual[atual.length - 1].e, txt: atual.map((x) => x.w).join(" ") });
      atual = [];
    }
  }
  if (atual.length) out.push({ s: atual[0].s, e: atual[atual.length - 1].e, txt: atual.map((x) => x.w).join(" ") });
  return out;
}

/** marca com * a palavra mais "forte" do bloco (número, nome próprio ou a maior) — sai colorida */
function destaca(txt) {
  if (/\*[^*]+\*/.test(txt)) return txt; // o roteiro já escolheu a palavra colorida
  const ws = txt.split(/\s+/);
  let melhor = -1;
  let nota = 0;
  ws.forEach((w, i) => {
    const limpo = w.replace(/[^\wÀ-ÿ]/g, "");
    if (!limpo) return;
    let n = limpo.length;
    if (/\d/.test(limpo)) n += 12; // número: a assinatura do formato (180 litros, 8 km)
    else if (/^[A-ZÀ-Ý]/.test(limpo) && i > 0) n += 6; // nome próprio
    if (n > nota) {
      nota = n;
      melhor = i;
    }
  });
  if (melhor >= 0 && nota >= 7) ws[melhor] = `*${ws[melhor]}*`;
  return ws.join(" ");
}

async function main() {
  const roteiro = JSON.parse(fs.readFileSync(process.argv[2], "utf-8"));
  const vozF = arg("--voz");
  const wordsF = arg("--words");
  const saida = arg("--out", "episodio.mp4");
  const trabalho = arg("--work", path.join(path.dirname(saida), "tmp_render"));
  const fps = Number(arg("--fps", "30"));
  const fontes = arg("--fonts", path.join(PONTE, "fonts"));
  const marca = arg("--marca", roteiro.marca || "");
  fs.mkdirSync(trabalho, { recursive: true });

  const cenas = roteiro.cenas || [];
  if (!cenas.length) throw new Error("o roteiro não tem cenas");
  const words = wordsF && fs.existsSync(wordsF) ? JSON.parse(fs.readFileSync(wordsF, "utf-8")) : [];
  const legendas = words.length ? blocosLegenda(words) : [];

  // duração de cada cena: pelo tempo da narração (campo `ate`) ou dividindo o total
  const durAudio = Number(arg("--duracao", "0")) || (words.length ? words[words.length - 1].e + 0.6 : cenas.length * 5);
  let t0 = 0;
  for (const [i, c] of cenas.entries()) {
    c._ini = t0;
    const ate = Number(c.ate || 0);
    c._fim = ate > t0 ? ate : (i === cenas.length - 1 ? durAudio : t0 + durAudio / cenas.length);
    if (c._fim <= c._ini + 0.3) c._fim = c._ini + 0.9;
    t0 = c._fim;
  }
  cenas[cenas.length - 1]._fim = Math.max(cenas[cenas.length - 1]._fim, durAudio);

  const { chromium } = playwright();
  const browser = await chromium.launch({ executablePath: chromiumPath(), args: ["--font-render-hinting=none", "--allow-file-access-from-files"] });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  await page.goto(pathToFileURL(path.join(AQUI, "palco", "cena.html")).href);
  const anton = path.join(fontes, "Anton-Regular.ttf");
  const inter = path.join(fontes, "Inter-ExtraBold.otf");
  await page.evaluate(
    ({ a, it, m }) => {
      document.getElementById("fonts").textContent =
        `@font-face{font-family:"Anton";src:url("${a}")}` + (it ? `@font-face{font-family:"Inter";font-weight:800 900;src:url("${it}")}` : "");
      document.getElementById("marca").textContent = m || "";
    },
    { a: pathToFileURL(anton).href, it: fs.existsSync(inter) ? pathToFileURL(inter).href : "", m: marca }
  );
  await page.evaluate(() => Promise.all([document.fonts.load('100px "Anton"'), document.fonts.load('800 20px "Inter"').catch(() => null)]));

  const total = Math.ceil(cenas[cenas.length - 1]._fim * fps);
  let n = 0;
  let cenaAtual = -1;
  let legAtual = null;
  process.stdout.write(`render: ${cenas.length} cenas, ${(total / fps).toFixed(1)}s, ${total} quadros\n`);
  for (let q = 0; q < total; q++) {
    const t = q / fps;
    const idx = Math.max(0, cenas.findIndex((c) => t < c._fim));
    if (idx !== cenaAtual) {
      cenaAtual = idx;
      await page.evaluate((c) => window.CENA.monta(c), cenas[idx]);
      legAtual = null;
    }
    const c = cenas[idx];
    await page.evaluate((p) => window.CENA.anima(p), (t - c._ini) / Math.max(0.3, c._fim - c._ini));
    const bloco = legendas.find((b) => t >= b.s - 0.05 && t <= b.e + 0.12);
    const txt = bloco ? bloco.txt : c.legenda_fixa || "";
    if (txt !== legAtual) {
      legAtual = txt;
      await page.evaluate((x) => window.CENA.legenda(x), txt ? destaca(txt) : "");
    }
    await page.screenshot({ path: path.join(trabalho, `q${String(q).padStart(6, "0")}.jpg`), type: "jpeg", quality: 90 });
    n++;
    if (n % (fps * 10) === 0) process.stdout.write(`   ${(n / fps).toFixed(0)}s de ${(total / fps).toFixed(0)}s\n`);
  }
  await browser.close();

  // junta os quadros + a narração
  const temVoz = vozF && fs.existsSync(vozF);
  const cmd = ["-v", "error", "-y", "-framerate", String(fps), "-i", path.join(trabalho, "q%06d.jpg")];
  if (temVoz) cmd.push("-i", vozF);
  const grafo = temVoz
    ? "[0:v]format=yuv420p[v];[1:a]aresample=48000,loudnorm=I=-14:TP=-1.5[a]"
    : "[0:v]format=yuv420p[v]";
  const gArq = path.join(trabalho, "grafo.txt");
  fs.writeFileSync(gArq, grafo);
  cmd.push(...filtroComplexo(gArq), "-map", "[v]");
  if (temVoz) cmd.push("-map", "[a]", "-c:a", "aac", "-b:a", "192k", "-shortest");
  cmd.push("-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-movflags", "+faststart", saida);
  const r = spawnSync("ffmpeg", cmd, { encoding: "utf-8" });
  if (r.status !== 0) throw new Error(`ffmpeg: ${(r.stderr || "").slice(-500)}`);
  for (const f of fs.readdirSync(trabalho)) if (/^q\d+\.jpg$/.test(f)) fs.unlinkSync(path.join(trabalho, f));
  process.stdout.write(`pronto: ${saida}\n`);
}

main().catch((e) => {
  console.error(String((e && e.stack) || e));
  process.exit(1);
});
