"use strict";

/**
 * Opções de "filtro em arquivo" que mudaram no FFmpeg:
 *   até a 6.x: -filter_script:v arq / -filter_complex_script arq
 *   7.0 em diante: -/filter:v arq / -/filter_complex arq  (as antigas foram removidas na 8)
 */
const { spawnSync } = require("child_process");

let MAJOR = null;
function versao() {
  if (MAJOR === null) {
    const r = spawnSync("ffmpeg", ["-version"], { encoding: "utf-8" });
    const m = /ffmpeg version n?(\d+)/.exec(r.stdout || "");
    MAJOR = m ? Number(m[1]) : 7; // build sem número (git): assume nova
  }
  return MAJOR;
}

const novo = () => versao() >= 7;
/** ["-filter_script:v", arq] ou ["-/filter:v", arq] */
const filtroV = (arq) => (novo() ? ["-/filter:v", arq] : ["-filter_script:v", arq]);
/** ["-filter_complex_script", arq] ou ["-/filter_complex", arq] */
const filtroComplexo = (arq) => (novo() ? ["-/filter_complex", arq] : ["-filter_complex_script", arq]);

/**
 * Cor da gravação. iPhone grava em HDR (HLG / Dolby Vision, BT.2020, 10 bits): convertido direto
 * para JPG/H.264 sem "tone mapping" fica lavado e sem cor. Aqui vem o filtro que converte
 * para SDR BT.709 do jeito certo (ou "" quando a gravação já é SDR).
 * Padrão "natural": ajustado para bater com a conversão Dolby Vision do iPhone (só converte, não colore).
 * DETTO_TONEMAP=203|antigo|clip|hable|0 troca.
 * @param {string} video
 * @returns {{hdr: boolean, transfer: string, primaries: string, filtro: string}}
 */
function corDaGravacao(video) {
  const r = spawnSync("ffprobe", ["-v", "error", "-select_streams", "v:0", "-show_entries", "stream=color_transfer,color_primaries,color_space,pix_fmt", "-of", "json", video], { encoding: "utf-8" });
  let s = {};
  try {
    s = (JSON.parse(r.stdout || "{}").streams || [])[0] || {};
  } catch (_) {
    s = {};
  }
  const transfer = s.color_transfer || "";
  const primaries = s.color_primaries || "";
  const hdr = /arib-std-b67|smpte2084/.test(transfer);
  let filtro = "";
  const tm = (process.env.DETTO_TONEMAP || "natural").toLowerCase();
  const temZscale = /\bzscale\b/.test(spawnSync("ffmpeg", ["-hide_banner", "-filters"], { encoding: "utf-8" }).stdout || "");
  if ((hdr || /bt2020/.test(primaries)) && !temZscale) {
    console.error("AVISO: gravação em HDR, mas este FFmpeg não tem o filtro zscale; a cor pode sair lavada (instale o FFmpeg 'full' do gyan.dev).");
    return { hdr, transfer, primaries, filtro: "" };
  }
  if (hdr && tm !== "0") {
    // HLG/PQ → linear → BT.709 com tone mapping
    // reduz para Full HD ANTES (o tone mapping em 4K é 4x mais lento e o palco é 1920 de qualquer jeito)
    // natural (padrão): igual à conversão Dolby Vision do iPhone (libplacebo) — branco em 350 nits, mobius,
    // desat=1 e 12% menos saturação (o zscale esquenta a pele). "203" = o de antes (pele laranja); "antigo" = npl=100
    const base = "scale='min(1920,iw)':-2:flags=bicubic,";
    if (tm === "antigo") filtro = base + "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=mobius:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p";
    else if (tm === "203" || tm === "mobius") filtro = base + "zscale=t=linear:npl=203,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=mobius:param=0.6:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p";
    else if (["clip", "hable", "reinhard"].includes(tm)) filtro = base + `zscale=t=linear:npl=203,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=${tm}:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p`;
    else filtro = base + "zscale=t=linear:npl=350,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=mobius:desat=1,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,eq=saturation=0.88";
  } else if (/bt2020/.test(primaries)) {
    filtro = "zscale=p=bt709:t=bt709:m=bt709:r=tv,format=yuv420p";
  }
  return { hdr, transfer, primaries, filtro };
}

module.exports = { filtroV, filtroComplexo, versao, corDaGravacao };
