"use strict";

/**
 * O desenho da vinheta, quadro a quadro. `window.VIN.monta(canal, nome, W, H)` prepara e
 * `window.VIN.quadro(p)` (p = 0..1 dentro da vinheta) põe o estado daquele instante.
 *
 * O tempo é dividido em três partes, como nas aberturas que funcionam:
 *   0 → 0,45  ENTRADA   o fundo acende, as faixas abrem, a sigla vem com zoom
 *   0,45      BATIDA    estouro branco, o nome TRAVA no lugar (é aqui que entra o impacto do som)
 *   0,45 → 1  ASSENTA   a luz passa, o selo pisca, o risco corre e o sub aparece; some no fim
 */

const AMARELO = "#ffd400";
const LIMA = "#c6ff3d";
const ROXO = "#a855f7";
const CIANO = "#3cf0ff";
const MAGENTA = "#ff3cc8";

/** o pôr do sol de Vice City em CAMADAS: céu, sol fatiado (recortado no disco) e a grade neon só no chão.
 *  Numa camada só, as faixas do sol riscavam o céu inteiro e a grade cobria a tela toda. */
function viceCamadas(W, H) {
  const palco = document.getElementById("palco");
  const fundo = document.getElementById("fundo");
  fundo.style.background = "linear-gradient(180deg, #1a0a2c 0%, #6a1c70 30%, #ff2d78 56%, #ff9632 76%, #ffd45a 100%)";
  for (const id of ["viceSol", "viceGrade"]) {
    const velho = document.getElementById(id);
    if (velho) velho.remove();
  }
  // o SOL: disco com degradê, cortado por faixas que engrossam para baixo
  const sol = document.createElement("div");
  sol.id = "viceSol";
  const r = Math.round(H * 0.30);
  Object.assign(sol.style, {
    position: "absolute", left: (W / 2 - r) + "px", top: (H * 0.66 - r) + "px",   // abaixo do nome, senão as faixas atrapalham a leitura
    width: r * 2 + "px", height: r * 2 + "px", borderRadius: "50%", zIndex: "0",
    background: "repeating-linear-gradient(180deg, transparent 0 " + Math.round(r * 0.16) + "px, rgba(12,4,26,.92) "
      + Math.round(r * 0.16) + "px " + Math.round(r * 0.22) + "px), linear-gradient(180deg, #ffe06a 0%, #ff4f8b 100%)",
    filter: "blur(.4px)", boxShadow: "0 0 " + Math.round(r * 0.5) + "px rgba(255,120,160,.55)",
  });
  // o GRID: só o terço de baixo, em perspectiva
  const grade = document.createElement("div");
  grade.id = "viceGrade";
  Object.assign(grade.style, {
    position: "absolute", left: "-30%", right: "-30%", bottom: "0", height: "34%", zIndex: "0",
    width: "160%", transform: "perspective(" + Math.round(H * 0.6) + "px) rotateX(62deg)", transformOrigin: "50% 100%",
    background: "repeating-linear-gradient(90deg, rgba(60,240,255,.5) 0 3px, transparent 3px 5%),"
      + "repeating-linear-gradient(0deg, rgba(255,60,200,.5) 0 3px, transparent 3px 9%)",
    maskImage: "linear-gradient(180deg, transparent 0%, #000 45%, #000 100%)",
    WebkitMaskImage: "linear-gradient(180deg, transparent 0%, #000 45%, #000 100%)",
  });
  palco.insertBefore(sol, fundo.nextSibling);
  palco.insertBefore(grade, sol.nextSibling);
  // o nome TEM que ficar por cima do sol e da grade (sem isso o disco cobria tudo)
  for (const id of ["luz", "centro", "selo", "faixaCima", "faixaBaixo", "sweep", "flash"]) {
    const el = document.getElementById(id);
    if (el) {
      el.style.position = el.style.position || "absolute";
      el.style.zIndex = id === "luz" ? "1" : "6";
    }
  }
}

const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
/* desacelera no fim: é o que faz o texto "travar" em vez de escorregar */
const freia = (t) => 1 - Math.pow(1 - clamp(t), 3);

/** listras diagonais escuras (o fundo do canal de notícias) */
function listras(W, H) {
  const passo = Math.round(H / 24);
  return `repeating-linear-gradient(135deg, #121212 0 ${passo}px, #1c1c1c ${passo}px ${passo * 2}px)`;
}

