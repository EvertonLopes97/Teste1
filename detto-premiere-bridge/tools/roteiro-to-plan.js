#!/usr/bin/env node
"use strict";

/**
 * Converte um roteiro de edição (.txt no formato DETTO) em EDIT_PLAN.json.
 *
 *   node tools/roteiro-to-plan.js roteiro.txt --media "C:/videos/gravacao.mov" \
 *        [--fps 30] [--width 1920] [--height 1080] [--duration 523.4] [--job job-001] [--out EDIT_PLAN.json]
 *        [--words words.json [--gap 0.8] [--no-jumpcuts 1] [--srt legendas.srt]]
 *
 * --words: transcrição com tempo por palavra ([{w, s, e}], ex.: Whisper). Com ela, cada
 * trecho do roteiro é alinhado à fala real, as deixas ("saiu chorando") viram tempos
 * exatos e as pausas maiores que --gap segundos são removidas (jump cuts).
 */

const fs = require("fs");
const { parseRoteiro } = require("./roteiro/parse");
const { buildPlan } = require("./roteiro/build");
const { alignRoteiro, makeMapper } = require("./roteiro/align");

/** a ERRATA do roteiro também vale para a fala usada nos comandos ("marcelo anjel" → MARCELO RANGEL) */
function comErrata(/** @type {string} */ txt, /** @type {Array<{heard: string, correct: string}>} */ errata) {
  const sem = (/** @type {string} */ x) => x.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  let out = txt;
  for (const e of [...errata].sort((a, b) => b.heard.length - a.heard.length)) {
    const alvo = sem(e.heard).toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    if (!alvo.trim()) continue;
    const re = new RegExp(`(^|[^\\p{L}])${alvo}(?=$|[^\\p{L}])`, "giu");
    const base = sem(out);
    let res = "", last = 0;
    for (const m of base.matchAll(re)) {
      const ini = (m.index || 0) + m[1].length;
      res += out.slice(last, ini) + e.correct.toLowerCase().replace(/(^|\s)(\p{L})(\p{L}*)/gu, (c, sp, l, r) => (/^(d[aoe]s?|e)$/.test(l + r) ? c : sp + l.toUpperCase() + r));
      last = ini + m[0].length - m[1].length;
    }
    out = res + out.slice(last);
  }
  return out;
}
const { buildCaptions, toSrt, spokenBySegment } = require("./roteiro/captions");
const { analyzePlan, formatPreview } = require("../plugin/src/core/analyze");

function args(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith("--")) out[argv[i].slice(2)] = argv[++i];
    else out._.push(argv[i]);
  }
  return out;
}

