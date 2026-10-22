"use strict";

/**
 * PALCO DAS HISTÓRIAS — desenha cada cena por código (SVG), no estilo "flat" dos reels que viralizaram
 * (Histórias com Kaio / Contos de Stick): formas simples, cores chapadas, bonequinho, legenda grande em caixa alta,
 * relógio no canto. Desenhar por código (em vez de gerar imagem por IA) mantém o MESMO visual em todos os episódios
 * da série e é instantâneo.
 *
 * window.CENA.monta(cena) → desenha; window.CENA.anima(p) → p de 0 a 1 dentro da cena (movimento lento de câmera).
 */

const W = 1080;
const H = 1920;

/* paletas por luz: o mesmo cenário de dia, de noite, no escuro, na chuva ou no alerta vermelho */
const LUZ = {
  dia: { ceu: "#cfe3ef", fundo: "#efe6d6", parede: "#efe6d6", chao: "#8b6b4a", predio: "#c9c3b6", vidro: "#aebfc9", tinta: "#2e2a26", veu: "none" },
  tarde: { ceu: "#f3cfa0", fundo: "#efe0cb", parede: "#efe0cb", chao: "#7d5f42", predio: "#c2b49e", vidro: "#d9b48a", tinta: "#2e2a26", veu: "rgba(255,160,60,.10)" },
  noite: { ceu: "#28384f", fundo: "#31425c", parede: "#3a4a63", chao: "#202c3e", predio: "#425573", vidro: "#ffd98a", tinta: "#e8e4dc", veu: "rgba(10,16,30,.12)" },
  escuro: { ceu: "#1b2534", fundo: "#222d3e", parede: "#273345", chao: "#17202c", predio: "#2e3b4f", vidro: "#5d6e86", tinta: "#d8d4cc", veu: "rgba(0,0,0,.18)" },
  chuva: { ceu: "#5b6872", fundo: "#6b7680", parede: "#6e7a85", chao: "#3f474f", predio: "#5a656f", vidro: "#8d9aa4", tinta: "#f0ece4", veu: "rgba(90,110,130,.22)" },
  alerta: { ceu: "#2a1216", fundo: "#2e1418", parede: "#331619", chao: "#1a0c0e", predio: "#3a1a1e", vidro: "#ff6b6b", tinta: "#f6e9e9", veu: "rgba(190,30,40,.22)" },
};

const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

/* ---------------------------------------------------------------- bonequinho */
/** pessoa simples (o "stick" com corpo), em poses. x,y = pés; alt = altura em px */
function pessoa(x, y, alt, pose = "parado", cor = "#3f6f7a", pele = "#f0cdab", olhando = 1) {
  const u = alt / 100; // unidade
  const cab = 17 * u;
  const corpoY = y - 62 * u;
  const p = [];
  const bracos = {
    parado: [[-12, 18], [12, 18]],
    olhando: [[-10, 6], [13, -2]],
    carregando: [[-16, 2], [16, 2]],
    andando: [[-18, 10], [16, 22]],
    correndo: [[-26, -4], [24, 16]],
    agachado: [[-14, 8], [14, 8]],
    batendo: [[-8, 16], [20, -22]],
    apontando: [[-10, 14], [26, -10]],
  }[pose] || [[-12, 18], [12, 18]];
  const pernas = { andando: 14, correndo: 26, agachado: 0 }[pose] || 6;
  const agacha = pose === "agachado" ? 20 * u : 0;
  const cy = corpoY + agacha;
  // pernas
  if (pose !== "agachado") {
    p.push(`<path d="M${x} ${cy + 34 * u} L${x - pernas * u} ${y}" stroke="#2c3e50" stroke-width="${7 * u}" stroke-linecap="round" fill="none"/>`);
    p.push(`<path d="M${x} ${cy + 34 * u} L${x + pernas * u} ${y}" stroke="#2c3e50" stroke-width="${7 * u}" stroke-linecap="round" fill="none"/>`);
  } else {
    p.push(`<path d="M${x} ${cy + 30 * u} L${x - 16 * u} ${y - 10 * u} L${x - 20 * u} ${y}" stroke="#2c3e50" stroke-width="${7 * u}" stroke-linecap="round" fill="none"/>`);
    p.push(`<path d="M${x} ${cy + 30 * u} L${x + 16 * u} ${y - 10 * u} L${x + 20 * u} ${y}" stroke="#2c3e50" stroke-width="${7 * u}" stroke-linecap="round" fill="none"/>`);
  }
  // tronco
  p.push(`<rect x="${x - 15 * u}" y="${cy}" width="${30 * u}" height="${36 * u}" rx="${9 * u}" fill="${cor}"/>`);
  // braços
  for (const [dx, dy] of bracos) {
    p.push(`<path d="M${x + (dx > 0 ? 13 : -13) * u} ${cy + 8 * u} L${x + dx * u} ${cy + dy * u}" stroke="${cor}" stroke-width="${7 * u}" stroke-linecap="round" fill="none"/>`);
    p.push(`<circle cx="${x + dx * u}" cy="${cy + dy * u}" r="${3.6 * u}" fill="${pele}"/>`);
  }
  // cabeça + rosto
  p.push(`<circle cx="${x}" cy="${cy - cab * 0.72}" r="${cab}" fill="${pele}"/>`);
  p.push(`<path d="M${x - cab} ${cy - cab * 1.05} a${cab} ${cab} 0 0 1 ${cab * 2} 0 z" fill="#3b2d23"/>`);
  const ox = olhando * 4.2 * u;
  p.push(`<circle cx="${x - 5.5 * u + ox}" cy="${cy - cab * 0.8}" r="${2.1 * u}" fill="#2b2b2b"/>`);
  p.push(`<circle cx="${x + 5.5 * u + ox}" cy="${cy - cab * 0.8}" r="${2.1 * u}" fill="#2b2b2b"/>`);
  return p.join("");
}

