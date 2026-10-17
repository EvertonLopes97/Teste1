#!/usr/bin/env node
"use strict";

/**
 * Edição dinâmica (estilo Reels/YouTube de futebol) a partir do EDIT_PLAN.
 *
 *   node tools/render-dynamic.js EDIT_PLAN.json --video gravacao.mov --out edicao.mp4 \
 *        --fonts ./fonts --face face.json [--work ./tmp] [--workers 4]
 *        [--format horizontal|vertical] [--cut N] [--from s --to s]
 *        [--no-images 1] [--fps 30|60] [--crf 18] [--scale 1.5]
 *
 *   --face     rastreamento do rosto (tools/motion/facetrack.py); centraliza zooms e janelas
 *   --format   horizontal (1920x1080) ou vertical (1080x1920)
 *   --cut N    corte vertical N sugerido no roteiro ("9:16 #N"); implica --format vertical
 *   --fps      quadros por segundo da entrega (padrão: o da gravação). 60 = Full HD 60 para redes
 *              sociais: gráficos e movimentos de câmera a 60 reais
 *   --lances   lances.json (tools/lances.py): vídeo dos lances na tela, com você pequeno no canto
 *   --base     a versão SEM lances já renderizada (mesmos parâmetros): só os trechos com lance são
 *              refeitos e emendados nela (rápido; o áudio é o mesmo)
 *
 * Etapas: fotos de apoio (Openverse, licenças livres) → diretor → quadros da gravação →
 * composição no Chromium (câmera + gráficos) → áudio (voz + SFX) → H.264.
 */

const fs = require("fs");
const path = require("path");
const os = require("os");
const crypto = require("crypto");
const { spawnSync } = require("child_process");
const { direct } = require("./motion/director");
const { ensureFlags } = require("./motion/flags");
const { findImages, creditsText } = require("./motion/media-search");
const { writeSfxTrack } = require("./motion/sfx");
const { renderComposite, extractCamFrames, gerarMascaras } = require("./motion/render-frames");
const { buildAudio } = require("./motion/audio");
const { corDaGravacao } = require("./motion/ffopts");

function args(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith("--")) out[argv[i].slice(2)] = argv[++i];
    else out._.push(argv[i]);
  }
  return out;
}

/** Trechos (timeline) do corte vertical N, a partir dos markers "9:16 #N". */
function cutRanges(plan, n) {
  const ms = (plan.markers || []).filter((m) => new RegExp(`^9:16 #${n}\\b`).test(m.name));
  if (!ms.length) throw new Error(`corte vertical #${n} não existe no plano`);
  return ms.sort((a, b) => a.time - b.time).map((m) => [m.time, m.time + (m.duration || 0)]);
}

