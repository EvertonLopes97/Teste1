"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { parseRoteiro, normalizeText } = require("../tools/roteiro/parse");
const { buildPlan, graphicText, graphicType } = require("../tools/roteiro/build");
const { alignRoteiro, makeMapper, close } = require("../tools/roteiro/align");
const { validateEditPlan } = require("../plugin/src/core/schema");

const ROTEIRO = `=====================================================================
 ROTEIRO DE EDIÇÃO — "TESTE: DA EXPULSÃO À REDENÇÃO"
 Canal @detto.galo
=====================================================================

PADRÕES GERAIS DA EDIÇÃO
------------------------
- PALAVRÃO: em [00:20] tem um "pra caralho". Decidir: manter, ou passar um bip de humor.

=====================================================================
 ABERTURA / GANCHO
=====================================================================

[00:00 – 00:10]
FALA: "Ontem acabou uma era, viu?"
VISUAL: vídeo aéreo do estádio ("Monumental lotado")
TELA: "ONTEM, ACABOU UMA ERA" (palavra por palavra, dourado)
EFEITO: começa em preto e o vídeo abre com flash branco
MÚSICA: entra trilha emotiva baixa (piano)

=====================================================================
 BLOCO 1 — A ESTREIA (2005)
=====================================================================
>>> LINHA DO TEMPO avança para 2005

[00:10 – 00:20]
FALA: "Messi ficou menos de dois minutos em campo e saiu chorando."
VISUAL: Messi saindo de campo
TELA: carimbo "17/08/2005 • BUDAPESTE"; destaque "18 ANOS"
GRÁFICO: PLACA DE PLACAR: ARGENTINA 2 x 1 HUNGRIA • AMISTOSO (a placa aparece e "desbota" no fim)
SFX: tique-taque
EFEITO: punch-in em "saiu chorando"
>>> OBS PARA O EDITOR: no áudio parece "Zimbabwe". O certo é FRANÇA.

[00:20 – 00:30]
FALA: "Ele joga pra caralho."
VISUAL: facecam tela cheia (reação)
TELA: caixa de comentário animada: "COMENTA AÍ" + botão "SEGUIR"

=====================================================================
 CORTES VERTICAIS (9:16) SUGERIDOS
=====================================================================
1. "EXPULSO": [00:10 – 00:20]. Gancho: "O Messi foi EXPULSO."

=====================================================================
 ERRATA PARA A LEGENDA
=====================================================================
- "Jhonel Messi" → LIONEL MESSI
`;

const BASE = { mediaPath: "C:/v/gravacao.mov", fps: 30, width: 1920, height: 1080 };

test("parse: título, blocos, trechos, campos, eventos, OBS, 9:16, errata e notas", () => {
  const r = parseRoteiro(ROTEIRO);
  assert.equal(r.title, "TESTE: DA EXPULSÃO À REDENÇÃO");
  assert.deepEqual(r.blocks, ["ABERTURA / GANCHO", "BLOCO 1 — A ESTREIA (2005)"]);
  assert.equal(r.segments.length, 3);
  assert.deepEqual([r.segments[1].start, r.segments[1].end], [10, 20]);
  assert.match(r.segments[1].fields.GRAFICO, /^PLACA DE PLACAR/);
  assert.deepEqual(r.segments[1].events, ["LINHA DO TEMPO avança para 2005"]);
  assert.match(r.segments[1].notes[0], /^OBS PARA O EDITOR/);
  assert.deepEqual(r.verticalCuts, [{ index: 1, title: "EXPULSO", ranges: [{ start: 10, end: 20 }], hook: "O Messi foi EXPULSO." }]);
  assert.deepEqual(r.errata, [{ heard: "Jhonel Messi", correct: "LIONEL MESSI" }]);
  assert.equal(r.timedNotes[0].time, 20);
});

test("parse: aceita texto exportado do Drive (escapes de Markdown e emoji corrompido)", () => {
  assert.equal(normalizeText("\\[00:10 – 00:20\\] \\- ok"), "[00:10 – 00:20] - ok");
  assert.equal(normalizeText('TELA: "\u00f0\u009f\u008f\u0086 CAMPEÃO"'), 'TELA: " CAMPEÃO"');
});

