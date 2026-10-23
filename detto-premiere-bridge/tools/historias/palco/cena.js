"use strict";

/**
 * PALCO DAS HISTÓRIAS — desenha cada cena por código (SVG), no estilo dos reels que viralizaram
 * (Histórias com Kaio / Contos de Stick): formas simples, cores chapadas, bonequinho CABEÇUDO, legenda grande em
 * caixa alta, relógio no canto. Desenhar por código (em vez de gerar imagem por IA) mantém o MESMO visual em todos os
 * episódios da série e é instantâneo.
 *
 * DUAS CAMADAS, para dar para ANIMAR de verdade sem refazer o desenho caro a cada quadro:
 *   #fundo  — o cenário, desenhado UMA vez por cena (recebe o movimento de câmera e o parallax)
 *   #atores — personagens, objetos e efeitos, REDESENHADOS a cada quadro (andar, piscar, falar, chuva, fumaça, água)
 *
 * window.CENA.monta(cena) → prepara a cena;  window.CENA.anima(p, t) → p = 0..1 dentro da cena, t = segundos do vídeo.
 */

const W = 1080;
const H = 1920;

/* paletas por luz — a base é a do Kaio: creme, bege e terroso; "noite"/"escuro" só escurecem o mesmo mundo */
const LUZ = {
  dia: { ceu: "#cfe0e6", fundo: "#efe6d6", parede: "#efe6d6", rodape: "#c9b99a", chao: "#b9a98a", predio: "#cbbfa8", predio2: "#d8cdb5", vidro: "#c3c8c2", vidroOn: "#f2c14e", tinta: "#2e2a26", veu: "" },
  tarde: { ceu: "#f3cfa0", fundo: "#efe0cb", parede: "#efe0cb", rodape: "#c6ab84", chao: "#b09268", predio: "#c9b394", predio2: "#d6c3a6", vidro: "#c9c0ae", vidroOn: "#ffb347", tinta: "#2e2a26", veu: "rgba(255,160,60,.10)" },
  noite: { ceu: "#39434f", fundo: "#4a4e55", parede: "#55565a", rodape: "#4a4034", chao: "#3b3a38", predio: "#5c5a55", predio2: "#6a665f", vidro: "#4b4f55", vidroOn: "#ffd98a", tinta: "#efe6d6", veu: "rgba(20,26,40,.16)" },
  escuro: { ceu: "#23282f", fundo: "#2c2f34", parede: "#33353a", rodape: "#2e2922", chao: "#24242a", predio: "#383a3c", predio2: "#43443f", vidro: "#33363b", vidroOn: "#8e8468", tinta: "#e4dccb", veu: "rgba(0,0,0,.20)" },
  chuva: { ceu: "#8d969b", fundo: "#9aa0a2", parede: "#9fa3a3", rodape: "#7d7466", chao: "#6f7072", predio: "#8e9191", predio2: "#9ea09c", vidro: "#8a9095", vidroOn: "#e8d9a8", tinta: "#f3efe6", veu: "rgba(120,140,150,.14)" },
  alerta: { ceu: "#5a3430", fundo: "#6b413a", parede: "#70463d", rodape: "#53352a", chao: "#48302a", predio: "#6d453c", predio2: "#7d5245", vidro: "#6a443d", vidroOn: "#ff8a6b", tinta: "#f8ece6", veu: "rgba(190,60,40,.16)" },
};

const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const r2 = (n) => Math.round(n * 10) / 10;

/* clareia/escurece uma cor #rrggbb (para a faixa do cabelo, a sombra da roupa etc.) */
function tom(hex, k) {
  const m = /^#?([0-9a-f]{6})$/i.exec(String(hex || ""));
  if (!m) return hex;
  const v = parseInt(m[1], 16);
  const f = (c) => Math.max(0, Math.min(255, Math.round(c + (k > 0 ? (255 - c) * k : c * k))));
  return `#${[(v >> 16) & 255, (v >> 8) & 255, v & 255].map((c) => f(c).toString(16).padStart(2, "0")).join("")}`;
}

/* ---------------------------------------------------------------- bonequinho
   Estilo do modelo: cabeça REDONDA grande sem pescoço, cabelo de tigela com faixa clara, olhos ovais grandes,
   sobrancelhas finas, boca pequena aberta, braços com MÃOS REDONDAS, calça e sapatos escuros.
   A ROUPA vem da história (`roupa`: moletom, camisa, jaleco, uniforme, terno, pijama, regata, capuz) e os
   acessórios também (`mochila`, `bone`, `colete`, `lanterna`) — assim o personagem veste o que a cena pede. */
const ROUPAS = ["moletom", "camisa", "jaleco", "uniforme", "terno", "pijama", "regata", "capuz"];