async function main() {
  const a = args(process.argv.slice(2));
  if (!a._[0] || !a.video || !a.out || !a.fonts) {
    console.error("uso: render-dynamic.js <EDIT_PLAN.json> --video <gravação> --out <saida.mp4> --fonts <dir> [--face face.json] [--format vertical] [--cut N] [--from s --to s] [--fps 30|60]");
    process.exit(2);
  }
  const t0 = Date.now();
  const log = (m) => console.error(`[${((Date.now() - t0) / 1000).toFixed(0).padStart(5)}s] ${m}`);
  const plan = JSON.parse(fs.readFileSync(a._[0], "utf-8"));
  const work = a.work || fs.mkdtempSync(path.join(os.tmpdir(), "detto-dyn-"));
  fs.mkdirSync(work, { recursive: true });
  const format = a.cut ? "vertical" : a.format || "horizontal";
  const outFps = Number(a.fps || plan.sequence.fps);
  if (![24, 25, 30, 50, 60].includes(outFps)) throw new Error(`--fps ${a.fps}: use 24, 25, 30, 50 ou 60`);
  const face = a.face ? JSON.parse(fs.readFileSync(a.face, "utf-8")) : null;
  if (!face) log("aviso: sem --face, zooms usam o centro da imagem");

  // fotos dos jogadores e escudos (tools/jogadores.py → jogadores.json ao lado do plano)
  const assetsFile = a.assets || path.join(path.dirname(path.resolve(a._[0])), "jogadores.json");
  const assets = fs.existsSync(assetsFile) ? JSON.parse(fs.readFileSync(assetsFile, "utf-8")) : null;

  // 1. fotos de apoio (b-roll) com licença livre
  let images = {};
  if (!a["no-images"] && !(plan.meta && plan.meta.mode === "modos")) {
    const needs = ((plan.meta && plan.meta.segments) || [])
      .filter((s) => s.broll)
      .map((s) => {
        const m = (plan.markers || []).find((x) => /^B-ROLL/.test(x.name) && Math.abs(x.time - s.start) < 0.05);
        return { id: s.id, time: s.start, text: `${m ? m.comment : ""} ${s.block}` };
      });
    images = findImages(needs, { cacheDir: path.join(work, "media"), log });
    fs.writeFileSync(path.join(work, "creditos.txt"), creditsText(images));
    log(`fotos: ${Object.keys(images).length}/${needs.length} trechos com imagem (créditos em ${path.join(work, "creditos.txt")})`);
  }

  // 2. diretor
  const d = direct(plan, { images, assets });
  fs.writeFileSync(path.join(work, "direction.json"), JSON.stringify(d, null, 1));
  log(`diretor: ${JSON.stringify(d.stats)}`);

  // 3. trechos a renderizar
  let ranges = [[0, d.duration]];
  if (a.cut) ranges = cutRanges(plan, a.cut);
  else if (a.from || a.to) ranges = [[Number(a.from || 0), Math.min(d.duration, Number(a.to || d.duration))]];
  const total = ranges.reduce((s, [x, y]) => s + (y - x), 0);
  // corte 9:16: o gancho escrito na tela nos primeiros segundos (o do roteiro; senão o título do corte)
  if (a.cut) {
    const vc = ((plan.meta && plan.meta.vertical_cuts) || []).find((v) => String(v.index) === String(a.cut));
    const gancho = vc && (vc.hook || vc.title);
    if (gancho) d.items.push({ id: "gancho", type: "gancho", start: ranges[0][0], end: ranges[0][0] + 3.0, data: { text: gancho }, z: 45 });
  }
  // vídeo dos lances (versão "com lances")
  const lancesOk = a.lances ? adicionaLances(d, a.lances, work, format, log) : [];
  if (a.lances && !lancesOk.length) log("aviso: nenhum lance com vídeo em " + a.lances);
  // --base: refaz só os trechos com lance e emenda na versão sem lances
  let pecas = null;
  if (a.base) {
    pecas = pecasDosLances(ranges, lancesOk, outFps);
    if (!pecas.length) {
      fs.copyFileSync(a.base, a.out);
      log(`sem lance neste trecho: cópia de ${a.base}`);
      return;
    }
  }
  log(`formato ${format} ${outFps} fps, ${ranges.map(([x, y]) => `${x.toFixed(1)}–${y.toFixed(1)}s`).join(" + ")} (${total.toFixed(1)}s)`);

  const flagsDir = path.join(work, "flags");
  await ensureFlags(d.items.flatMap((i) => [i.data?.a?.flag, i.data?.b?.flag, ...(i.data?.rows || []).flatMap((r) => r.flags || [])]), flagsDir);

  // 4. quadros da gravação (com jump cuts) e composição
  const camDir = path.join(work, "cam");
  const rr = pecas ? pecas.map((x) => x.tl) : ranges; // o que é composto agora
  extractCamFrames(plan, a.video, camDir, d.fps, rr);
  log("quadros da gravação extraídos");
  gerarMascaras(d, camDir, rr, log);
  // quadros já compostos são reaproveitados só se direção, formato e trechos forem os mesmos
  const key = crypto.createHash("sha1").update(JSON.stringify([d, format, pecas ? pecas.map((x) => x.tl) : ranges, a.scale || 1.5, outFps, a["seguir-rosto"] || "0", corDaGravacao(a.video).filtro, plan.cuts.map((c) => [c.start, c.end, c.timeline]), 4])).digest("hex").slice(0, 10);
  const framesDir = path.join(work, `frames_${format}${a.cut ? `_cut${a.cut}` : ""}_${outFps}fps_${key}`);
  // quadros de renders antigos (outro roteiro/teste) ocupam GBs: apaga antes de começar (disco cheio = vídeo cortado)
  for (const velho of fs.existsSync(work) ? fs.readdirSync(work) : []) {
    if (/^frames_/.test(velho) && path.join(work, velho) !== framesDir) fs.rmSync(path.join(work, velho), { recursive: true, force: true });
  }
  const livre = espacoLivreGB(work);
  const precisa = rr.reduce((x, [p, q]) => x + q - p, 0) * 0.012 * (outFps / 30) * (format === "vertical" ? 0.8 : 1) + 1.5;
  if (livre !== null && livre < precisa) {
    log(`AVISO: só ${livre.toFixed(1)} GB livres no disco do job. Este render precisa de ~${precisa.toFixed(1)} GB. Libere espaço se der erro.`);
  }
  const n = await renderComposite({
    plan,
    direction: d,
    camDir,
    outDir: framesDir,
    face,
    seguirRosto: a["seguir-rosto"] === "1",
    fontsDir: a.fonts,
    flagsDir,
    format,
    scale: Number(a.scale || 1.5),
    ranges: pecas ? pecas.map((x) => x.tl) : ranges,
    fps: outFps,
    workers: Number(a.workers || 4),
    onProgress: (done, all) => log(`composição: ${done}/${all} quadros`),
  });
  log(`composição: ${n} quadros`);
  if (pecas) {
    emenda(a.base, framesDir, pecas, outFps, a.out, a, log);
    fs.rmSync(framesDir, { recursive: true, force: true });
    log(`pronto (com lances): ${a.out}`);
    return;
  }

  // 5. áudio
  const sfxWav = writeSfxTrack(d.sfx, d.duration, path.join(work, "sfx.wav"));
  const audio = buildAudio({ plan, duration: d.duration, video: a.video, sfxWav, out: path.join(work, `audio_${format}${a.cut ? `_cut${a.cut}` : ""}.wav`), tmpDir: work, ranges, tratarVoz: a.voz !== "0", sfxGain: a.sfx !== undefined ? Number(a.sfx) : undefined });
  log("áudio pronto");

  // 6. vídeo final
  const vf = [];
  const endsAtEnd = ranges[ranges.length - 1][1] >= d.duration - 0.05;
  if (d.fadeOut && endsAtEnd && !a.cut) vf.push(`fade=t=out:st=${(total - 1.5).toFixed(3)}:d=1.5`);
  // trecho avulso (--to antes do fim): fecha com um fade curto em vez de corte seco
  const af = [];
  if (a.to && !endsAtEnd) {
    vf.push(`fade=t=out:st=${(total - 0.6).toFixed(3)}:d=0.6`);
    af.push(`afade=t=out:st=${(total - 0.6).toFixed(3)}:d=0.6`);
  }
  // H.264 High para redes sociais: keyframe a cada 2 s, bitrate limitado (Full HD 60 ≈ 16 Mb/s)
  const maxrate = outFps > 30 ? "16M" : "10M";
  const r = spawnSync(
    "ffmpeg",
    ["-y", "-v", "error", "-framerate", String(outFps), "-start_number", "0", "-i", path.join(framesDir, "%06d.jpg"), "-i", audio,
     ...(vf.length ? ["-vf", vf.join(",")] : []),
     ...(af.length ? ["-af", af.join(",")] : []),
     "-c:v", "libx264", "-preset", a.preset || "medium", "-crf", String(a.crf || 18), "-maxrate", maxrate, "-bufsize", "32M",
     "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", String(outFps), "-g", String(outFps * 2), "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
     "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", a.out],
    { stdio: "inherit" }
  );
  if (r.status !== 0) throw new Error("falha na codificação final");
  // confere a duração: vídeo mais curto que o plano = quadro faltando (disco cheio) → avisa em vez de "pronto"
  const dur = Number(spawnSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.out], { encoding: "utf-8" }).stdout || 0);
  if (dur && dur < total - 1.5) {
    throw new Error(`o vídeo saiu com ${dur.toFixed(1)} s, mas devia ter ${total.toFixed(1)} s (faltou quadro — disco cheio?). Libere espaço e rode de novo: ele continua de onde parou.`);
  }
  // render terminou certo: os quadros compostos não servem mais (vários GB)
  fs.rmSync(framesDir, { recursive: true, force: true });
  log(`pronto: ${a.out}`);
}

