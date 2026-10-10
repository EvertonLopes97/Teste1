"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { parseRoteiro } = require("../tools/roteiro/parse");
const { alignRoteiro } = require("../tools/roteiro/align");
const { buildCaptions } = require("../tools/roteiro/captions");
const { buildPlan } = require("../tools/roteiro/build");
const { roteiroComponents, gamesInFala, normModo } = require("../tools/roteiro/componentes");
const { direct } = require("../tools/motion/director");
const { segmentKeys, score } = require("../tools/motion/media-search");

const ROTEIRO = `=====================================================================
 ROTEIRO + MAPA DE EDIÇÃO — "MELHORES E PIORES DA RODADA"
=====================================================================

=====================================================================
 0. GANCHO (0:00 – 0:20)
=====================================================================

[0:00 – 0:06]  MODO: [CAM] + [VFX]
FALA: "Essa rodada teve TRÊS notas 10 no Sofascore."
VFX: três "10" azuis caem do topo da tela.

[0:06 – 0:20]  MODO: [CAM+MG]
FALA: "Teve goleiro com nota 9,5 que perdeu o jogo e um jogador que foi expulso e tirou 4,5."
MG: dois cards entram sincronizados com a fala:
    RONALDO (Bahia) 9,5 → TOMÁS PÉREZ (Galo) 4,5
    O card do Pérez entra com glitch vermelho e um cartão vermelho carimba em cima.

=====================================================================
 1. OS RESULTADOS (0:20 – 0:45)
=====================================================================

[0:20 – 0:35]  MODO: [MG+VO]
FALA: "Quarta-feira: Inter 2 a 1 Corinthians. Vitória 4 a 0 na Chape. Quinta-feira: Athletico 2 a 2 Galo."
MG: as PLACAS DE PLACAR caem uma por vez.

[0:35 – 0:45]  MODO: [CAM]
FALA: "Pegou fogo, né, velho? O Palmeiras alcança o Flamengo?"
[IMPROVISA: seu palpite]
TELA: enquete "QUEM É CAMPEÃO? 🔴⚫ x 🟢" no canto.

=====================================================================
 CTA 1 (0:45 – 0:50)  MODO: [CAM]
=====================================================================
FALA: "Comenta aí e segue o perfil."
TELA: balão de comentário + botão "SEGUIR" sendo clicado.

=====================================================================
 7. A SELEÇÃO DA RODADA — CAMPINHO (0:50 – 1:10)
=====================================================================
MODO: [MG+VO] do começo ao fim
TRILHA: trap pesado.

[0:50 – 0:52]
MG: o campo desce do topo; título "SELEÇÃO DA RODADA".

[0:52 – 1:10]
FALA: "No gol, Ronaldo. No meio, Savarino. No ataque, Neymar."
MG: cada mini-card entra na posição:
           [ NEYMAR 8,3 ]
       [ SAVARINO 10 ]
         [ RONALDO 9,5 ]

=====================================================================
 CORTES VERTICAIS (9:16) PRA TIKTOK / REELS / SHORTS
=====================================================================
1. "3 NOTAS 10" — [0:00 – 0:20]. Gancho na tela: "TRÊS NOTAS 10
   NA MESMA RODADA"

=====================================================================
 LISTA DE ASSETS PRA SEPARAR ANTES DE EDITAR
=====================================================================
  Melhores: Ronaldo (BAH), Savarino (FLU), Neymar (SAN).
  Piores: Tomás Pérez (CAM).
`;