function pessoa(q, t) {
  const x = q.x * W;
  const y = q.y * H;
  const alt = q.alt || 430;
  const u = alt / 100;
  const pose = q.pose || "parado";
  const roupa = ROUPAS.includes(q.roupa) ? q.roupa : "moletom";
  const cor = q.cor || (roupa === "jaleco" ? "#eef2f3" : roupa === "terno" ? "#2f3540" : "#4a6b6b");
  const pele = q.pele || "#f0d5a8";
  const cabelo = q.cabelo || "#5a3b26";
  const olh = q.olhando == null ? 1 : q.olhando;

  const andando = pose === "andando" || pose === "correndo";
  const vel = pose === "correndo" ? 9 : 5;
  const passo = andando ? Math.sin(t * vel) : 0;
  const bob = andando ? Math.abs(Math.cos(t * vel)) * 3 * u : Math.sin(t * 1.7) * 1.1 * u; // respiração / pulo do passo
  const agacha = pose === "agachado" ? 26 * u : 0;

  const cabR = 23 * u;                       // cabeça GRANDE (é a assinatura do estilo)
  const corpoH = 34 * u;
  const pernaH = 26 * u;
  const yPes = y - agacha * 0.3;
  const yCorpo = yPes - pernaH - corpoH + bob;
  const yCab = yCorpo - cabR * 0.86;
  const p = [];

  // ---- mochila ATRÁS do corpo (aparece pelos lados; as alças vêm depois, por cima do tronco)
  if (q.mochila) {
    const mc = q.cor_mochila || "#7a5637";
    p.push(`<rect x="${x - 24 * u}" y="${yCorpo + 1 * u}" width="${48 * u}" height="${corpoH * 0.92}" rx="${9 * u}" fill="${tom(mc, -0.25)}"/>`);
  }

  // ---- pernas
  const calca = q.calca || (roupa === "pijama" ? "#6d7f9c" : roupa === "terno" ? "#2a2f38" : "#3a5a86");
  if (pose === "agachado") {
    for (const lado of [-1, 1]) {
      p.push(`<path d="M${x + lado * 7 * u} ${yCorpo + corpoH} L${x + lado * 17 * u} ${yPes - 6 * u} L${x + lado * 23 * u} ${yPes}" stroke="${calca}" stroke-width="${10 * u}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`);
    }
  } else {
    const a1 = passo * 11 * u;
    for (const [lado, d] of [[-1, a1], [1, -a1]]) {
      const px = x + lado * 6 * u + d;
      p.push(`<path d="M${x + lado * 6 * u} ${yCorpo + corpoH} L${px} ${yPes}" stroke="${calca}" stroke-width="${10 * u}" fill="none" stroke-linecap="round"/>`);
      p.push(`<rect x="${px - (lado < 0 ? 7 : 3) * u}" y="${yPes - 2 * u}" width="${10 * u}" height="${4.6 * u}" rx="${2.3 * u}" fill="#23262b"/>`);
    }
  }

  // ---- tronco (ombros arredondados, largo, sem pescoço)
  const larg = roupa === "regata" ? 33 : 38;
  if (roupa === "regata") {  // ombros de pele, camiseta mais estreita
    p.push(`<rect x="${x - 19 * u}" y="${yCorpo}" width="${38 * u}" height="${corpoH + 2 * u}" rx="${12 * u}" fill="${pele}"/>`);
  }
  p.push(`<rect x="${x - larg / 2 * u}" y="${yCorpo}" width="${larg * u}" height="${corpoH + 2 * u}" rx="${12 * u}" fill="${cor}"/>`);

  // detalhes por tipo de roupa — é o que faz o personagem "vestir" a cena
  if (roupa === "moletom" || roupa === "capuz") {
    p.push(`<rect x="${x - 11 * u}" y="${yCorpo + corpoH * 0.6}" width="${22 * u}" height="${9 * u}" rx="${4 * u}" fill="${tom(cor, -0.18)}"/>`); // bolso canguru
    if (roupa === "capuz") p.push(`<path d="M${x - 17 * u} ${yCorpo + 3 * u} q${17 * u} ${-16 * u} ${34 * u} 0 z" fill="${tom(cor, -0.14)}"/>`);
  } else if (roupa === "camisa") {
    p.push(`<path d="M${x - 8 * u} ${yCorpo + 1 * u} L${x} ${yCorpo + 11 * u} L${x + 8 * u} ${yCorpo + 1 * u}" fill="${tom(cor, 0.5)}"/>`);
    for (let i = 0; i < 3; i++) p.push(`<circle cx="${x}" cy="${yCorpo + (16 + i * 7) * u}" r="${1.3 * u}" fill="${tom(cor, -0.35)}"/>`);
  } else if (roupa === "jaleco") {
    p.push(`<rect x="${x - 1 * u}" y="${yCorpo + 2 * u}" width="${2 * u}" height="${corpoH - 2 * u}" fill="${tom(cor, -0.12)}"/>`);
    p.push(`<rect x="${x + 6 * u}" y="${yCorpo + 17 * u}" width="${10 * u}" height="${8 * u}" rx="${1.5 * u}" fill="${tom(cor, -0.1)}"/>`);
  } else if (roupa === "uniforme") {
    p.push(`<rect x="${x - larg / 2 * u}" y="${yCorpo + 13 * u}" width="${larg * u}" height="${6 * u}" fill="${tom(cor, 0.45)}"/>`);
  } else if (roupa === "terno") {
    p.push(`<path d="M${x - 9 * u} ${yCorpo + 1 * u} L${x} ${yCorpo + 14 * u} L${x + 9 * u} ${yCorpo + 1 * u} L${x + 9 * u} ${yCorpo + 9 * u} L${x} ${yCorpo + 20 * u} L${x - 9 * u} ${yCorpo + 9 * u} z" fill="${tom(cor, 0.22)}"/>`);
    p.push(`<path d="M${x - 2.6 * u} ${yCorpo + 9 * u} L${x + 2.6 * u} ${yCorpo + 9 * u} L${x + 1.8 * u} ${yCorpo + 24 * u} L${x - 1.8 * u} ${yCorpo + 24 * u} z" fill="#9b2d2d"/>`);
  } else if (roupa === "pijama") {
    for (let i = 0; i < 4; i++) p.push(`<rect x="${x - larg / 2 * u + (3 + i * 9) * u}" y="${yCorpo + 2 * u}" width="${3 * u}" height="${corpoH - 2 * u}" fill="${tom(cor, 0.35)}" opacity=".7"/>`);
  }
  if (q.colete) p.push(`<rect x="${x - 15 * u}" y="${yCorpo + 4 * u}" width="${30 * u}" height="${corpoH - 6 * u}" rx="${5 * u}" fill="#e8a33d" opacity=".92"/>
    <rect x="${x - 15 * u}" y="${yCorpo + 16 * u}" width="${30 * u}" height="${4 * u}" fill="#f4f1e6"/>`);

  // alças da mochila, por cima do tronco (é o que se vê de frente, como no modelo)
  if (q.mochila) {
    const mc = tom(q.cor_mochila || "#7a5637", -0.08);
    for (const lado of [-1, 1]) {
      p.push(`<path d="M${x + lado * 11 * u} ${yCorpo + 1 * u} L${x + lado * 13 * u} ${yCorpo + 23 * u}" stroke="${mc}" stroke-width="${5 * u}" stroke-linecap="round" fill="none"/>`);
    }
  }

  // ---- braços com MÃOS REDONDAS (sempre visíveis, como no modelo)
  const BR = {
    parado: [[-25, 20], [25, 20]], olhando: [[-25, 18], [27, 10]], carregando: [[-26, 4], [26, 4]],
    andando: [[-26 - passo * 7, 16], [26 + passo * 7, 16]], correndo: [[-31 - passo * 9, 4], [31 + passo * 9, 4]],
    agachado: [[-27, 10], [27, 10]], batendo: [[-25, 20], [28, -20]], apontando: [[-25, 20], [35, -8]],
    assustado: [[-29, -16], [29, -16]], pensando: [[-25, 20], [16, -14]], segurando: [[-25, 20], [14, -2]],
  }[pose] || [[-25, 20], [25, 20]];
  const corBraco = roupa === "regata" ? pele : cor;
  for (const [dx, dy] of BR) {
    const ox = x + (dx > 0 ? larg / 2.6 : -larg / 2.6) * u;
    p.push(`<path d="M${ox} ${yCorpo + 9 * u} L${x + dx * u} ${yCorpo + (9 + dy) * u}" stroke="${corBraco}" stroke-width="${9.5 * u}" fill="none" stroke-linecap="round"/>`);
    p.push(`<circle cx="${x + dx * u}" cy="${yCorpo + (9 + dy) * u}" r="${4.8 * u}" fill="${pele}"/>`);
  }

  // ---- cabeça REDONDA com o cabelo de tigela (e a faixa mais clara do modelo)
  p.push(`<circle cx="${x}" cy="${yCab}" r="${cabR}" fill="${pele}"/>`);
  if (cabelo !== "none" && !q.bone) {
    p.push(`<path d="M${x - cabR} ${yCab + cabR * 0.1} a${cabR} ${cabR} 0 0 1 ${cabR * 2} 0 l${-cabR * 0.17} 0 a${cabR * 0.83} ${cabR * 0.52} 0 0 0 ${-cabR * 1.66} 0 z" fill="${cabelo}"/>`);
    p.push(`<path d="M${x - cabR} ${yCab + cabR * 0.1} a${cabR} ${cabR} 0 0 1 ${cabR * 2} 0 l0 ${-cabR * 0.5} a${cabR} ${cabR} 0 0 0 ${-cabR * 2} 0 z" fill="${cabelo}"/>`);
    p.push(`<path d="M${x - cabR * 0.97} ${yCab - cabR * 0.17} a${cabR} ${cabR} 0 0 1 ${cabR * 1.94} 0" stroke="${tom(cabelo, 0.3)}" stroke-width="${cabR * 0.14}" fill="none"/>`);
  }
  if (q.bone) {
    const bc = q.cor_bone || "#c0392b";
    p.push(`<path d="M${x - cabR} ${yCab - cabR * 0.1} a${cabR} ${cabR} 0 0 1 ${cabR * 2} 0 z" fill="${bc}"/>`);
    p.push(`<rect x="${x - cabR * 1.05}" y="${yCab - cabR * 0.17}" width="${cabR * 2.1}" height="${cabR * 0.2}" rx="${cabR * 0.1}" fill="${tom(bc, -0.2)}"/>`);
    p.push(`<path d="M${x + cabR * 0.9} ${yCab - cabR * 0.14} q${cabR * 0.7} ${cabR * 0.06} ${cabR * 0.72} ${cabR * 0.2} l${-cabR * 0.72} 0 z" fill="${tom(bc, -0.2)}"/>`);
  }

  // ---- olhos GRANDES ovais (sem branco), piscando sozinhos
  const pisca = (t * 1000 + (q.x || 0) * 3000) % 3400 < 130;
  const ox = olh * 2.6 * u;
  const oy = yCab + cabR * 0.14;
  const orx = 4.3 * u;
  const ory = 5.6 * u;
  for (const lado of [-1, 1]) {
    const cx = x + lado * 8.6 * u + ox;
    if (pisca) p.push(`<rect x="${cx - orx}" y="${oy - 0.9 * u}" width="${orx * 2}" height="${1.9 * u}" rx="${0.95 * u}" fill="#2b2b2b"/>`);
    else p.push(`<ellipse cx="${cx}" cy="${oy}" rx="${orx}" ry="${ory}" fill="#2b2b2b"/>`);
  }
  // sobrancelhas finas e curvas — sempre presentes (o modelo tem), inclinadas pela cara
  const cara = q.cara || "";
  const inc = cara === "bravo" ? 3.4 : cara === "assustado" ? -3.0 : cara === "serio" ? 1.2 : 0;
  for (const lado of [-1, 1]) {
    const cx = x + lado * 8.6 * u + ox;
    const dy = inc * lado * -1 * u;
    p.push(`<path d="M${cx - 4.6 * u} ${oy - 8.6 * u + dy * 0.2} q${4.6 * u} ${-2.6 * u} ${9.2 * u} ${dy}" stroke="${tom(cabelo === "none" ? "#5a3b26" : cabelo, -0.1)}" stroke-width="${2 * u}" stroke-linecap="round" fill="none"/>`);
  }
  // boca: fala (abre e fecha) ou a cara da cena — sempre desenhada
  if (q.falando) {
    const a = (0.5 + 0.5 * Math.sin(t * 17)) * 4.2 * u + 1.4 * u;
    p.push(`<ellipse cx="${x + ox * 0.5}" cy="${oy + 10 * u}" rx="${3.6 * u}" ry="${a}" fill="#2b2b2b"/>`);
  } else if (cara === "feliz") {
    p.push(`<path d="M${x - 4.4 * u + ox * 0.5} ${oy + 9 * u} q${4.4 * u} ${4.4 * u} ${8.8 * u} 0" stroke="#2b2b2b" stroke-width="${2 * u}" fill="none" stroke-linecap="round"/>`);
  } else if (cara === "assustado") {
    p.push(`<ellipse cx="${x + ox * 0.5}" cy="${oy + 10 * u}" rx="${2.9 * u}" ry="${3.8 * u}" fill="#2b2b2b"/>`);
  } else {
    p.push(`<ellipse cx="${x + ox * 0.5}" cy="${oy + 10 * u}" rx="${2.8 * u}" ry="${2.1 * u}" fill="#2b2b2b"/>`);
  }
  // lanterna na mão (cena escura)
  if (q.lanterna) {
    const lx = x + 28 * u;
    const ly = yCorpo + 22 * u;
    p.push(`<rect x="${lx - 4 * u}" y="${ly - 3 * u}" width="${13 * u}" height="${6 * u}" rx="${2 * u}" fill="#3b4350"/>
      <path d="M${lx + 9 * u} ${ly - 3 * u} L${lx + 52 * u} ${ly - 22 * u} L${lx + 52 * u} ${ly + 22 * u} L${lx + 9 * u} ${ly + 3 * u} z" fill="#ffe9a8" opacity=".32"/>`);
  }
  return p.join("");
}