/**
 * Lances (tools/lances.py → lances.json): extrai os quadros de cada lance e põe na direção como
 * placa "lance" (vídeo na tela, câmera pequena no canto). Devolve os lances usados [{t, dur}].
 */
function adicionaLances(d, arquivo, work, format, log) {
  const lj = JSON.parse(fs.readFileSync(arquivo, "utf-8"));
  const usados = [];
  const { TEAMS } = require("./roteiro/componentes");
  const siglaNome = (/** @type {string} */ sg) => ((TEAMS.find((t) => t.sigla === sg) || {}).nome || sg).replace(/-MG$|-PR$|-GO$/i, "");
  (lj.lances || []).forEach((L, k) => {
    // foto do lance (sem vídeo): a foto parada com zoom lento
    if (L.foto && fs.existsSync(L.foto) && L.dur > 0.8) {
      const t0 = Math.max(0, L.t);
      const dur = Math.min(L.dur, d.duration - t0);
      d.items.push({ id: `lance_${k}`, type: "lance", start: t0, end: t0 + dur, layout: "camPip", z: 11, data: { foto: require("url").pathToFileURL(L.foto).href, telaCheia: format !== "vertical", chip: (L.placar || (L.times || []).map(siglaNome).join(" x ") || "").toUpperCase(), jogador: L.jogador || "" } });
      usados.push({ t: t0, dur });
      return;
    }
    if (!L.video || !fs.existsSync(L.video) || !(L.dur > 0.8)) return;
    const t0 = Math.max(0, L.t);
    const dur = Math.min(L.dur, Math.max(0, (L.fim || L.ini + L.dur) - L.ini), d.duration - t0);
    if (dur < 0.8) return;
    const tag = crypto.createHash("sha1").update(`${L.video}|${L.ini}|${dur}`).digest("hex").slice(0, 8);
    const dir = path.join(work, "lances", `${k}_${tag}`);
    const fps = 30;
    const n = Math.round(dur * fps);
    const tem = fs.existsSync(dir) ? fs.readdirSync(dir).filter((f) => f.endsWith(".jpg")).length : 0;
    if (tem < n - 2) {
      fs.rmSync(dir, { recursive: true, force: true });
      fs.mkdirSync(dir, { recursive: true });
      const r = spawnSync("ffmpeg", ["-y", "-v", "error", "-ss", String(L.ini), "-i", L.video, "-t", dur.toFixed(3), "-vf", `fps=${fps},scale=1280:-2`, "-q:v", "3", "-start_number", "0", path.join(dir, "%06d.jpg")], { stdio: "inherit" });
      if (r.status !== 0) {
        log(`aviso: não consegui ler o lance ${k} (${L.video})`);
        return;
      }
    }
    const qtd = fs.readdirSync(dir).filter((f) => f.endsWith(".jpg")).length;
    if (!qtd) return;
    const base = require("url").pathToFileURL(dir).href + "/";
    const chip = (L.placar || (L.times || []).map(siglaNome).join(" x ") || "").toUpperCase();
    d.items.push({ id: `lance_${k}`, type: "lance", start: t0, end: t0 + qtd / fps, layout: "camPip", z: 11, data: { base, n: qtd, fps, telaCheia: format !== "vertical", chip, jogador: L.jogador || "" } });
    usados.push({ t: t0, dur: qtd / fps });
  });
  // durante o lance, nada de carta/etiqueta/texto 3D por cima do vídeo (encerra antes ou some)
  const PRO = ["rastreio", "carta", "texto3d", "congela", "atras", "cards", "stamps", "keyword"];
  d.items = d.items.filter((it) => {
    if (!PRO.includes(it.type) || it.layout) return true;
    for (const u of usados) {
      if (it.start < u.t + u.dur && it.end > u.t) {
        if (it.start < u.t - 0.8) it.end = u.t;
        else return false;
      }
    }
    return true;
  });
  if (usados.length) log(`lances: ${usados.length} com vídeo`);
  return usados;
}

