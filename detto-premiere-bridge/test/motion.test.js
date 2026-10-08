"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { direct, parseScore, parseNumber, headlineLines } = require("../tools/motion/director");
const { flagCode } = require("../tools/motion/flags");
const { writeSfxTrack } = require("../tools/motion/sfx");
const { alignWords, toSrt } = require("../tools/roteiro/captions");

test("parseScore: times, bandeiras, pênaltis, competição e derrota da Argentina", () => {
  const s = parseScore("ALEMANHA 1 x 1 ARGENTINA (pênaltis: 4 x 2 Alemanha) • QUARTAS 2006");
  assert.deepEqual([s.a.flag, s.b.flag, s.sa, s.sb], ["de", "ar", 1, 1]);
  assert.equal(s.sub, "pênaltis: 4 x 2 Alemanha");
  assert.equal(s.comp, "QUARTAS 2006");
  assert.equal(s.loss, true);
  assert.equal(parseScore("ARGENTINA 3 x 3 FRANÇA (pênaltis: 4 x 2 Argentina) • FINAL").loss, false);
  assert.equal(parseScore("✅ POLÔNIA 0 x 2 ARGENTINA").loss, false);
  assert.equal(parseScore("INGLATERRA 1 x 0 → 1 x 1 (Enzo, 85') → 1 x 2"), null);
  assert.equal(flagCode("Sérvia e Montenegro"), "rs");
  assert.equal(flagCode("ARÁBIA SAUDITA"), "sa");
});

test("parseNumber: rótulos antes/depois, milhar, minuto e descrições ignoradas", () => {
  assert.deepEqual(
    (({ display, num, top, label }) => ({ display, num, top, label }))(parseNumber("MENOS DE 2 MINUTOS")),
    { display: "2", num: 2, top: "MENOS DE", label: "MINUTOS" }
  );
  const fans = parseNumber("👥 +85.000");
  assert.equal(fans.num, 85000);
  assert.equal(fans.thousands, true);
  assert.equal(parseNumber("113'").suffix, "'");
  assert.equal(parseNumber("FINAIS PERDIDAS: 2").label, "FINAIS PERDIDAS");
  assert.equal(parseNumber("00:00 01:5X"), null);
});

test("headlineLines: quebra em linhas com a do meio em destaque", () => {
  assert.deepEqual(headlineLines("ÚLTIMO JOGO • 06/10/2026"), [
    { text: "ÚLTIMO JOGO", box: false },
    { text: "06/10/2026", box: true },
  ]);
  assert.equal(headlineLines("A FOTO MAIS TRISTE DA CARREIRA").length, 3);
});

function miniPlan() {
  const seg = (start, end, broll, block) => ({ id: `s${start}`, start, end, block, broll, mood: "" });
  return {
    sequence: { fps: 30 },
    cuts: [
      { start: 0, end: 10, timeline: 0 },
      { start: 11, end: 30, timeline: 10 },
    ],
    meta: { segments: [seg(0, 10, true, "ABERTURA / GANCHO"), seg(10, 20, true, "BLOCO 1 — A ESTREIA (2005)"), seg(20, 29, false, "BLOCO 1 — A ESTREIA (2005)")] },
    markers: [
      { time: 10, name: "BLOCO 1 — A ESTREIA (2005)", color: "blue" },
      { time: 10, name: "LINHA DO TEMPO → 2005", color: "cyan" },
    ],
    graphics: [
      { type: "headline", start: 0, duration: 10, text: "ONTEM, ACABOU UMA ERA" },
      { type: "date_stamp", start: 10, duration: 10, text: "17/08/2005 • BUDAPESTE" },
      { type: "scoreboard", start: 10.5, duration: 9, text: "ARGENTINA 2 x 1 HUNGRIA • AMISTOSO" },
      { type: "counter", start: 12, duration: 8, text: "MENOS DE 2 MINUTOS" },
      { type: "headline", start: 21, duration: 8, text: "VOCÊ IMAGINAVA?" },
      { type: "cta", start: 24, duration: 5, text: "COMENTA AÍ" },
    ],
    vfx: [{ name: "ZOOM_PUNCH_IN", start: 22, duration: 1.5, approximate: false }],
    captions: [
      { start: 0.5, end: 1.5, words: [{ w: "Ontem", s: 0.5, e: 1, hl: false }] },
      { start: 21.2, end: 21.8, words: [{ w: "imaginava", s: 21.2, e: 21.8, hl: false }] },
      { start: 26, end: 27, words: [{ w: "livre", s: 26, e: 27, hl: false }] },
    ],
  };
}