/** figurante: silhueta preta (a multidão do estilo) */
function silhueta(x, y, alt, t, i = 0) {
  const u = alt / 100;
  const s = Math.sin(t * 5 + i * 1.7);
  return `<g fill="#1d1d20" stroke="#1d1d20">
    <path d="M${x - 5 * u} ${y - 28 * u} L${x - 5 * u + s * 11 * u} ${y}" stroke-width="${8 * u}" stroke-linecap="round" fill="none"/>
    <path d="M${x + 5 * u} ${y - 28 * u} L${x + 5 * u - s * 11 * u} ${y}" stroke-width="${8 * u}" stroke-linecap="round" fill="none"/>
    <rect x="${x - 13 * u}" y="${y - 62 * u}" width="${26 * u}" height="${36 * u}" rx="${10 * u}"/>
    <path d="M${x - 12 * u} ${y - 54 * u} L${x - 20 * u - s * 6 * u} ${y - 38 * u}" stroke-width="${7.5 * u}" stroke-linecap="round" fill="none"/>
    <path d="M${x + 12 * u} ${y - 54 * u} L${x + 20 * u + s * 6 * u} ${y - 38 * u}" stroke-width="${7.5 * u}" stroke-linecap="round" fill="none"/>
    <circle cx="${x}" cy="${y - 76 * u}" r="${15 * u}"/></g>`;
}