/**
 * Trechos com lance dentro do que é renderizado: tempo na timeline (tl) e quadros na saída (out).
 * A saída é a emenda dos `ranges` na ordem; o quadro f da timeline no range i fica em cum_i + f - início_i.
 */
function pecasDosLances(ranges, lances, fps) {
  const out = [];
  let cum = 0;
  for (const [a, b] of ranges) {
    const fa = Math.round(a * fps);
    const fb = Math.round(b * fps);
    for (const L of lances) {
      const x = Math.max(fa, Math.round(L.t * fps));
      const y = Math.min(fb, Math.round((L.t + L.dur) * fps));
      if (y - x >= 2) out.push({ tl: [x / fps, y / fps], o0: cum + x - fa, n: y - x });
    }
    cum += fb - fa;
  }
  return out.sort((p, q) => p.o0 - q.o0);
}

/** Emenda: a versão sem lances com os quadros novos (trechos com lance) no lugar. Áudio copiado. */
function emenda(base, framesDir, pecas, fps, out, a, log) {
  const patch = path.join(framesDir, "..", "lances_patch.mp4");
  let r = spawnSync("ffmpeg", ["-y", "-v", "error", "-framerate", String(fps), "-start_number", "0", "-i", path.join(framesDir, "%06d.jpg"), "-c:v", "libx264", "-preset", "fast", "-crf", "12", "-pix_fmt", "yuv420p", patch], { stdio: "inherit" });
  if (r.status !== 0) throw new Error("falha ao codificar os lances");
  const partes = [];
  let pos = 0; // quadro da base
  let pp = 0; // quadro do patch
  const f = [];
  for (const p of pecas) {
    if (p.o0 > pos) partes.push(`[0:v]trim=start_frame=${pos}:end_frame=${p.o0},setpts=PTS-STARTPTS[s${partes.length}]`);
    partes.push(`[1:v]trim=start_frame=${pp}:end_frame=${pp + p.n},setpts=PTS-STARTPTS[s${partes.length}]`);
    pos = p.o0 + p.n;
    pp += p.n;
  }
  partes.push(`[0:v]trim=start_frame=${pos},setpts=PTS-STARTPTS[s${partes.length}]`);
  f.push(...partes, `${partes.map((_, i) => `[s${i}]`).join("")}concat=n=${partes.length}:v=1:a=0[v]`);
  const maxrate = fps > 30 ? "16M" : "10M";
  r = spawnSync("ffmpeg", ["-y", "-v", "error", "-i", base, "-i", patch, "-filter_complex", f.join(";"), "-map", "[v]", "-map", "0:a?", "-c:a", "copy",
    "-c:v", "libx264", "-preset", a.preset || "medium", "-crf", String(a.crf || 18), "-maxrate", maxrate, "-bufsize", "32M", "-profile:v", "high", "-pix_fmt", "yuv420p",
    "-r", String(fps), "-g", String(fps * 2), "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-movflags", "+faststart", out], { stdio: "inherit" });
  if (r.status !== 0) throw new Error("falha ao emendar os lances na versão sem lances");
  fs.rmSync(patch, { force: true });
  log(`emenda: ${pecas.length} trecho(s) de lance trocados`);
}

/** GB livres no disco da pasta (Windows: wmic/PowerShell; Linux/mac: df). null se não souber. */
function espacoLivreGB(dir) {
  try {
    if (process.platform === "win32") {
      const drive = path.resolve(dir).slice(0, 2);
      const out = spawnSync("powershell", ["-NoProfile", "-Command", `(Get-PSDrive ${drive[0]}).Free`], { encoding: "utf-8" }).stdout;
      const n = Number(String(out).trim());
      return n ? n / 1e9 : null;
    }
    const out = spawnSync("df", ["-Pk", dir], { encoding: "utf-8" }).stdout.trim().split("\n").pop() || "";
    const kb = Number(out.split(/\s+/)[3]);
    return kb ? kb / 1e6 : null;
  } catch {
    return null;
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
