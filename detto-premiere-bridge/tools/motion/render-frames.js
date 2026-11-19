"use strict";

/**
 * Renderização final quadro a quadro: cada quadro da gravação (já com os jump cuts)
 * vira a "câmera" do palco, que compõe câmera + gráficos no mesmo quadro. Assim a
 * câmera pode virar janela com moldura, os gráficos podem virar cards e tudo fica
 * sincronizado ao quadro.
 */

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");
const { filtroV, corDaGravacao } = require("./ffopts");
const { pathToFileURL } = require("url");
const { openStage } = require("./stage-browser");
const { cameraAt } = require("./director");

/**
 * Extrai os quadros mantidos (timeline) da gravação: cam/000000.jpg …
 * Com `ranges` (trechos da timeline, ex.: --from/--to ou um corte vertical), só os quadros
 * desses trechos. A cor HDR do iPhone é convertida para SDR (ver corDaGravacao).
 * @param {Array<[number, number]>} [ranges]
 */
/** @param {string} f */
function tamanho(f) {
  try {
    return fs.statSync(f).size;
  } catch {
    return 0;
  }
}

function extractCamFrames(plan, video, dir, fps, ranges) {
  const total = Math.round(plan.cuts.reduce((m, c) => Math.max(m, c.timeline + (c.end - c.start)), 0) * fps);
  // quadros de uma extração com outra cor (ex.: antes da correção do HDR) não servem
  const cor = corDaGravacao(video);
  // os quadros são guardados pela posição na TIMELINE: se os cortes mudaram (silêncio do começo, CORTES NA
  // GRAVAÇÃO, outro roteiro), os antigos são de outro trecho da gravação → vídeo fora de sincronia. Refaz.
  const assinatura = `${cor.filtro}|${fps}|${path.resolve(video)}|${JSON.stringify(plan.cuts.map((c) => [c.start, c.end, c.timeline]))}`;
  const marca = path.join(dir, "cor.txt");
  if (fs.existsSync(dir) && (!fs.existsSync(marca) || fs.readFileSync(marca, "utf-8") !== assinatura)) fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(marca, assinatura);
  const want = (ranges && ranges.length ? ranges : [[0, total / fps]]).map(([a, b]) => [Math.round(a * fps), Math.min(total, Math.round(b * fps))]);
  const name = (n) => path.join(dir, `${String(n).padStart(6, "0")}.jpg`);
  // timeline → quadro da gravação, só onde falta
  /** @type {Array<[number, number]>} */
  const pairs = [];
  for (const c of plan.cuts.slice().sort((a, b) => a.timeline - b.timeline)) {
    const t0 = Math.round(c.timeline * fps);
    const n = Math.round(c.end * fps) - Math.round(c.start * fps);
    for (let k = 0; k < n; k++) {
      const f = t0 + k;
      if (f >= total || !want.some(([a, b]) => f >= a && f < b) || tamanho(name(f)) > 2000) continue;
      pairs.push([f, Math.round(c.start * fps) + k]);
    }
  }
  if (!pairs.length) return total;
  // trechos contínuos da gravação
  /** @type {Array<[number, number]>} */
  const spans = [];
  for (const [, s] of pairs) {
    const l = spans[spans.length - 1];
    if (l && s === l[1] + 1) l[1] = s;
    else spans.push([s, s]);
  }
  if (cor.hdr) console.error(`cor da gravação: HDR (${cor.transfer}, ${cor.primaries}) → convertendo para SDR BT.709`);
  const sel = spans.map(([a, b]) => `between(n,${a},${b})`).join("+");
  const script = path.join(dir, "..", "camselect.filter");
  fs.writeFileSync(script, `fps=${fps},select='${sel}',setpts=N/FRAME_RATE/TB${cor.filtro ? `,${cor.filtro}` : ""}`);
  const tmp = path.join(dir, "_novo");
  fs.rmSync(tmp, { recursive: true, force: true });
  fs.mkdirSync(tmp);
  const r = spawnSync("ffmpeg", ["-y", "-v", "error", "-i", video, ...filtroV(script), "-an", "-q:v", "2", "-start_number", "0", "-frames:v", String(pairs.length), path.join(tmp, "%06d.jpg")], { stdio: "inherit" });
  if (r.status !== 0) throw new Error("falha ao extrair quadros da gravação");
  // os quadros saem na ordem da gravação = ordem da timeline (os cortes não se cruzam)
  pairs.forEach(([f], i) => {
    const src = path.join(tmp, `${String(i).padStart(6, "0")}.jpg`);
    if (fs.existsSync(src)) fs.renameSync(src, name(f));
  });
  fs.rmSync(tmp, { recursive: true, force: true });
  return total;
}