/** gato simples (a "Paçoca" de toda história) */
function gato(x, y, alt = 70, cor = "#d98e3a") {
  const u = alt / 70;
  return `<g><ellipse cx="${x}" cy="${y - 14 * u}" rx="${26 * u}" ry="${15 * u}" fill="${cor}"/>
    <circle cx="${x - 24 * u}" cy="${y - 28 * u}" r="${12 * u}" fill="${cor}"/>
    <path d="M${x - 32 * u} ${y - 36 * u} l${4 * u} ${-10 * u} l${7 * u} ${7 * u} z" fill="${cor}"/>
    <path d="M${x - 18 * u} ${y - 38 * u} l${3 * u} ${-9 * u} l${6 * u} ${8 * u} z" fill="${cor}"/>
    <circle cx="${x - 28 * u}" cy="${y - 29 * u}" r="${1.8 * u}" fill="#2b2b2b"/>
    <circle cx="${x - 20 * u}" cy="${y - 29 * u}" r="${1.8 * u}" fill="#2b2b2b"/>
    <path d="M${x + 24 * u} ${y - 18 * u} q${14 * u} ${-6 * u} ${8 * u} ${-20 * u}" stroke="${cor}" stroke-width="${6 * u}" fill="none" stroke-linecap="round"/>
    <rect x="${x - 20 * u}" y="${y - 4 * u}" width="${7 * u}" height="${6 * u}" fill="${cor}"/>
    <rect x="${x + 6 * u}" y="${y - 4 * u}" width="${7 * u}" height="${6 * u}" fill="${cor}"/></g>`;
}

