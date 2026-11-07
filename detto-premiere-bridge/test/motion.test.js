"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { direct, cameraAt, parseScore, parseNumber, headlineLines } = require("../tools/motion/director");
const { segmentKeys, score, sizedUrl } = require("../tools/motion/media-search");
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
  const seg = (id, start, end, broll, block) => ({ id, start, end, block, broll, mood: "" });
  const w = (text, s) => text.split(" ").map((x, i) => ({ w: x, s: s + i * 0.3, e: s + i * 0.3 + 0.25, hl: false }));
  // fala: "2x1" é dito em 14.3 s, "dois" (minutos) em 16.3 s, "2005" em 11.4 s
  const words = [
    ...w("Ontem acabou uma era viu", 0.2),
    ...w("17 de agosto de 2005 Budapeste", 10.2),
    ...w("A Argentina venceu por 2x1 a Hungria", 13.1),
    ...w("ficou menos de dois minutos em campo", 15.4),
    ...w("Você imaginava quem seria esse cara", 21.0),
    ...w("já se inscreve no canal", 24.6),
  ];
  return {
    sequence: { fps: 30 },
    cuts: [
      { start: 0, end: 10, timeline: 0 },
      { start: 11, end: 30, timeline: 10 },
    ],
    meta: { segments: [seg("s0", 0, 10, true, "ABERTURA / GANCHO"), seg("s1", 10, 20, true, "BLOCO 1 — A ESTREIA (2005)"), seg("s2", 20, 29, false, "BLOCO 1 — A ESTREIA (2005)")] },
    markers: [
      { time: 10, name: "BLOCO 1 — A ESTREIA (2005)", color: "blue" },
      { time: 10, name: "LINHA DO TEMPO → 2005", color: "cyan" },
    ],
    graphics: [
      { type: "headline", start: 0, duration: 10, text: "ONTEM, ACABOU UMA ERA" },
      { type: "date_stamp", start: 10, duration: 10, text: "17/08/2005 • BUDAPESTE" },
      { type: "scoreboard", start: 10.5, duration: 9, text: "ARGENTINA 2 x 1 HUNGRIA • AMISTOSO" },
      { type: "counter", start: 11, duration: 8, text: "MENOS DE 2 MINUTOS" },
      { type: "headline", start: 20, duration: 8, text: "VOCÊ IMAGINAVA?" },
      { type: "cta", start: 20.5, duration: 5, text: "COMENTA AÍ" },
    ],
    vfx: [
      { name: "SLOW_ZOOM+BREATH", start: 3, duration: 4, approximate: false },
      { name: "ZOOM_PUNCH_IN", start: 22, duration: 1.5, approximate: false },
    ],
    captions: [{ start: 0, end: 30, words }],
  };
}

