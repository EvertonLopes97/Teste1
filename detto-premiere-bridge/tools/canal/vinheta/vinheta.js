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
    this.canal = canal === "vlog" ? "vlog" : "noticias";
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