/* ---------------------------------------------------------------- objetos */
const OBJ = {
  balde: (x, y, s = 1, c) => `<path d="M${x - 32 * s} ${y - 46 * s} L${x - 26 * s} ${y} L${x + 26 * s} ${y} L${x + 32 * s} ${y - 46 * s} z" fill="#4a7fb5"/>
    <rect x="${x - 32 * s}" y="${y - 52 * s}" width="${64 * s}" height="${8 * s}" rx="${3 * s}" fill="#3d6c9c"/>
    ${c !== false ? `<path d="M${x - 27 * s} ${y - 30 * s} L${x + 27 * s} ${y - 30 * s} L${x + 25 * s} ${y - 2 * s} L${x - 25 * s} ${y - 2 * s} z" fill="#7cc4e8" opacity=".85"/>` : ""}`,
  banheira: (x, y, s = 1) => `<rect x="${x - 150 * s}" y="${y - 70 * s}" width="${300 * s}" height="${70 * s}" rx="${26 * s}" fill="#e9eef2"/>
    <rect x="${x - 136 * s}" y="${y - 50 * s}" width="${272 * s}" height="${42 * s}" rx="${16 * s}" fill="#7cc4e8"/>
    <rect x="${x + 108 * s}" y="${y - 120 * s}" width="${9 * s}" height="${52 * s}" fill="#b9c3cb"/>
    <rect x="${x + 86 * s}" y="${y - 124 * s}" width="${40 * s}" height="${9 * s}" rx="${4 * s}" fill="#b9c3cb"/>`,
  vela: (x, y, s = 1) => `<rect x="${x - 11 * s}" y="${y - 40 * s}" width="${22 * s}" height="${40 * s}" rx="${4 * s}" fill="#f2e7cf"/>
    <ellipse cx="${x}" cy="${y - 54 * s}" rx="${8 * s}" ry="${15 * s}" fill="#ffb648"/>
    <ellipse cx="${x}" cy="${y - 50 * s}" rx="${4 * s}" ry="${8 * s}" fill="#fff2b8"/>`,
  celular: (x, y, s = 1, texto = "") => `<rect x="${x - 52 * s}" y="${y - 104 * s}" width="${104 * s}" height="${196 * s}" rx="${16 * s}" fill="#1b1f27" stroke="#3b4350" stroke-width="${3 * s}"/>
    <rect x="${x - 44 * s}" y="${y - 94 * s}" width="${88 * s}" height="${176 * s}" rx="${10 * s}" fill="${texto ? "#2a1013" : "#0e1117"}"/>
    ${texto ? `<rect x="${x - 38 * s}" y="${y - 70 * s}" width="${76 * s}" height="${44 * s}" rx="${7 * s}" fill="#c0392b"/>
      <text x="${x}" y="${y - 44 * s}" text-anchor="middle" font-family="Inter,sans-serif" font-weight="900" font-size="${15 * s}" fill="#fff">${esc(texto)}</text>` : ""}`,
  porta: (x, y, s = 1, aberta = false) => `<rect x="${x - 60 * s}" y="${y - 210 * s}" width="${120 * s}" height="${210 * s}" rx="${5 * s}" fill="${aberta ? "#1a1f27" : "#6b4b31"}"/>
    ${aberta ? "" : `<circle cx="${x + 40 * s}" cy="${y - 100 * s}" r="${7 * s}" fill="#d8b24a"/>
      <rect x="${x - 46 * s}" y="${y - 196 * s}" width="${92 * s}" height="${80 * s}" rx="${4 * s}" fill="none" stroke="#573c26" stroke-width="${4 * s}"/>`}`,
  caixa: (x, y, s = 1) => `<rect x="${x - 44 * s}" y="${y - 62 * s}" width="${88 * s}" height="${62 * s}" fill="#c08a4e"/>
    <rect x="${x - 44 * s}" y="${y - 62 * s}" width="${88 * s}" height="${12 * s}" fill="#a3703c"/>`,
  moto: (x, y, s = 1) => `<circle cx="${x - 52 * s}" cy="${y - 26 * s}" r="${26 * s}" fill="none" stroke="#2c3e50" stroke-width="${8 * s}"/>
    <circle cx="${x + 52 * s}" cy="${y - 26 * s}" r="${26 * s}" fill="none" stroke="#2c3e50" stroke-width="${8 * s}"/>
    <path d="M${x - 52 * s} ${y - 26 * s} L${x - 10 * s} ${y - 58 * s} L${x + 40 * s} ${y - 56 * s} L${x + 52 * s} ${y - 26 * s}" stroke="#c0392b" stroke-width="${11 * s}" fill="none" stroke-linejoin="round"/>
    <rect x="${x - 26 * s}" y="${y - 76 * s}" width="${54 * s}" height="${16 * s}" rx="${7 * s}" fill="#2c3e50"/>`,
  carro: (x, y, s = 1, cor = "#3b6ea5") => `<rect x="${x - 95 * s}" y="${y - 54 * s}" width="${190 * s}" height="${40 * s}" rx="${13 * s}" fill="${cor}"/>
    <path d="M${x - 62 * s} ${y - 54 * s} L${x - 44 * s} ${y - 86 * s} L${x + 46 * s} ${y - 86 * s} L${x + 64 * s} ${y - 54 * s} z" fill="${cor}"/>
    <path d="M${x - 50 * s} ${y - 58 * s} L${x - 38 * s} ${y - 80 * s} L${x + 40 * s} ${y - 80 * s} L${x + 52 * s} ${y - 58 * s} z" fill="#cfe0ee" opacity=".8"/>
    <circle cx="${x - 56 * s}" cy="${y - 12 * s}" r="${16 * s}" fill="#22282f"/><circle cx="${x + 56 * s}" cy="${y - 12 * s}" r="${16 * s}" fill="#22282f"/>`,
  mochila: (x, y, s = 1) => `<rect x="${x - 38 * s}" y="${y - 82 * s}" width="${76 * s}" height="${82 * s}" rx="${16 * s}" fill="#4b6b4a"/>
    <rect x="${x - 28 * s}" y="${y - 46 * s}" width="${56 * s}" height="${30 * s}" rx="${7 * s}" fill="#3c5a3c"/>
    <rect x="${x - 14 * s}" y="${y - 94 * s}" width="${28 * s}" height="${16 * s}" rx="${7 * s}" fill="#3c5a3c"/>`,
  escada: (x, y, s = 1) => {
    const d = [];
    for (let i = 0; i < 6; i++) d.push(`<rect x="${x - 70 * s + i * 22 * s}" y="${y - i * 34 * s - 30 * s}" width="${110 * s}" height="${30 * s}" fill="#9aa3ab"/>`);
    return d.join("");
  },
  torneira: (x, y, s = 1, pingando = true) => `<rect x="${x - 7 * s}" y="${y - 96 * s}" width="${14 * s}" height="${60 * s}" fill="#b9c3cb"/>
    <path d="M${x} ${y - 96 * s} q0 ${-40 * s} ${50 * s} ${-40 * s}" stroke="#b9c3cb" stroke-width="${14 * s}" fill="none"/>
    ${pingando ? `<circle cx="${x}" cy="${y - 20 * s}" r="${7 * s}" fill="#7cc4e8"/>` : ""}`,
};

