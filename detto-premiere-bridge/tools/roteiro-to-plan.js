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
const { buildCaptions, toSrt } = require("./roteiro/captions");
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
  let roteiro = parseRoteiro(fs.readFileSync(a._[0], "utf-8"));
  let keep;
  let words = null;
  if (a.words) {
    if (!a.duration) throw new Error("--words exige --duration (duração real da mídia em segundos)");
    words = JSON.parse(fs.readFileSync(a.words, "utf-8"));
    const aligned = alignRoteiro(roteiro, words, {
      mediaDuration: Number(a.duration),
      gap: a.gap ? Number(a.gap) : undefined,
    });
    roteiro = aligned.roteiro;
    if (!a["no-jumpcuts"]) keep = aligned.keep;
    console.error(`alinhamento: ${aligned.report.matched} trechos encontrados na fala, ${aligned.report.estimated} estimados`);
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