/** trechos congelados (VFX congela): a imagem para no quadro do começo, o áudio segue */
function congelados(d) {
  return (d.items || []).filter((i) => i.type === "congela").map((i) => [i.start, i.end]);
}

/** tempo da gravação mostrado no tempo t da timeline (congela = quadro parado) */
function tempoCam(t, freezes) {
  const fz = freezes.find(([a, b]) => t >= a && t < b);
  return fz ? fz[0] + 0.02 : t;
}

/**
 * Máscaras da pessoa (recorte) só nos quadros com "texto atrás" ou "congela": cam/mask/000123.png.
 * Roda tools/motion/recorte.py (MediaPipe). Sem Python/MediaPipe, segue sem recorte.
 */
function gerarMascaras(d, camDir, ranges, log = console.error) {
  const camFps = d.fps;
  const freezes = congelados(d);
  /** @type {Map<number, boolean>} quadro → precisa de borda (congela) */
  const precisa = new Map();
  for (const it of d.items || []) {
    if (it.type !== "atras" && it.type !== "congela") continue;
    for (const [a, b] of ranges) {
      const x = Math.max(a, it.start);
      const y = Math.min(b, it.end);
      for (let t = x; t < y; t += 1 / camFps) {
        const q = Math.floor(tempoCam(t, freezes) * camFps + 1e-6);
        precisa.set(q, precisa.get(q) || it.type === "congela");
      }
    }
  }
  if (!precisa.size) return;
  const maskDir = path.join(camDir, "mask");
  const nome = (q, s = "") => path.join(maskDir, `${String(q).padStart(6, "0")}${s}.png`);
  const falta = [...precisa].filter(([q, b]) => !fs.existsSync(nome(q)) || (b && !fs.existsSync(nome(q, "_borda"))));
  if (!falta.length) return;
  const lista = path.join(camDir, "..", "recorte.txt");
  fs.writeFileSync(lista, falta.sort((a, b) => a[0] - b[0]).map(([q, b]) => (b ? `${q} c` : String(q))).join("\n"));
  const py = process.env.DETTO_PYTHON || (process.platform === "win32" ? "python" : "python3");
  log(`recorte da pessoa: ${falta.length} quadros (texto atrás / congela)`);
  const r = spawnSync(py, [path.join(__dirname, "recorte.py"), camDir, maskDir, lista], { stdio: "inherit" });
  if (r.status !== 0) log("aviso: recorte falhou; o texto vai acima da cabeça (sem recorte)");
}

/** Posição do rosto no tempo da timeline (interpola o rastreamento feito na gravação). */
function makeFaceAt(plan, face, seguir) {
  if (!seguir && face && face.points && face.points.length) {
    // câmera estática: zoom sempre no mesmo ponto (rosto médio), sem andar de lado
    const med = (k) => face.points.map((p) => p[k]).sort((a, b) => a - b)[Math.floor(face.points.length / 2)];
    const fixo = { cx: med("cx"), cy: med("cy"), w: med("w") };
    return () => fixo;
  }
  const cuts = plan.cuts.slice().sort((a, b) => a.timeline - b.timeline);
  const pts = (face && face.points) || [];
  const step = face && face.fps ? 1 / face.fps : 0.2;
  return (t) => {
    if (!pts.length) return { cx: 0.5, cy: 0.42, w: 0.17 };
    const c = cuts.find((x) => t >= x.timeline && t < x.timeline + (x.end - x.start)) || cuts[cuts.length - 1];
    const src = c.start + (t - c.timeline);
    const i = Math.max(0, Math.min(pts.length - 2, Math.floor(src / step)));
    const a = pts[i];
    const b = pts[i + 1];
    const k = Math.max(0, Math.min(1, (src - a.t) / Math.max(1e-6, b.t - a.t)));
    return { cx: a.cx + (b.cx - a.cx) * k, cy: a.cy + (b.cy - a.cy) * k, w: a.w + (b.w - a.w) * k };
  };
}

/**
 * @param {{plan: any, direction: any, camDir: string, outDir: string, face: any, fontsDir: string,
 *          flagsDir: string, format?: string, scale?: number, ranges: Array<[number, number]>,
 *          fps?: number, workers?: number, quality?: number, onProgress?: (done: number, total: number) => void}} o
 *   fps: quadros por segundo da saída (padrão: o da gravação). Em 60 com gravação a 30, gráficos e
 *        movimentos de câmera saem a 60 reais e cada quadro da gravação é usado duas vezes.
 * @returns {Promise<number>} quadros gravados (outDir/000000.jpg …)
 */