/* ---------------------------------------------------------------- cenários */
function predios(p, n = 7, base = H * 0.62, acesas = 0.25, semente = 7) {
  const r = (i) => ((Math.sin(semente * 99 + i * 37.7) + 1) / 2);
  const out = [];
  for (let i = 0; i < n; i++) {
    const w = 110 + r(i) * 110;
    const x = (i * (W + 120)) / n - 60;
    const h = 190 + r(i + 50) * 430 + (i % 3 === 0 ? 160 : 0);
    out.push(`<rect x="${x}" y="${base - h}" width="${w}" height="${h}" fill="${p.predio}"/>`);
    for (let a = 0; a < Math.floor(h / 74); a++) {
      for (let b = 0; b < Math.floor(w / 46); b++) {
        const on = r(i * 77 + a * 13 + b * 5) < acesas;
        out.push(`<rect x="${x + 14 + b * 46}" y="${base - h + 24 + a * 74}" width="${26}" height="${34}" fill="${on ? p.vidro : "rgba(0,0,0,.22)"}" opacity="${on ? 1 : 0.5}"/>`);
      }
    }
  }
  return out.join("");
}

const CENARIO = {
  cidade: (p, c) => `<rect width="${W}" height="${H}" fill="${p.ceu}"/>${predios(p, 7, H * 0.66, c.luz === "noite" ? 0.22 : c.luz === "escuro" ? 0.02 : 0.1, c.semente)}
    <rect y="${H * 0.66}" width="${W}" height="${H * 0.34}" fill="${p.chao}"/>`,
  predio: (p, c) => `<rect width="${W}" height="${H}" fill="${p.ceu}"/>${predios(p, 4, H * 0.8, 0.1, c.semente + 3)}
    <rect x="${W * 0.18}" y="${H * 0.1}" width="${W * 0.64}" height="${H * 0.7}" fill="${p.predio}"/>
    ${Array.from({ length: 7 }, (_, a) => Array.from({ length: 4 }, (_, b) =>
      `<rect x="${W * 0.22 + b * 140}" y="${H * 0.15 + a * 160}" width="90" height="110" fill="${(a * 4 + b) % 5 === 0 ? p.vidro : "rgba(0,0,0,.25)"}"/>`).join("")).join("")}
    <rect y="${H * 0.8}" width="${W}" height="${H * 0.2}" fill="${p.chao}"/>`,
  quarto: (p) => `<rect width="${W}" height="${H}" fill="${p.parede}"/>
    <rect y="${H * 0.66}" width="${W}" height="${H * 0.34}" fill="${p.chao}"/>
    <rect x="${W * 0.08}" y="${H * 0.72}" width="${W * 0.84}" height="18" fill="rgba(0,0,0,.12)"/>`,
  janela: (p, c) => `<rect width="${W}" height="${H}" fill="${p.parede}"/>
    <defs><clipPath id="vidro"><rect x="${W * 0.14}" y="${H * 0.16}" width="${W * 0.72}" height="${H * 0.46}"/></clipPath></defs>
    <rect x="${W * 0.14}" y="${H * 0.16}" width="${W * 0.72}" height="${H * 0.46}" fill="${p.ceu}"/>
    <g clip-path="url(#vidro)">${predios(p, 5, H * 0.6, c.luz === "escuro" ? 0.03 : 0.2, c.semente + 9)}</g>
    <rect x="${W * 0.14}" y="${H * 0.16}" width="${W * 0.72}" height="${H * 0.46}" fill="none" stroke="${p.tinta}" stroke-width="10"/>
    <rect x="${W * 0.49}" y="${H * 0.16}" width="12" height="${H * 0.46}" fill="${p.tinta}"/>
    <rect x="${W * 0.14}" y="${H * 0.385}" width="${W * 0.72}" height="12" fill="${p.tinta}"/>
    <rect y="${H * 0.68}" width="${W}" height="${H * 0.32}" fill="${p.chao}"/>`,
  banheiro: (p) => `<rect width="${W}" height="${H}" fill="#dfe6ea"/>
    <rect y="${H * 0.66}" width="${W}" height="${H * 0.34}" fill="#c3ced5"/>
    ${Array.from({ length: 9 }, (_, i) => `<rect x="${i * 120}" y="0" width="4" height="${H * 0.74}" fill="rgba(0,0,0,.05)"/>`).join("")}`,
  corredor: (p) => `<rect width="${W}" height="${H}" fill="${p.parede}"/>
    <path d="M0 0 L${W * 0.3} ${H * 0.3} L${W * 0.3} ${H * 0.72} L0 ${H}" fill="rgba(0,0,0,.16)"/>
    <path d="M${W} 0 L${W * 0.7} ${H * 0.3} L${W * 0.7} ${H * 0.72} L${W} ${H}" fill="rgba(0,0,0,.16)"/>
    <rect y="${H * 0.66}" width="${W}" height="${H * 0.34}" fill="${p.chao}"/>`,
  rua: (p, c) => `<rect width="${W}" height="${H}" fill="${p.ceu}"/>${predios(p, 6, H * 0.56, c.luz === "escuro" ? 0.02 : 0.14, c.semente + 2)}
    <rect y="${H * 0.56}" width="${W}" height="${H * 0.44}" fill="#3b4148"/>
    <rect y="${H * 0.56}" width="${W}" height="26" fill="${p.chao}"/>
    ${Array.from({ length: 5 }, (_, i) => `<rect x="${60 + i * 230}" y="${H * 0.78}" width="120" height="16" fill="#e8e2d2" opacity=".75"/>`).join("")}`,
  laje: (p, c) => `<rect width="${W}" height="${H}" fill="${p.ceu}"/>${predios(p, 6, H * 0.52, 0.12, c.semente + 5)}
    <rect y="${H * 0.52}" width="${W}" height="${H * 0.48}" fill="${p.chao}"/>
    <rect y="${H * 0.46}" width="${W}" height="${H * 0.08}" fill="${p.predio}"/>`,
  garagem: (p) => `<rect width="${W}" height="${H}" fill="#2c333b"/>
    <rect y="${H * 0.68}" width="${W}" height="${H * 0.32}" fill="#1e242b"/>
    ${Array.from({ length: 4 }, (_, i) => `<rect x="${i * 290 + 30}" y="${H * 0.2}" width="14" height="${H * 0.56}" fill="#3b444e"/>`).join("")}`,
  mercado: (p) => `<rect width="${W}" height="${H}" fill="#e8e3d6"/>
    ${Array.from({ length: 3 }, (_, i) => `<rect x="60" y="${H * 0.3 + i * 150}" width="${W - 120}" height="20" fill="#b9a98c"/>
      ${Array.from({ length: 9 }, (_, b) => `<rect x="${80 + b * 100}" y="${H * 0.3 + i * 150 - 54}" width="56" height="54" rx="5" fill="${["#c0392b", "#3b6ea5", "#d8a43a", "#4b8b5a"][(i + b) % 4]}"/>`).join("")}`).join("")}
    <rect y="${H * 0.68}" width="${W}" height="${H * 0.32}" fill="#cfc7b4"/>`,
  escuro: (p) => `<rect width="${W}" height="${H}" fill="#07090d"/>`,
};