test("build: plano válido no formato do Bridge", () => {
  const plan = buildPlan(parseRoteiro(ROTEIRO), BASE);
  const v = validateEditPlan(plan);
  assert.equal(v.valid, true, JSON.stringify(v.errors));
  assert.equal(plan.cuts.length, 3);
  assert.deepEqual(plan.cuts[1], { id: "seg_00m10s", source: "facecam_001", start: 10, end: 20, timeline: 10, track: "V1", audioTrack: "A1" });
  const names = plan.markers.map((m) => m.name);
  for (const n of ["ABERTURA / GANCHO", "BLOCO 1 — A ESTREIA (2005)", "LINHA DO TEMPO → 2005", "B-ROLL: Monumental lotado", "9:16 #1: EXPULSO", "PALAVRÃO"]) {
    assert.ok(names.includes(n), `falta marker ${n}`);
  }
  assert.ok(names.some((n) => n.startsWith("OBS:")));
  const byType = (t) => plan.graphics.filter((g) => g.type === t).map((g) => g.text);
  assert.deepEqual(byType("date_stamp"), ["17/08/2005 • BUDAPESTE"]);
  assert.deepEqual(byType("scoreboard"), ["ARGENTINA 2 x 1 HUNGRIA • AMISTOSO"]);
  assert.deepEqual(byType("cta"), ["COMENTA AÍ → SEGUIR"]);
  assert.equal(plan.vfx.find((v) => v.start >= 10).name, "ZOOM_PUNCH_IN");
  assert.equal(plan.meta.errata.length, 1);
});

test("graphicText/graphicType: heurísticas de texto de tela", () => {
  assert.equal(graphicText('um CARTÃO VERMELHO 3D gira e "bate" na tela'), "CARTÃO VERMELHO 3D");
  assert.equal(graphicText("CHAVEAMENTO ANIMADO da Copa 2022 se acendendo: ARÁBIA SAUDITA 2 x 1 ARGENTINA (estreia)"), "ARÁBIA SAUDITA 2 x 1 ARGENTINA");
  assert.equal(graphicText("HOLANDA 2 x 2 ARGENTINA (pênaltis: 3 x 4) • QUARTAS"), "HOLANDA 2 x 2 ARGENTINA (pênaltis: 3 x 4) • QUARTAS");
  assert.equal(graphicType('contador "GOLS NA COPA: 0"', "TELA"), "counter");
  assert.equal(graphicType("FRANÇA 4 x 3 ARGENTINA", "GRAFICO"), "scoreboard");
});

test.describe("alinhamento com a transcrição", () => {
  // fala real começa mais tarde e mais rápido do que o roteiro estimou, com uma pausa longa
  const words = [
    ["Ontem", 0.5], ["acabou", 0.8], ["uma", 1.1], ["era", 1.3], ["viu", 1.6],
    ["Messi", 6.0], ["ficou", 6.3], ["menos", 6.6], ["de", 6.8], ["dois", 7.0], ["minutos", 7.3], ["em", 7.7], ["campo", 7.9],
    ["e", 8.2], ["saiu", 8.4], ["chorando", 8.7],
    ["Ele", 9.5], ["joga", 9.8], ["pra", 10.1], ["caralho", 10.3],
  ].map(([w, s]) => ({ w: String(w), s: Number(s), e: Number(s) + 0.25 }));

  test("trechos começam onde a FALA começa; deixas e palavrão viram tempos exatos", () => {
    const { roteiro, keep, report } = alignRoteiro(parseRoteiro(ROTEIRO), words, { mediaDuration: 12 });
    assert.equal(report.matched, 3);
    assert.deepEqual(roteiro.segments.map((s) => Number(s.start.toFixed(2))), [0, 5.88, 9.38]);
    assert.equal(roteiro.segments[1].cues["saiu chorando"], 8.4);
    assert.equal(roteiro.timedNotes[0].time, 10.3);
    // pausa de 1.6→6.0 removida
    assert.equal(keep.length, 2);
    assert.equal(keep[0].start, 0);
    assert.ok(keep[1].start > 5.5 && keep[1].start < 6);
  });

  test("plano com jump cuts: timeline contínua, efeitos na deixa e bip no palavrão", () => {
    const { roteiro, keep } = alignRoteiro(parseRoteiro(ROTEIRO), words, { mediaDuration: 12 });
    const plan = buildPlan(roteiro, { ...BASE, keep, mediaDuration: 12 });
    assert.equal(validateEditPlan(plan).valid, true);
    let t = 0;
    for (const c of plan.cuts) {
      assert.ok(Math.abs(c.timeline - t) < 0.05, `buraco na timeline em ${c.id}`);
      t = c.timeline + (c.end - c.start);
    }
    assert.ok(t < 12 - 3, "pausa longa removida");
    const punch = plan.vfx.find((v) => v.name === "ZOOM_PUNCH_IN");
    assert.equal(punch.approximate, false);
    const map = makeMapper(keep);
    assert.ok(Math.abs(punch.start - (map(8.4) - 0.1)) < 0.05);
    const bleep = plan.audio.find((a) => a.type === "bleep");
    assert.ok(Math.abs(bleep.start - map(10.3)) < 0.05);
  });

  test("close(): tolera pequenas diferenças de transcrição", () => {
    assert.equal(close("gotze", "gotz"), true);
    assert.equal(close("lusail", "luzail"), true);
    assert.equal(close("messi", "mexico"), false);
  });
});