async function main() {
  const a = args(process.argv.slice(2));
  if (!a._[0] || !a.media) {
    console.error("uso: roteiro-to-plan.js <roteiro.txt> --media <arquivo> [--fps 30] [--width 1920] [--height 1080] [--duration s] [--job id] [--out plano.json]");
    process.exit(2);
  }
  // roteiro salvo no Bloco de Notas antigo (ANSI/Windows-1252) também vale
  const buf = fs.readFileSync(a._[0]);
  let txt = buf.toString("utf-8");
  if (txt.includes("\uFFFD")) txt = buf.toString("latin1");
  let roteiro = parseRoteiro(txt);
  if (!roteiro.segments.length) {
    // roteiro sem a linha de BLOCO (colado no painel, escrito à mão): os trechos [0:00 – 0:08] viram um bloco só
    const i = txt.search(/^\s*\[\s*\d{1,2}:\d{2}/m);
    if (i >= 0) roteiro = parseRoteiro(txt.slice(0, i) + "\n=====\n BLOCO 1\n=====\n" + txt.slice(i));
  }
  if (!roteiro.segments.length) {
    console.error("O roteiro não tem nenhum trecho com tempo ([0:00 – 0:08] + FALA:). Confira o formato no exemplo do CLAUDE.md.");
    process.exit(1);
  }
  let keep;
  let words = null;
  if (a.words) {
    if (!a.duration) throw new Error("--words exige --duration (duração real da mídia em segundos)");
    words = JSON.parse(fs.readFileSync(a.words, "utf-8"));
    // CORTES NA GRAVAÇÃO (repetições, erros): as palavras desses trechos saem da fala, da legenda e do vídeo
    const cortes = roteiro.cortes || [];
    if (cortes.length) {
      const antes = words.length;
      words = words.filter((w) => !cortes.some((c) => (w.s + w.e) / 2 >= c.start && (w.s + w.e) / 2 <= c.end));
      console.log(`cortes na gravação: ${cortes.length} trechos, ${antes - words.length} palavras fora`);
    }
    const aligned = alignRoteiro(roteiro, words, {
      mediaDuration: Number(a.duration),
      gap: a.gap ? Number(a.gap) : undefined,
    });
    roteiro = aligned.roteiro;
    // o que foi FALADO em cada trecho: os comandos de edição seguem a fala, não o texto escrito
    const sp = spokenBySegment(roteiro, words);
    const { alignWords } = require("./roteiro/captions");
    roteiro.segments.forEach((s, i) => {
      const x = /** @type {any} */ (s);
      if (sp[i].text.split(" ").length >= 3) x.spoken = comErrata(sp[i].text, roteiro.errata || []);
      x.parecido = sp[i].parecido;
      // tempo de cada palavra do ROTEIRO (as não faladas ficam no lugar "mais ou menos" entre as vizinhas)
      const display = (s.fields.FALA || "").replace(/"/g, "").split(/\s+/).filter(Boolean);
      const heard = words.filter((w) => w.s >= s.start - 0.05 && w.s < s.end);
      if (display.length && heard.length) x.palavras = alignWords(display, heard).map((t, k) => (t ? { w: display[k], t: t.s } : null)).filter(Boolean);
    });
    if (!a["no-jumpcuts"]) keep = aligned.keep;
    // garante que nada dos cortes fique (o respiro de 0,12 s das palavras vizinhas)
    if (keep && (roteiro.cortes || []).length) {
      for (const c of roteiro.cortes) {
        keep = keep.flatMap((k) => (k.end <= c.start || k.start >= c.end ? [k] : [{ start: k.start, end: c.start }, { start: c.end, end: k.end }].filter((x) => x.end - x.start > 0.05)));
      }
    }
    console.error(`alinhamento: ${aligned.report.matched} trechos encontrados na fala, ${aligned.report.estimated} estimados`);
    const mmss = (/** @type {number} */ t) => `${Math.floor(t / 60)}:${String(Math.round(t % 60)).padStart(2, "0")}`;
    const est = aligned.report.details.filter((d) => d.at === null).map((d) => mmss(d.tc));
    if (est.length) console.error(`  (estimados = sem fala casada; vinheta sem FALA é normal): ${est.join(", ")}`);
    if (a.report) fs.writeFileSync(a.report, JSON.stringify(aligned.report, null, 2));
  }
  const plan = buildPlan(roteiro, {
    keep,
    mediaPath: a.media,
    fps: Number(a.fps || 30),
    width: Number(a.width || 1920),
    height: Number(a.height || 1080),
    mediaDuration: a.duration ? Number(a.duration) : undefined,
    jobId: a.job,
  });
  if (words) {
    // legenda dinâmica: texto corrigido do roteiro + tempo de cada palavra falada
    const toTimeline = keep ? makeMapper(keep) : (t) => t;
    plan.captions = buildCaptions(roteiro, words, toTimeline);
    if (a.srt) fs.writeFileSync(a.srt, toSrt(plan.captions));
  }
  if (a.ajustes && plan.meta.segments) {
    // relatório: onde a fala foi diferente do roteiro e o que a edição mudou por isso
    const mmss = (/** @type {number} */ t) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
    const linhas = ["Trechos em que você falou diferente do roteiro (a edição seguiu a FALA):", ""];
    roteiro.segments.forEach((s, i) => {
      const x = /** @type {any} */ (s);
      const aj = (plan.meta.segments[i] && plan.meta.segments[i].ajustes) || [];
      if (!s.fields.FALA || (x.parecido >= 0.75 && !aj.length)) return;
      linhas.push(`[${mmss(x.tc)} do roteiro → ${mmss(s.start)} do vídeo]  ${Math.round((x.parecido || 0) * 100)}% igual`);
      linhas.push(`  ROTEIRO: ${s.fields.FALA.replace(/"/g, "").slice(0, 220)}`);
      linhas.push(`  FALOU:   ${(x.spoken || "(não achei na fala)").slice(0, 220)}`);
      for (const l of aj) linhas.push(`  → ${l}`);
      linhas.push("");
    });
    fs.writeFileSync(a.ajustes, linhas.join("\n"));
  }
  const json = JSON.stringify(plan, null, 2);
  if (a.out) fs.writeFileSync(a.out, json + "\n");
  else process.stdout.write(json + "\n");

  const preview = await analyzePlan(plan);
  console.error(`\n${roteiro.title}\n${formatPreview(preview)}`);
  for (const e of preview.validation.errors) console.error(`ERRO ${e.path}: ${e.message}`);
  for (const w of preview.validation.warnings) console.error(`aviso ${w.path}: ${w.message}`);
  process.exit(preview.validation.valid ? 0 : 1);
}

main();