/* ---------------------------------------------------------------- chuva / overlays */
function chuva(semente = 3, n = 150) {
  const r = (i) => ((Math.sin(semente * 13 + i * 77.3) + 1) / 2);
  return Array.from({ length: n }, (_, i) =>
    `<line x1="${r(i) * W}" y1="${r(i + 999) * H}" x2="${r(i) * W - 16}" y2="${r(i + 999) * H + 46}" stroke="#cfe3ef" stroke-width="3" opacity=".40"/>`).join("");
}

/* ---------------------------------------------------------------- montagem */
function svgCena(c) {
  const p = LUZ[c.luz] || LUZ.noite;
  const fundo = (CENARIO[c.cenario] || CENARIO.quarto)(p, c);
  const corpo = [];
  for (const o of c.objetos || []) {
    const f = OBJ[o.tipo];
    if (f) corpo.push(`<g opacity="${o.opacidade == null ? 1 : o.opacidade}">${f(o.x * W, o.y * H, o.s == null ? 1 : o.s, o.extra)}</g>`);
  }
  for (const g of c.gatos || []) corpo.push(gato(g.x * W, g.y * H, g.alt || 70, g.cor));
  for (const q of c.pessoas || []) corpo.push(pessoa(q.x * W, q.y * H, q.alt || 300, q.pose, q.cor, q.pele, q.olhando == null ? 1 : q.olhando));
  const veu = p.veu !== "none" ? `<rect width="${W}" height="${H}" fill="${p.veu}"/>` : "";
  const agua = c.chuva ? chuva(c.semente || 3) : "";
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">${fundo}${corpo}${veu}${agua}</svg>`;
}