/** gato simples (a "Paçoca" de toda história) — o rabo balança */
function gato(g, t) {
  const x = g.x * W;
  const y = g.y * H;
  const u = (g.alt || 150) / 70;
  const cor = g.cor || "#d98e3a";
  const rabo = Math.sin(t * 2.6) * 7 * u;
  return `<g><ellipse cx="${x}" cy="${y - 14 * u}" rx="${26 * u}" ry="${15 * u}" fill="${cor}"/>
    <circle cx="${x - 24 * u}" cy="${y - 28 * u}" r="${12 * u}" fill="${cor}"/>
    <path d="M${x - 32 * u} ${y - 36 * u} l${4 * u} ${-10 * u} l${7 * u} ${7 * u} z" fill="${cor}"/>
    <path d="M${x - 18 * u} ${y - 38 * u} l${3 * u} ${-9 * u} l${6 * u} ${8 * u} z" fill="${cor}"/>
    <circle cx="${x - 28 * u}" cy="${y - 29 * u}" r="${1.8 * u}" fill="#2b2b2b"/>
    <circle cx="${x - 20 * u}" cy="${y - 29 * u}" r="${1.8 * u}" fill="#2b2b2b"/>
    <path d="M${x + 24 * u} ${y - 18 * u} q${14 * u} ${-6 * u} ${8 + rabo}  ${-20 * u}" stroke="${cor}" stroke-width="${6 * u}" fill="none" stroke-linecap="round"/>
    <rect x="${x - 20 * u}" y="${y - 4 * u}" width="${7 * u}" height="${6 * u}" fill="${cor}"/>
    <rect x="${x + 6 * u}" y="${y - 4 * u}" width="${7 * u}" height="${6 * u}" fill="${cor}"/></g>`;
}