/** fala "real": algumas palavras trocadas, muletas e um improviso que não está no roteiro */
function falado(r) {
  const words = [];
  let t = 0.3;
  const say = (w) => {
    words.push({ w, s: +t.toFixed(2), e: +(t + 0.3).toFixed(2) });
    t += 0.36;
  };
  r.segments.forEach((s) => {
    t += 0.8;
    s.realStart = t;
    const fala = (s.fields.FALA || "").replace(/"/g, "").split(/\s+/).filter(Boolean);
    fala.forEach((w, i) => {
      if (i === 2) say("tipo"); // muleta
      say(i === 4 ? "assim" : w); // palavra trocada
    });
    if (s.improv) "eu acho que o verdão leva esse título fácil rapaziada".split(" ").forEach(say);
  });
  return words;
}

test("roteiro com MODO: cabeçalho com tempo, MODO na linha do tempo, sub-blocos, improviso, 9:16 em duas linhas", () => {
  const r = parseRoteiro(ROTEIRO);
  assert.equal(r.title, "MELHORES E PIORES DA RODADA");
  const modos = r.segments.map((s) => normModo(s.fields.MODO).modo);
  assert.deepEqual(modos, ["CAM", "CAM+MG", "MG+VO", "CAM", "CAM", "MG+VO", "MG+VO"]);
  assert.ok(r.segments.find((s) => s.start === 45 && s.header), "CTA sem [tempo] vira trecho do cabeçalho");
  assert.ok(r.segments.find((s) => s.start === 35).improv);
  assert.deepEqual(r.verticalCuts[0], { index: 1, title: "3 NOTAS 10", ranges: [{ start: 0, end: 20 }], hook: "TRÊS NOTAS 10 NA MESMA RODADA" });
  assert.match(r.assets, /Ronaldo \(BAH\)/);
});

test("componentes: cards com time e nota, cartão vermelho no certo, placares da fala, enquete, campinho", () => {
  const r = parseRoteiro(ROTEIRO);
  const c = roteiroComponents(r);
  const comp = (i, type) => c.segments[i].comps.find((x) => x.type === type);
  assert.equal(comp(0, "bignum").data.count, 3);
  const cards = comp(1, "cards").data.cards;
  assert.deepEqual(cards.map((x) => [x.name, x.sigla, x.rating, !!x.red]), [["Ronaldo", "BAH", 9.5, false], ["Tomás Pérez", "CAM", 4.5, true]]);
  const games = comp(2, "scoregrid").data.groups;
  assert.deepEqual(games.map((g) => [g.label, g.games.map((m) => `${m.siglaA} ${m.sa}x${m.sb} ${m.siglaB}`)]), [["QUARTA", ["INT 2x1 COR", "VIT 4x0 CHA"]], ["QUINTA", ["CAP 2x2 CAM"]]]);
  assert.deepEqual(comp(3, "poll").data.options.sort(), ["FLAMENGO", "PALMEIRAS"]);
  assert.ok(comp(4, "cta"));
  const pitch = comp(5, "pitch");
  assert.equal(pitch.data.title, "SELEÇÃO DA RODADA");
  assert.deepEqual(pitch.data.rows.map((row) => row.map((x) => x.name)), [["Neymar"], ["Savarino"], ["Ronaldo"]]);
  assert.ok(c.segments[6].comps[0].continues, "o campinho continua no trecho seguinte");
  assert.deepEqual(gamesInFala("a vitória do Palmeiras 1 a 0").length, 0, "\"vitória\" minúsculo não é time");
});

test("fala mudada: cada trecho começa onde foi falado; a legenda mostra o que foi DITO", () => {
  const r = parseRoteiro(ROTEIRO);
  const words = falado(r);
  const a = alignRoteiro(r, words, { mediaDuration: words.at(-1).e + 1 });
  a.roteiro.segments.forEach((s, i) => {
    if (!r.segments[i].fields.FALA || i === 0) return;
    assert.ok(Math.abs(s.start - r.segments[i].realStart) < 0.6, `trecho ${s.tc}: ${s.start} ≠ ${r.segments[i].realStart}`);
  });
  const caps = buildCaptions(a.roteiro, words, (t) => t);
  const text = caps.map((c) => c.text).join(" ");
  assert.match(text, /tipo/, "muleta falada aparece");
  assert.match(text, /verdão leva esse título/, "improviso aparece na legenda");
  assert.match(text, /Sofascore/, "grafia do roteiro nos nomes");
});

test("diretor por MODO: CAM+MG = câmera pequena, MG+VO = tela cheia, cards na hora do nome", () => {
  const r = parseRoteiro(ROTEIRO);
  const words = falado(r);
  const a = alignRoteiro(r, words, { mediaDuration: words.at(-1).e + 1 });
  const plan = buildPlan(a.roteiro, { keep: a.keep, mediaPath: "x.mov", fps: 30, width: 1920, height: 1080, mediaDuration: words.at(-1).e + 1 });
  plan.captions = buildCaptions(a.roteiro, words, (t) => t);
  // sem jump cuts no teste: timeline = mídia
  plan.cuts = [{ id: "c1", source: "facecam_001", start: 0, end: words.at(-1).e + 1, timeline: 0, track: "V1", audioTrack: "A1" }];
  plan.meta.segments.forEach((s, i) => {
    s.start = a.roteiro.segments[i].start;
    s.end = a.roteiro.segments[i].end;
  });
  const d = direct(plan, { assets: { players: { Ronaldo: { photo: "/tmp/r.png" } }, teams: {} } });
  const cards = d.items.find((i) => i.type === "cards");
  assert.equal(cards.layout, "camPip");
  assert.equal(cards.data.cards[0].photo, "/tmp/r.png");
  const grid = d.items.find((i) => i.type === "scoregrid");
  assert.equal(grid.layout, "full");
  assert.ok(grid.data.groups[0].games.every((g) => g.at !== undefined), "cada placar na hora em que é falado");
  const pitch = d.items.find((i) => i.type === "pitch");
  assert.ok(pitch.start < plan.meta.segments[6].start && pitch.end >= d.duration - 0.01, "campinho cobre os trechos do bloco");
  assert.ok(d.items.find((i) => i.type === "bignum" && !i.layout), "números caindo por cima da câmera");
  // legenda não aparece por cima dos gráficos
  const caps = d.items.filter((i) => i.type === "caption");
  assert.ok(!caps.some((c) => c.start >= grid.start && c.start < grid.end));
});

test("fotos de apoio: só com a pessoa citada no título (nada de Messi fixo)", () => {
  const k = segmentKeys("Hulk Atlético-MG 2021");
  assert.deepEqual(k.person, ["Hulk"]);
  assert.equal(score({ title: "Lionel Messi 2021", width: 900, height: 900 }, k), -99);
  assert.ok(score({ title: "Hulk Atletico Mineiro 2021", width: 900, height: 900 }, k) > 5);
});