const CENA = {
  /** desenha a cena; `cena` é um objeto do roteiro (cenario, luz, pessoas, objetos, legenda, relogio...) */
  monta(cena) {
    const c = cena || {};
    document.getElementById("arte").innerHTML = svgCena(c);
    // relógio / contador no alto
    const topo = document.getElementById("topo");
    if (c.relogio || c.contador) {
      topo.style.display = "flex";
      topo.innerHTML = (c.selo ? `<div class="selo">${esc(c.selo)}</div>` : "")
        + (c.relogio ? `<div class="hora">${esc(c.relogio)}</div>` : "")
        + (c.contador ? `<div class="cont"><b>${esc(c.contador)}</b>${c.contador_sub ? `<span>${esc(c.contador_sub)}</span>` : ""}</div>` : "");
    } else topo.style.display = "none";
    // onomatopeia (PLIC..., TRRRUM!)
    const ono = document.getElementById("ono");
    ono.textContent = c.onomatopeia || "";
    ono.style.display = c.onomatopeia ? "block" : "none";
    if (c.onomatopeia) {
      ono.style.left = `${(c.ono_x == null ? 0.62 : c.ono_x) * 100}%`;
      ono.style.top = `${(c.ono_y == null ? 0.3 : c.ono_y) * 100}%`;
    }
    this.legenda("");
    this._c = c;
  },

  /** legenda grande em caixa alta; a palavra entre *asteriscos* sai colorida */
  legenda(txt) {
    const el = document.getElementById("leg");
    const t = String(txt || "").trim();
    el.style.display = t ? "block" : "none";
    el.innerHTML = esc(t.toUpperCase()).replace(/\*([^*]+)\*/g, "<em>$1</em>").replace(/\*/g, "");
  },

  /** movimento lento de câmera dentro da cena (p de 0 a 1): é isso que dá "vida" sem precisar animar */
  anima(p) {
    const c = this._c || {};
    const m = c.movimento || "zoom";
    const q = Math.max(0, Math.min(1, p));
    let t = "";
    if (m === "zoom") t = `scale(${1.04 + q * 0.1})`;
    else if (m === "afasta") t = `scale(${1.16 - q * 0.1})`;
    else if (m === "direita") t = `scale(1.12) translateX(${(0.5 - q) * 5}%)`;
    else if (m === "esquerda") t = `scale(1.12) translateX(${(q - 0.5) * 5}%)`;
    else if (m === "sobe") t = `scale(1.12) translateY(${(q - 0.5) * 5}%)`;
    else if (m === "desce") t = `scale(1.12) translateY(${(0.5 - q) * 5}%)`;
    else t = "scale(1.05)";
    document.getElementById("arte").style.transform = t;
  },
};

window.CENA = CENA;
window.CENA_SVG = svgCena;