/* ---------------------------------------------------------------- objetos (alguns animados) */
const OBJ = {
  balde: (x, y, s, o, t) => {
    const nivel = o.enchendo ? Math.min(1, (t - (o.desde || 0)) / 3) : (o.cheio === false ? 0 : 0.8);
    const h = 44 * s * nivel;
    return `<path d="M${x - 32 * s} ${y - 46 * s} L${x - 26 * s} ${y} L${x + 26 * s} ${y} L${x + 32 * s} ${y - 46 * s} z" fill="#4a7fb5"/>
      ${nivel > 0.02 ? `<path d="M${x - 26 * s - h * 0.14} ${y - h} L${x + 26 * s + h * 0.14} ${y - h} L${x + 25 * s} ${y - 2 * s} L${x - 25 * s} ${y - 2 * s} z" fill="#7cc4e8"/>` : ""}
      <rect x="${x - 32 * s}" y="${y - 52 * s}" width="${64 * s}" height="${8 * s}" rx="${3 * s}" fill="#3d6c9c"/>`;
  },
  banheira: (x, y, s, o, t) => {
    const nivel = o.enchendo ? Math.min(1, (t - (o.desde || 0)) / 4) : 1;
    const hh = 40 * s * nivel;
    return `<rect x="${x - 150 * s}" y="${y - 70 * s}" width="${300 * s}" height="${70 * s}" rx="${26 * s}" fill="#e9eef2"/>
      <rect x="${x - 136 * s}" y="${y - 8 * s - hh}" width="${272 * s}" height="${hh}" rx="${10 * s}" fill="#7cc4e8"/>
      <rect x="${x + 108 * s}" y="${y - 120 * s}" width="${9 * s}" height="${52 * s}" fill="#b9c3cb"/>
      <rect x="${x + 86 * s}" y="${y - 124 * s}" width="${40 * s}" height="${9 * s}" rx="${4 * s}" fill="#b9c3cb"/>
      ${o.enchendo && nivel < 1 ? `<rect x="${x + 110 * s}" y="${y - 112 * s}" width="${5 * s}" height="${100 * s - hh}" fill="#7cc4e8" opacity=".8"/>` : ""}`;
  },
  vela: (x, y, s, o, t) => {
    const f = 1 + Math.sin(t * 9) * 0.16;
    return `<rect x="${x - 11 * s}" y="${y - 40 * s}" width="${22 * s}" height="${40 * s}" rx="${4 * s}" fill="#f2e7cf"/>
      <ellipse cx="${x}" cy="${y - 54 * s}" rx="${8 * s / f}" ry="${15 * s * f}" fill="#ffb648"/>
      <ellipse cx="${x}" cy="${y - 50 * s}" rx="${4 * s / f}" ry="${8 * s * f}" fill="#fff2b8"/>`;
  },
  celular: (x, y, s, o, t) => {
    const pisca = o.alerta ? (Math.sin(t * 6) > -0.2 ? 1 : 0.25) : 1;
    return `<rect x="${x - 52 * s}" y="${y - 104 * s}" width="${104 * s}" height="${196 * s}" rx="${16 * s}" fill="#1b1f27" stroke="#3b4350" stroke-width="${3 * s}"/>
      <rect x="${x - 44 * s}" y="${y - 94 * s}" width="${88 * s}" height="${176 * s}" rx="${10 * s}" fill="${o.extra ? "#2a1013" : "#0e1117"}"/>
      ${o.extra ? `<g opacity="${pisca}"><rect x="${x - 38 * s}" y="${y - 70 * s}" width="${76 * s}" height="${44 * s}" rx="${7 * s}" fill="#c0392b"/>
        <text x="${x}" y="${y - 44 * s}" text-anchor="middle" font-family="Inter,sans-serif" font-weight="900" font-size="${14 * s}" fill="#fff">${esc(o.extra)}</text></g>` : ""}`;
  },
  porta: (x, y, s, o, t) => {
    const tr = o.batendo ? Math.sin(t * 26) * 2.6 * s : 0;
    return `<g transform="translate(${tr},0)"><rect x="${x - 60 * s}" y="${y - 210 * s}" width="${120 * s}" height="${210 * s}" rx="${5 * s}" fill="${o.aberta ? "#1a1f27" : "#6b4b31"}"/>
      ${o.aberta ? "" : `<circle cx="${x + 40 * s}" cy="${y - 100 * s}" r="${7 * s}" fill="#d8b24a"/>
        <rect x="${x - 46 * s}" y="${y - 196 * s}" width="${92 * s}" height="${80 * s}" rx="${4 * s}" fill="none" stroke="#573c26" stroke-width="${4 * s}"/>`}</g>`;
  },
  caixa: (x, y, s) => `<rect x="${x - 44 * s}" y="${y - 62 * s}" width="${88 * s}" height="${62 * s}" fill="#c08a4e"/>
    <rect x="${x - 44 * s}" y="${y - 62 * s}" width="${88 * s}" height="${12 * s}" fill="#a3703c"/>`,
  moto: (x, y, s) => `<circle cx="${x - 52 * s}" cy="${y - 26 * s}" r="${26 * s}" fill="none" stroke="#2c3e50" stroke-width="${8 * s}"/>
    <circle cx="${x + 52 * s}" cy="${y - 26 * s}" r="${26 * s}" fill="none" stroke="#2c3e50" stroke-width="${8 * s}"/>
    <path d="M${x - 52 * s} ${y - 26 * s} L${x - 10 * s} ${y - 58 * s} L${x + 40 * s} ${y - 56 * s} L${x + 52 * s} ${y - 26 * s}" stroke="#c0392b" stroke-width="${11 * s}" fill="none" stroke-linejoin="round"/>
    <rect x="${x - 26 * s}" y="${y - 76 * s}" width="${54 * s}" height="${16 * s}" rx="${7 * s}" fill="#2c3e50"/>`,
  carro: (x, y, s, o) => {
    const cor = o.cor || "#3b6ea5";
    return `<rect x="${x - 95 * s}" y="${y - 54 * s}" width="${190 * s}" height="${40 * s}" rx="${13 * s}" fill="${cor}"/>
      <path d="M${x - 62 * s} ${y - 54 * s} L${x - 44 * s} ${y - 86 * s} L${x + 46 * s} ${y - 86 * s} L${x + 64 * s} ${y - 54 * s} z" fill="${cor}"/>
      <path d="M${x - 50 * s} ${y - 58 * s} L${x - 38 * s} ${y - 80 * s} L${x + 40 * s} ${y - 80 * s} L${x + 52 * s} ${y - 58 * s} z" fill="#cfe0ee" opacity=".8"/>
      <circle cx="${x - 56 * s}" cy="${y - 12 * s}" r="${16 * s}" fill="#22282f"/><circle cx="${x + 56 * s}" cy="${y - 12 * s}" r="${16 * s}" fill="#22282f"/>`;
  },
  mochila: (x, y, s) => `<rect x="${x - 38 * s}" y="${y - 82 * s}" width="${76 * s}" height="${82 * s}" rx="${16 * s}" fill="#7a5637"/>
    <rect x="${x - 28 * s}" y="${y - 46 * s}" width="${56 * s}" height="${30 * s}" rx="${7 * s}" fill="#5f4129"/>
    <rect x="${x - 14 * s}" y="${y - 94 * s}" width="${28 * s}" height="${16 * s}" rx="${7 * s}" fill="#5f4129"/>`,
  escada: (x, y, s) => Array.from({ length: 6 }, (_, i) =>
    `<rect x="${x - 70 * s + i * 22 * s}" y="${y - i * 34 * s - 30 * s}" width="${110 * s}" height="${30 * s}" fill="#9aa3ab"/>`).join(""),
  torneira: (x, y, s, o, t) => {
    const g = ((t * 1.5) % 1);
    return `<rect x="${x - 7 * s}" y="${y - 96 * s}" width="${14 * s}" height="${60 * s}" fill="#b9c3cb"/>
      <path d="M${x} ${y - 96 * s} q0 ${-40 * s} ${50 * s} ${-40 * s}" stroke="#b9c3cb" stroke-width="${14 * s}" fill="none"/>
      ${o.seca ? "" : o.jorrando
        ? `<rect x="${x - 4 * s}" y="${y - 34 * s}" width="${8 * s}" height="${34 * s}" fill="#7cc4e8"/>`
        : `<circle cx="${x}" cy="${y - 34 * s + g * 34 * s}" r="${6 * s}" fill="#7cc4e8" opacity="${1 - g * 0.5}"/>`}`;
  },
  // relógio de parede: o ponteiro anda (bom para os closes de apoio)
  relogio: (x, y, s, o, t) => {
    const ang = (t * 0.9) % (Math.PI * 2);
    return `<circle cx="${x}" cy="${y}" r="${58 * s}" fill="#f4efe2" stroke="#2e2a26" stroke-width="${7 * s}"/>
      <line x1="${x}" y1="${y}" x2="${x}" y2="${y - 36 * s}" stroke="#2e2a26" stroke-width="${6 * s}" stroke-linecap="round"/>
      <line x1="${x}" y1="${y}" x2="${x + Math.sin(ang) * 46 * s}" y2="${y - Math.cos(ang) * 46 * s}" stroke="#c0392b" stroke-width="${4 * s}" stroke-linecap="round"/>
      <circle cx="${x}" cy="${y}" r="${5 * s}" fill="#2e2a26"/>`;
  },
  garrafa: (x, y, s) => `<rect x="${x - 20 * s}" y="${y - 96 * s}" width="${40 * s}" height="${96 * s}" rx="${10 * s}" fill="#5a8f9c"/>
    <rect x="${x - 11 * s}" y="${y - 114 * s}" width="${22 * s}" height="${22 * s}" rx="${5 * s}" fill="#36606b"/>
    <rect x="${x - 20 * s}" y="${y - 58 * s}" width="${40 * s}" height="${14 * s}" fill="#cfd8d5"/>`,
};