async function renderComposite(o) {
  const d = o.direction;
  const camFps = d.fps; // quadros extraídos da gravação (cam/000000.jpg …)
  const fps = o.fps || camFps;
  const camTotal = Math.round(o.plan.cuts.reduce((m, c) => Math.max(m, c.timeline + (c.end - c.start)), 0) * camFps);
  const faceAt = makeFaceAt(o.plan, o.face, o.seguirRosto);
  // a cabeça DE VERDADE (rastreio, mira, emoji grudado): sempre segue o rosto, mesmo com câmera parada
  const cabecaAt = makeFaceAt(o.plan, o.face, true);
  const freezes = congelados(d);
  const maskDir = path.join(o.camDir, "mask");
  fs.mkdirSync(o.outDir, { recursive: true });
  /** @type {Array<{out: number, f: number}>} */
  const jobs = [];
  let out = 0;
  for (const [a, b] of o.ranges) {
    for (let f = Math.round(a * fps); f < Math.round(b * fps); f++) jobs.push({ out: out++, f });
  }
  const file = (n) => path.join(o.outDir, `${String(n).padStart(6, "0")}.jpg`);
  // retomável; quadro vazio/quebrado (disco cheio, queda no meio) é refeito
  const bom = (/** @type {string} */ f) => {
    try {
      return fs.statSync(f).size > 2000;
    } catch {
      return false;
    }
  };
  const todo = jobs.filter((j) => !bom(file(j.out)));
  const opts = { fontsDir: o.fontsDir, flagsDir: o.flagsDir, format: o.format, scale: o.scale || 1.5 };
  let stage = await openStage(opts);
  let reabrindo = null;
  /** página nova; se o Chromium caiu, abre outro (vídeo longo no Windows às vezes derruba) */
  const novaPagina = async () => {
    for (let k = 0; k < 3; k++) {
      try {
        const page = await stage.newPage();
        await stage.load(page, d.items);
        return page;
      } catch (e) {
        if (!reabrindo) {
          reabrindo = (async () => {
            try {
              await stage.close();
            } catch (_) {
              /* já fechado */
            }
            stage = await openStage(opts);
          })().finally(() => (reabrindo = null));
        }
        await reabrindo;
      }
    }
    throw new Error("o Chromium não abriu de novo");
  };
  const RECICLA = 1500; // página nova a cada N quadros: memória do Chromium não cresce
  let done = jobs.length - todo.length;
  try {
    const workers = Math.max(1, Math.min(o.workers || 4, todo.length || 1));
    const chunk = Math.ceil(todo.length / workers);
    await Promise.all(
      Array.from({ length: workers }, async (_, w) => {
        const mine = todo.slice(w * chunk, (w + 1) * chunk);
        if (!mine.length) return;
        let page = await novaPagina();
        let feitos = 0;
        for (const j of mine) {
          const t = j.f / fps;
          const tc = tempoCam(t, freezes);
          const cf = Math.min(camTotal - 1, Math.floor(tc * camFps + 1e-6));
          const mk = path.join(maskDir, `${String(cf).padStart(6, "0")}.png`);
          const bd = path.join(maskDir, `${String(cf).padStart(6, "0")}_borda.png`);
          const cam = { src: pathToFileURL(path.join(o.camDir, `${String(cf).padStart(6, "0")}.jpg`)).href, ...cameraAt(d, t), face: faceAt(tc), faceT: cabecaAt(tc), mask: fs.existsSync(mk) ? pathToFileURL(mk).href : "", borda: fs.existsSync(bd) ? pathToFileURL(bd).href : "" };
          for (let tent = 0; ; tent++) {
            try {
              if (feitos > 0 && feitos % RECICLA === 0 && tent === 0) throw new Error("reciclar");
              await stage.composite(page, t, cam, file(j.out), o.quality || 92);
              break;
            } catch (e) {
              if (tent >= 3) throw e;
              if (String(e.message) !== "reciclar") console.error(`quadro ${j.out}: ${String(e.message).split("\n")[0]} — tentando de novo`);
              try {
                await page.close();
              } catch (_) {
                /* página já caiu */
              }
              page = await novaPagina();
            }
          }
          feitos++;
          done++;
          if (o.onProgress && done % (fps * 20) === 0) o.onProgress(done, jobs.length);
        }
        await page.close().catch(() => {});
      })
    );
  } finally {
    await stage.close().catch(() => {});
  }
  return jobs.length;
}

module.exports = { renderComposite, extractCamFrames, makeFaceAt, gerarMascaras, congelados, tempoCam };