const VIN = {
  monta(canal, nome, W, H, selo_, sub_) {
    this.canal = ["vlog", "vice"].includes(canal) ? canal : "noticias";
    const palavras = String(nome || "").toUpperCase().trim().split(/\s+/);
    const fundo = document.getElementById("fundo");
    const luz = document.getElementById("luz");
    const sigla = document.getElementById("sigla");
    const nomeEl = document.getElementById("nome");
    const selo = document.getElementById("selo");
    const sub = document.getElementById("sub");
    const risco = document.getElementById("risco");

    if (this.canal === "noticias") {
      // telejornal: listras, sigla DG amarela atrás, faixas amarelas e selo PLANTÃO
      fundo.style.background = listras(W, H);
      luz.style.background = `radial-gradient(60% 70% at 50% 45%, rgba(255,212,0,.18), transparent 70%)`;
      sigla.textContent = palavras.map((p) => p[0]).join("").slice(0, 3) || "DG";
      sigla.style.color = "rgba(255,212,0,.14)";
      // a última palavra sai amarela ("DETTO GALO NOTÍCIAS" → NOTÍCIAS amarelo)
      const ult = palavras.length > 1 ? palavras.pop() : "";
      nomeEl.innerHTML = esc(palavras.join(" ")) + (ult ? `<br><em style="color:${AMARELO}">${esc(ult)}</em>` : "");
      selo.textContent = selo_ === "@" ? "PLANTÃO" : String(selo_ || "");
      sub.textContent = sub_ === "@" ? "VÍDEO NOVO TODO DIA" : String(sub_ || "");
      sub.style.color = "rgba(255,255,255,.92)";
      risco.style.background = AMARELO;
      for (const f of document.querySelectorAll(".faixa")) f.style.background = AMARELO;
    } else if (this.canal === "vice") {
      // GTA 6 / gameplay: o pôr do sol de Vice City, com a franja ciano/magenta nas letras
      viceCamadas(W, H);
      luz.style.background = "radial-gradient(50% 55% at 50% 52%, rgba(255,80,160,.35), transparent 70%)";
      sigla.textContent = palavras.map((x) => x[0]).join("").slice(0, 3);
      sigla.style.color = "rgba(255,255,255,.07)";
      const ultv = palavras.length > 1 ? palavras.pop() : "";
      nomeEl.innerHTML = esc(palavras.join(" ")) + (ultv ? "<br>" + esc(ultv) : "");
      nomeEl.style.textShadow = "-7px 0 " + CIANO + ", 7px 0 " + MAGENTA + ", 0 10px 40px rgba(0,0,0,.6)";
      selo.textContent = selo_ === "@" ? "" : String(selo_ || "");
      sub.textContent = sub_ === "@" ? "TUDO SOBRE O GTA 6" : String(sub_ || "");
      sub.style.color = CIANO;
      risco.style.background = "linear-gradient(90deg, " + CIANO + ", " + MAGENTA + ")";
      document.getElementById("faixaCima").style.background = "linear-gradient(90deg, " + CIANO + ", transparent)";
      document.getElementById("faixaBaixo").style.background = "linear-gradient(90deg, transparent, " + MAGENTA + ")";
    } else {
      // vlog + gameplay: lima de um lado, roxo do outro
      fundo.style.background = "linear-gradient(135deg, #0a0e0c 0%, #140a22 100%)";
      luz.style.background = `radial-gradient(42% 60% at 16% 50%, rgba(198,255,61,.3), transparent 70%),
        radial-gradient(42% 60% at 84% 50%, rgba(168,85,247,.34), transparent 70%)`;
      sigla.textContent = palavras.map((p) => p[0]).join("").slice(0, 3);
      sigla.style.color = "rgba(255,255,255,.06)";
      const ult = palavras.length > 1 ? palavras.pop() : "";
      nomeEl.innerHTML = esc(palavras.join(" ")) + (ult ? `<br><em style="color:${LIMA}">${esc(ult)}</em>` : "");
      selo.textContent = selo_ === "@" ? "" : String(selo_ || "");
      sub.textContent = sub_ === "@" ? "VLOG · GAMEPLAY" : String(sub_ || "");
      sub.style.color = "rgba(255,255,255,.88)";
      risco.style.background = `linear-gradient(90deg, ${LIMA}, ${ROXO})`;
      document.getElementById("faixaCima").style.background = `linear-gradient(90deg, ${LIMA}, transparent)`;
      document.getElementById("faixaBaixo").style.background = `linear-gradient(90deg, transparent, ${ROXO})`;
    }
    this.quadro(0);
  },

  quadro(p) {
    const q = clamp(p);
    const BAT = 0.45;                       // o instante da batida (o som bate junto)
    const entra = freia(q / BAT);           // 0→1 até a batida
    const depois = clamp((q - BAT) / (1 - BAT));
    const sai = clamp((q - 0.86) / 0.14);   // os últimos 14%: some para o vídeo

    const palco = document.getElementById("palco");
    palco.style.opacity = String(1 - sai);

    // sigla gigante: entra com zoom e fica
    const sigla = document.getElementById("sigla");
    sigla.style.opacity = String(entra * 0.9);
    sigla.style.transform = `scale(${1.5 - entra * 0.5})`;

    // nome: vem de baixo e TRAVA na batida; depois respira de leve
    const nome = document.getElementById("nome");
    const respira = depois > 0 ? Math.sin(depois * Math.PI) * 0.012 : 0;
    nome.style.opacity = String(clamp(entra * 1.3));
    nome.style.transform = `translateY(${(1 - entra) * 7}vh) scale(${(0.92 + entra * 0.08 + respira).toFixed(4)})`;
    nome.style.filter = `blur(${((1 - entra) * 1.4).toFixed(2)}vh)`;

    // faixas abrem antes da batida
    for (const [id, dir] of [["faixaCima", 1], ["faixaBaixo", 1]]) {
      const f = document.getElementById(id);
      f.style.transform = `scaleX(${freia(q / (BAT * 0.9)) * dir})`;
    }

    // estouro branco no instante da batida
    const flash = document.getElementById("flash");
    flash.style.opacity = String(Math.max(0, 1 - Math.abs(q - BAT) / 0.06) * 0.85);

    // passada de luz logo depois da batida
    const sweep = document.getElementById("sweep");
    const s = clamp((q - BAT - 0.05) / 0.3);
    sweep.style.opacity = String(s > 0 && s < 1 ? 1 : 0);
    sweep.style.transform = `translateX(${(-60 + s * 160).toFixed(1)}%)`;

    // selo piscando e o risco correndo por baixo do nome
    const selo = document.getElementById("selo");
    // canal sem selo (vlog) não mostra a pílula vermelha vazia
    selo.style.display = selo.textContent.trim() ? "block" : "none";
    selo.style.opacity = String(depois > 0.05 && Math.sin(depois * 26) > -0.3 ? 1 : 0);
    document.getElementById("risco").style.width = `${freia(depois / 0.45) * 26}vw`;
    document.getElementById("sub").style.opacity = String(clamp((depois - 0.35) / 0.3));
  },
};

window.VIN = VIN;