/* ---------------------------------------------------------------- cenários (desenhados UMA vez por cena) */
function predios(p, n, base, acesas, semente) {
  const r = (i) => ((Math.sin(semente * 99 + i * 37.7) + 1) / 2);
  const out = [];
  for (let i = 0; i < n; i++) {
    const w = 110 + r(i) * 110;
    const x = (i * (W + 120)) / n - 60;
    const h = 190 + r(i + 50) * 430 + (i % 3 === 0 ? 160 : 0);
    out.push(`<rect x="${x}" y="${base - h}" width="${w}" height="${h}" fill="${i % 2 ? p.predio : p.predio2}"/>`);
    for (let a = 0; a < Math.floor(h / 74); a++) {
      for (let b = 0; b < Math.floor(w / 46); b++) {
        const on = r(i * 77 + a * 13 + b * 5) < acesas;
        out.push(`<rect x="${x + 14 + b * 46}" y="${base - h + 24 + a * 74}" width="26" height="34" fill="${on ? p.vidroOn : p.vidro}"/>`);
      }
    }
  }
  return out.join("");
}

/** O PRÉDIO DA HISTÓRIA, com os andares contados de baixo para cima e o ANDAR DA CENA marcado.
    `andar` (ex. 12) e `andares` (ex. 15) vêm do roteiro: a janela do andar acende, ganha seta e o rótulo "12º ANDAR",
    e os vizinhos ficam apagados. É o que faz o público ENTENDER onde a pessoa está. */
function predioAndares(p, c) {
  const total = Math.max(4, Math.min(24, Number(c.andares) || 15));
  const alvo = Math.max(1, Math.min(total, Number(c.andar) || 0));
  const topo = H * 0.09;
  const base = H * 0.88;
  const hA = (base - topo) / total;
  const px = W * 0.2;
  const pw = W * 0.6;
  const out = [`<rect width="${W}" height="${H}" fill="${p.ceu}"/>`, predios(p, 4, base, 0.06, (c.semente || 1) + 3)];
  out.push(`<rect x="${px}" y="${topo}" width="${pw}" height="${base - topo}" fill="${p.predio}"/>`);
  out.push(`<rect x="${px}" y="${topo - 18}" width="${pw}" height="18" fill="${p.predio2}"/>`);
  for (let a = 0; a < total; a++) {
    const andar = total - a;                          // desenha de cima para baixo, numera de baixo para cima
    const y = topo + a * hA;
    const marcado = andar === alvo;
    out.push(`<rect x="${px}" y="${y + hA - 3}" width="${pw}" height="3" fill="rgba(0,0,0,.18)"/>`);
    for (let b = 0; b < 4; b++) {
      const jx = px + pw * 0.08 + b * (pw * 0.23);
      const jw = pw * 0.16;
      const jh = Math.min(hA * 0.56, 70);
      const on = marcado || ((a * 4 + b) % 7 === 0 && !alvo);
      out.push(`<rect x="${jx}" y="${y + hA * 0.2}" width="${jw}" height="${jh}" fill="${on ? p.vidroOn : p.vidro}"/>`);
    }
    if (marcado) {
      // a etiqueta fica DENTRO do prédio: na borda ela some quando a câmera dá zoom
      out.push(`<rect x="${px - 6}" y="${y}" width="${pw + 12}" height="${hA}" fill="none" stroke="#ffd400" stroke-width="8"/>`);
      const eh = Math.min(hA * 0.78, 86);
      const ey = y + (hA - eh) / 2;
      const ew = 236;
      out.push(`<rect x="${px + 18}" y="${ey}" width="${ew}" height="${eh}" rx="10" fill="#ffd400"/>`);
      out.push(`<path d="M${px + 18 + ew} ${ey + eh / 2 - 17} l26 17 l-26 17 z" fill="#ffd400"/>`);
      out.push(`<text x="${px + 18 + ew / 2}" y="${ey + eh * 0.74}" text-anchor="middle" font-family="Anton,sans-serif" font-size="${eh * 0.66}" fill="#1a1c20">${andar}º ANDAR</text>`);
    } else if (andar % 3 === 0) {
      out.push(`<text x="${px + pw + 16}" y="${y + hA * 0.68}" font-family="Inter,sans-serif" font-weight="900" font-size="24" fill="${p.tinta}" opacity=".45">${andar}</text>`);
    }
  }
  out.push(`<rect y="${base}" width="${W}" height="${H - base}" fill="${p.chao}"/>`);
  return out.join("");
}