test.describe("diretor", () => {
  const images = { s0: { file: "/tmp/a.jpg", creator: "Autor", license: "CC BY 4.0" } };
  const d = direct(miniPlan(), { images });
  const plates = d.items.filter((i) => i.z === 10);
  const at = (type) => plates.find((p) => p.type === type);

  test("cada gráfico entra na palavra falada (sincronia), não no início do trecho", () => {
    assert.ok(Math.abs(at("score").start - (14.3 - 0.12)) < 0.01, `placar em ${at("score").start}`);
    assert.ok(Math.abs(at("number").start - (16.3 - 0.12)) < 0.01, "'dois minutos' por extenso casa com o número 2");
    assert.ok(Math.abs(at("era").start - (11.4 - 0.12)) < 0.01, "cartão de era no ano falado");
    const kw = d.items.find((i) => i.type === "keyword");
    assert.ok(Math.abs(kw.start - (21.0 - 0.12)) < 0.01);
    const cta = d.items.find((i) => i.type === "cta");
    assert.ok(Math.abs(cta.start - (25.2 - 0.12)) < 0.01, "CTA no 'inscreve'");
  });

  test("layouts misturam tela cheia (voz ao fundo), janela, card e quadro de foto", () => {
    for (const p of plates) assert.ok(["full", "camWindow", "gfxCard", "photoCard"].includes(p.layout), `${p.type} sem layout`);
    const used = new Set(plates.filter((p) => p.type !== "photo").map((p) => p.layout));
    assert.ok(used.has("full") && used.size >= 2, `pouca variação: ${[...used]}`);
    for (const p of plates) if (["list", "bars", "era"].includes(p.type)) assert.notEqual(p.layout, "gfxCard");
    const photo = at("photo");
    assert.equal(photo.layout, "photoCard");
    assert.equal(photo.data.credit, "Autor • CC BY 4.0");
  });

  test("gráficos de tela não se sobrepõem", () => {
    const sorted = plates.slice().sort((a, b) => a.start - b.start);
    for (let i = 1; i < sorted.length; i++) assert.ok(sorted[i].start >= sorted[i - 1].end - 1e-9);
  });

  test("legenda some sob janela/palavra-chave e vai para o lado do rosto com card lateral", () => {
    const caps = d.items.filter((i) => i.type === "caption");
    const win = plates.filter((p) => p.layout === "camWindow" || p.layout === "full");
    for (const c of caps) {
      const mid = (c.start + c.end) / 2;
      assert.ok(!win.some((p) => mid >= p.start && mid < p.end), "legenda sob janela de câmera");
    }
  });

  test("câmera: base no enquadramento original; centraliza só no suspense, zoom de corte e punch-in", () => {
    const base = cameraAt(d, 1);
    assert.equal(base.z, 1);
    assert.equal(base.c, 0, "fora da dinâmica não centraliza no rosto");
    // aproximação lenta no suspense (SLOW_ZOOM em 3 s): zoom e centralização crescem juntos
    const p0 = cameraAt(d, 3.5);
    const p1 = cameraAt(d, 5.5);
    assert.ok(p0.z > 1 && p1.z > p0.z && p1.c > p0.c && p1.c <= 1, "aproximação contínua");
    // punch-in centraliza
    assert.equal(cameraAt(d, 22.5).c, 1);
    // zoom seco em alguns jump cuts (a cada 3), voltando ao plano original
    const cuts = Array.from({ length: 6 }, (_, i) => ({ start: i * 10, end: i * 10 + 4, timeline: i * 4 }));
    const d2 = direct({ ...miniPlan(), cuts, vfx: [] }, {});
    const zoom = d2.shots.find((s) => s.style === "cut");
    assert.ok(zoom && zoom.z > 1 && zoom.c === 1);
    assert.ok(d2.shots.filter((s) => s.style === "base").length > d2.shots.filter((s) => s.style === "cut").length, "maioria no plano original");
    const hit = d.shakes[0];
    const samples = Array.from({ length: 30 }, (_, i) => cameraAt(d, hit.t + i / 30).sx);
    assert.ok(Math.max(...samples.map(Math.abs)) <= hit.amp + 1e-9);
    assert.ok(Math.abs(cameraAt(d, hit.t + 0.7).sx) < 1e-9, "tremor termina rápido");
    // poucas inversões de sentido = tremor lento (não "vibração")
    let flips = 0;
    for (let i = 2; i < samples.length; i++) if (Math.sign(samples[i] - samples[i - 1]) !== Math.sign(samples[i - 1] - samples[i - 2])) flips++;
    assert.ok(flips <= 4, `tremor rápido demais (${flips} inversões em 1 s)`);
  });

  test("SFX acompanham as entradas", () => {
    const kinds = new Set(d.sfx.map((s) => s.kind));
    for (const k of ["whoosh", "hit", "pop", "click", "ding"]) assert.ok(kinds.has(k), `falta SFX ${k}`);
  });
});

test("busca de fotos: só Messi/estádio no título, época próxima, sem figurinhas", () => {
  const keys = segmentKeys('Messi no banco ("Messi banco Argentina Alemanha 2006")');
  assert.equal(keys.year, "2006");
  const s = (title, tags = []) => score({ title, tags: tags.map((name) => ({ name })), width: 1200, height: 800 }, keys);
  assert.ok(s("Messi Argentina Germany 2006 World Cup") > s("Lionel Messi Argentina v Egypt 7 July 2026"));
  assert.equal(s("Murfy", ["messi"]), -99, "tag sozinha não basta");
  assert.equal(s("Lionel Messi / Version FC Barcelona 2004 toy"), -99);
  assert.ok(sizedUrl({ url: "https://upload.wikimedia.org/wikipedia/commons/a/ab/Foo.jpg", width: 4000 }).includes("/thumb/a/ab/Foo.jpg/1280px-Foo.jpg"));
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