test.describe("diretor", () => {
  const d = direct(miniPlan());
  const plates = d.items.filter((i) => i.z === 10);

  test("cartão de era no início do bloco e placas nos trechos de narração", () => {
    const era = plates.find((p) => p.type === "era");
    assert.equal(era.start, 10);
    assert.equal(era.data.year, "2005");
    assert.equal(era.data.title, "A ESTREIA");
    assert.ok(plates.some((p) => p.type === "score" && p.data.a.flag === "ar" && p.data.b.flag === "hu"));
    assert.ok(plates.some((p) => p.type === "headline"));
  });

  test("placas não se sobrepõem e deixam facecam entre elas", () => {
    const sorted = plates.slice().sort((a, b) => a.start - b.start);
    for (let i = 1; i < sorted.length; i++) {
      const gap = sorted[i].start - sorted[i - 1].end;
      assert.ok(gap >= -1e-9, "sobreposição de placas");
      if (sorted[i - 1].type !== "era") assert.ok(gap >= 0.99, `facecam curta demais entre placas (${gap.toFixed(2)}s)`);
    }
  });

  test("trecho de opinião: palavra-chave e CTA sobre a facecam; legenda só com facecam limpa", () => {
    assert.ok(d.items.some((i) => i.type === "keyword" && i.data.text === "VOCÊ IMAGINAVA?"));
    assert.ok(d.items.some((i) => i.type === "cta"));
    const caps = d.items.filter((i) => i.type === "caption").map((c) => c.data.words[0].w);
    assert.ok(!caps.includes("Ontem"), "legenda sob placa de tela cheia");
    assert.ok(!caps.includes("imaginava"), "legenda sob palavra-chave");
  });

  test("enquadramentos cobrem a timeline sem buracos e variam a cada plano", () => {
    assert.equal(d.shots[0].start, 0);
    for (let i = 1; i < d.shots.length; i++) {
      assert.ok(Math.abs(d.shots[i].start - d.shots[i - 1].end) < 1e-6);
      assert.notEqual(d.shots[i].z, d.shots[i - 1].z);
    }
    assert.ok(Math.abs(d.shots.at(-1).end - d.duration) < 1e-6);
    assert.deepEqual(d.punches, [{ start: 22, end: 23.4, dz: 0.16 }]);
  });

  test("SFX acompanham as entradas", () => {
    const kinds = new Set(d.sfx.map((s) => s.kind));
    for (const k of ["whoosh", "hit", "pop", "click", "ding"]) assert.ok(kinds.has(k), `falta SFX ${k}`);
    assert.ok(d.sfx.every((s, i) => i === 0 || s.t >= d.sfx[i - 1].t));
  });

  test("sépia/P&B do roteiro não vão para a facecam por padrão", () => {
    const plan = miniPlan();
    plan.vfx.push({ name: "SEPIA", start: 0, duration: 5 });
    assert.deepEqual(direct(plan).filters.sepia, []);
    assert.deepEqual(direct(plan, { facecamColorFx: true }).filters.sepia, [[0, 5]]);
  });
});

test("SFX: WAV mono 48 kHz com a duração pedida", () => {
  const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "sfx-")), "sfx.wav");
  writeSfxTrack([{ t: 0.1, kind: "whoosh" }, { t: 0.5, kind: "hit" }, { t: 0.9, kind: "ding" }], 2, file);
  const buf = fs.readFileSync(file);
  assert.equal(buf.toString("ascii", 0, 4), "RIFF");
  assert.equal(buf.readUInt32LE(24), 48000);
  assert.equal(buf.readUInt32LE(40), 2 * 48000 * 2);
  let peak = 0;
  for (let i = 44; i < buf.length; i += 2) peak = Math.max(peak, Math.abs(buf.readInt16LE(i)));
  assert.ok(peak > 3000, "SFX audível");
});

test("legendas: texto do roteiro com o tempo da fala, mesmo com palavra ouvida errada", () => {
  const heard = [
    { w: "aos", s: 1.0, e: 1.2 },
    { w: "113", s: 1.2, e: 1.6 },
    { w: "minutos", s: 1.6, e: 2.0 },
    { w: "Götz", s: 2.1, e: 2.4 },
    { w: "fez", s: 2.4, e: 2.6 },
    { w: "o", s: 2.6, e: 2.7 },
    { w: "gol", s: 2.7, e: 3.0 },
  ];
  const times = alignWords(["aos", "113", "minutos,", "Götze", "fez", "o", "gol."], heard);
  assert.deepEqual(times.map((t) => t && t.s), [1.0, 1.2, 1.6, 2.1, 2.4, 2.6, 2.7]);
  const srt = toSrt([{ start: 61.5, end: 62.25, text: "Götze fez o gol.", words: [] }]);
  assert.equal(srt, "1\n00:01:01,500 --> 00:01:02,250\nGötze fez o gol.\n");
});