const CENARIO = {
  cidade: (p, c) => `<rect width="${W}" height="${H}" fill="${p.ceu}"/>${predios(p, 7, H * 0.7, c.luz === "noite" ? 0.2 : c.luz === "escuro" ? 0.02 : 0.08, c.semente)}
    <rect y="${H * 0.7}" width="${W}" height="${H * 0.3}" fill="${p.chao}"/>`,
  predio: (p, c) => predioAndares(p, c),
  quarto: (p) => `<rect width="${W}" height="${H}" fill="${p.parede}"/>
    <rect y="${H * 0.6}" width="${W}" height="${H * 0.4}" fill="${p.rodape}"/>
    <rect y="${H * 0.6}" width="${W}" height="14" fill="rgba(0,0,0,.14)"/>
    <rect x="${W * 0.1}" y="${H * 0.2}" width="${W * 0.34}" height="${H * 0.22}" fill="#fbf7ef" stroke="${p.tinta}" stroke-width="8"/>
    <rect x="${W * 0.1}" y="${H * 0.308}" width="${W * 0.34}" height="8" fill="${p.tinta}"/>
    <rect x="${W * 0.267}" y="${H * 0.2}" width="8" height="${H * 0.22}" fill="${p.tinta}"/>`,
  janela: (p, c) => `<rect width="${W}" height="${H}" fill="${p.parede}"/>
    <defs><clipPath id="vidro"><rect x="${W * 0.14}" y="${H * 0.14}" width="${W * 0.72}" height="${H * 0.42}"/></clipPath></defs>
    <rect x="${W * 0.14}" y="${H * 0.14}" width="${W * 0.72}" height="${H * 0.42}" fill="${p.ceu}"/>
    <g clip-path="url(#vidro)">${predios(p, 5, H * 0.56, c.luz === "escuro" ? 0.03 : 0.2, c.semente + 9)}</g>
    <rect x="${W * 0.14}" y="${H * 0.14}" width="${W * 0.72}" height="${H * 0.42}" fill="none" stroke="${p.tinta}" stroke-width="12"/>
    <rect x="${W * 0.49}" y="${H * 0.14}" width="12" height="${H * 0.42}" fill="${p.tinta}"/>
    <rect y="${H * 0.66}" width="${W}" height="${H * 0.34}" fill="${p.rodape}"/>`,
  banheiro: (p) => `<rect width="${W}" height="${H}" fill="#e2e7e4"/>
    <rect y="${H * 0.66}" width="${W}" height="${H * 0.34}" fill="#c9d0cd"/>
    ${Array.from({ length: 9 }, (_, i) => `<rect x="${i * 120}" y="0" width="4" height="${H * 0.66}" fill="rgba(0,0,0,.05)"/>`).join("")}`,
  corredor: (p) => `<rect width="${W}" height="${H}" fill="${p.parede}"/>
    <path d="M0 0 L${W * 0.28} ${H * 0.26} L${W * 0.28} ${H * 0.7} L0 ${H}" fill="rgba(0,0,0,.14)"/>
    <path d="M${W} 0 L${W * 0.72} ${H * 0.26} L${W * 0.72} ${H * 0.7} L${W} ${H}" fill="rgba(0,0,0,.14)"/>
    <rect y="${H * 0.66}" width="${W}" height="${H * 0.34}" fill="${p.rodape}"/>`,
  rua: (p, c) => `<rect width="${W}" height="${H}" fill="${p.ceu}"/>${predios(p, 6, H * 0.58, c.luz === "escuro" ? 0.02 : 0.12, c.semente + 2)}
    <rect y="${H * 0.58}" width="${W}" height="${H * 0.42}" fill="#4a4a4c"/>
    <rect y="${H * 0.58}" width="${W}" height="26" fill="${p.rodape}"/>
    ${Array.from({ length: 5 }, (_, i) => `<rect x="${60 + i * 230}" y="${H * 0.8}" width="120" height="16" fill="#e8e2d2" opacity=".7"/>`).join("")}`,
  laje: (p, c) => `<rect width="${W}" height="${H}" fill="${p.ceu}"/>${predios(p, 6, H * 0.54, 0.1, c.semente + 5)}
    <rect y="${H * 0.54}" width="${W}" height="${H * 0.46}" fill="${p.rodape}"/>
    <rect y="${H * 0.5}" width="${W}" height="${H * 0.05}" fill="${p.predio}"/>`,
  garagem: (p) => `<rect width="${W}" height="${H}" fill="#3a3f45"/>
    <rect y="${H * 0.72}" width="${W}" height="${H * 0.28}" fill="#2b3036"/>
    ${Array.from({ length: 4 }, (_, i) => `<rect x="${i * 290 + 30}" y="${H * 0.18}" width="14" height="${H * 0.54}" fill="#474d55"/>`).join("")}`,
  escadaria: (p) => `<rect width="${W}" height="${H}" fill="${p.parede}"/>
    ${Array.from({ length: 9 }, (_, i) => `<rect x="${W * 0.1 + i * 36}" y="${H * 0.42 + i * 68}" width="${W * 0.8 - i * 36}" height="68" fill="${i % 2 ? p.rodape : p.chao}"/>`).join("")}
    <rect x="${W * 0.06}" y="0" width="18" height="${H}" fill="rgba(0,0,0,.12)"/>`,
  mercado: (p) => `<rect width="${W}" height="${H}" fill="#e8e3d6"/>
    ${Array.from({ length: 3 }, (_, i) => `<rect x="60" y="${H * 0.26 + i * 150}" width="${W - 120}" height="20" fill="#b9a98c"/>
      ${Array.from({ length: 9 }, (_, b) => `<rect x="${80 + b * 100}" y="${H * 0.26 + i * 150 - 54}" width="56" height="54" rx="5" fill="${["#c0392b", "#3b6ea5", "#d8a43a", "#4b8b5a"][(i + b) % 4]}"/>`).join("")}`).join("")}
    <rect y="${H * 0.72}" width="${W}" height="${H * 0.28}" fill="#cfc7b4"/>`,
  escuro: () => `<rect width="${W}" height="${H}" fill="#14161a"/>`,
};

/* ---------------------------------------------------------------- efeitos animados (camada de cima) */
function chuva(t, semente, n = 130) {
  const r = (i) => ((Math.sin(semente * 13 + i * 77.3) + 1) / 2);
  const out = [];
  for (let i = 0; i < n; i++) {
    const vel = 900 + r(i) * 700;
    const x = r(i) * W - ((t * 180) % 200);
    const y = (r(i + 999) * H + t * vel) % (H + 120) - 60;
    out.push(`<line x1="${r2(x)}" y1="${r2(y)}" x2="${r2(x - 16)}" y2="${r2(y + 46)}" stroke="#dfe9ef" stroke-width="3" opacity=".42"/>`);
  }
  return out.join("");
}

function fumaca(t, semente, n = 9) {
  const r = (i) => ((Math.sin(semente * 31 + i * 51.1) + 1) / 2);
  return Array.from({ length: n }, (_, i) => {
    const d = (t * 0.12 + r(i)) % 1;
    const x = r(i) * W;
    return `<circle cx="${r2(x + Math.sin(t * 0.6 + i) * 40)}" cy="${r2(H * 0.5 - d * H * 0.45)}" r="${r2(40 + r(i + 7) * 60 + d * 70)}" fill="#8e8e8e" opacity="${r2((1 - d) * 0.3)}"/>`;
  }).join("");
}

/* ---------------------------------------------------------------- montagem */
const PLANO = { geral: 1.04, medio: 1.3, close: 1.85 };

const CENA = {
  monta(cena) {
    const c = cena || {};
    this._c = c;
    const p = LUZ[c.luz] || LUZ.noite;
    this._p = p;
    const fundo = (CENARIO[c.cenario] || CENARIO.quarto)(p, c);
    document.getElementById("fundo").innerHTML =
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">${fundo}
       ${p.veu ? `<rect width="${W}" height="${H}" fill="${p.veu}"/>` : ""}</svg>`;
    const topo = document.getElementById("topo");
    if (c.relogio || c.contador) {
      topo.style.display = "flex";
      topo.innerHTML = (c.selo ? `<div class="selo">${esc(c.selo)}</div>` : "")
        + (c.relogio ? `<div class="hora">${esc(c.relogio)}</div>` : "")
        + (c.contador ? `<div class="cont"><b>${esc(c.contador)}</b>${c.contador_sub ? `<span>${esc(c.contador_sub)}</span>` : ""}</div>` : "");
    } else topo.style.display = "none";
    const ono = document.getElementById("ono");
    ono.textContent = c.onomatopeia || "";
    ono.style.display = c.onomatopeia ? "block" : "none";
    if (c.onomatopeia) {
      ono.style.left = `${(c.ono_x == null ? 0.62 : c.ono_x) * 100}%`;
      ono.style.top = `${(c.ono_y == null ? 0.3 : c.ono_y) * 100}%`;
    }
    // CARTELA DE ESCOLHA (o fim de todo episódio: é ela que traz o comentário e o próximo episódio)
    const el = document.getElementById("escolha");
    const e = c.escolha;
    if (e && (e.a || e.b)) {
      el.style.display = "flex";
      el.innerHTML = `<div class="perg">${esc(e.pergunta || "O QUE ELE FAZ AGORA?")}</div>
        <div class="op"><i>A</i><span>${esc(e.a || "")}</span></div>
        <div class="op b"><i>B</i><span>${esc(e.b || "")}</span></div>
        <div class="cta">COMENTA <b>A</b> OU <b>B</b> 👇</div>`;
    } else el.style.display = "none";
    this.legenda("");
    this.anima(0, 0);
  },

  legenda(txt) {
    const el = document.getElementById("leg");
    const t = String(txt || "").trim();
    el.style.display = t ? "block" : "none";
    el.innerHTML = esc(t.toUpperCase()).replace(/\*([^*]+)\*/g, "<em>$1</em>").replace(/\*/g, "");
  },

  /** p = 0..1 dentro da cena (movimento de câmera); t = segundos (animação dos atores) */
  anima(p, t) {
    const c = this._c || {};
    const q = Math.max(0, Math.min(1, p));
    const m = c.movimento || "zoom";
    // o PLANO decide o tamanho: geral (a cena), médio (a pessoa) e close (o detalhe — é o "corte de apoio" do formato)
    const z = PLANO[c.plano] || PLANO.geral;
    const fx = c.foco && c.foco.x != null ? c.foco.x : 0.5;
    const fy = c.foco && c.foco.y != null ? c.foco.y : 0.5;
    let tr = `scale(${z})`;
    if (m === "zoom") tr = `scale(${z + q * 0.1})`;
    else if (m === "afasta") tr = `scale(${z + 0.12 - q * 0.1})`;
    else if (m === "direita") tr = `scale(${z + 0.08}) translateX(${(0.5 - q) * 5}%)`;
    else if (m === "esquerda") tr = `scale(${z + 0.08}) translateX(${(q - 0.5) * 5}%)`;
    else if (m === "sobe") tr = `scale(${z + 0.08}) translateY(${(q - 0.5) * 5}%)`;
    else if (m === "desce") tr = `scale(${z + 0.08}) translateY(${(0.5 - q) * 5}%)`;
    // tremor (porta batendo, explosão, susto)
    if (c.tremor) {
      const k = Math.max(0, 1 - q * 1.6);
      tr += ` translate(${r2(Math.sin(t * 40) * 9 * k)}px, ${r2(Math.cos(t * 37) * 7 * k)}px)`;
    }
    const fundoEl = document.getElementById("fundo");
    const atoresEl = document.getElementById("atores");
    fundoEl.style.transformOrigin = `${fx * 100}% ${fy * 100}%`;
    atoresEl.style.transformOrigin = `${fx * 100}% ${fy * 100}%`;
    // PARALLAX: o fundo anda um pouco menos que os atores — é o que dá sensação de profundidade (o "motion")
    fundoEl.style.transform = `${tr} translateZ(0) scale(0.985)`;
    atoresEl.style.transform = tr;

    // ---- camada animada
    const a = [];
    if (c.fumaca) a.push(fumaca(t, c.semente || 3));
    for (const o of c.objetos || []) {
      const f = OBJ[o.tipo];
      if (f) a.push(`<g opacity="${o.opacidade == null ? 1 : o.opacidade}">${f(o.x * W, o.y * H, o.s == null ? 1 : o.s, o, t)}</g>`);
    }
    // quem anda vai de `x` até `x2` ao longo da cena (pelo progresso, não pelo relógio: nunca some da tela)
    const desloca = (o) => (o.x2 == null ? o.x : o.x + (o.x2 - o.x) * q);
    for (const [i, s] of (c.silhuetas || []).entries()) {
      a.push(silhueta(desloca(s) * W, s.y * H, s.alt || 300, t, i));
    }
    for (const g of c.gatos || []) a.push(gato({ ...g, x: desloca(g) }, t));
    for (const pe of c.pessoas || []) a.push(pessoa({ ...pe, x: desloca(pe) }, t));
    if (c.chuva) a.push(chuva(t, c.semente || 3));
    if (c.escurece) a.push(`<rect width="${W}" height="${H}" fill="#000" opacity="${r2(Math.min(0.82, q * 1.4))}"/>`);
    if (c.clarao) a.push(`<rect width="${W}" height="${H}" fill="#fff" opacity="${r2(Math.max(0, 0.85 - q * 4))}"/>`);
    atoresEl.innerHTML =
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">${a.join("")}</svg>`;

    // a cartela A/B entra em partes (pergunta → A → B → chamada) e a chamada pulsa: é o que segura o comentário
    if (c.escolha) {
      const el = document.getElementById("escolha");
      const partes = el.querySelectorAll(".perg, .op, .cta");
      partes.forEach((n, i) => {
        const ini = 0.06 + i * 0.13;
        const k = Math.max(0, Math.min(1, (q - ini) / 0.16));
        n.style.opacity = String(k);
        const lado = n.classList.contains("op") ? (n.classList.contains("b") ? 1 : -1) : 0;
        n.style.transform = `translateX(${r2((1 - k) * lado * 14)}%) translateY(${r2((1 - k) * 8)}px)`;
      });
      const cta = el.querySelector(".cta");
      if (cta && q > 0.58) cta.style.transform = `scale(${r2(1 + Math.sin(t * 7) * 0.05)})`;
    }
  },
};

window.CENA = CENA;
window.CENA_LUZ = LUZ;
window.CENA_PESSOA = pessoa;
window.CENA_CENARIO = CENARIO;
