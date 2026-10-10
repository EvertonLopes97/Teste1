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
 * Tone mapping "mobius": meios-tons e cor iguais aos do iPhone, só os brilhos fortes são
 * comprimidos (hable escurece; clip estoura o céu/janela). DETTO_TONEMAP=clip|hable|0 troca.
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
  const tm = (process.env.DETTO_TONEMAP || "mobius").toLowerCase();
  const temZscale = /\bzscale\b/.test(spawnSync("ffmpeg", ["-hide_banner", "-filters"], { encoding: "utf-8" }).stdout || "");
  if ((hdr || /bt2020/.test(primaries)) && !temZscale) {
    console.error("AVISO: gravação em HDR, mas este FFmpeg não tem o filtro zscale; a cor pode sair lavada (instale o FFmpeg 'full' do gyan.dev).");
    return { hdr, transfer, primaries, filtro: "" };
  }
  if (hdr && tm !== "0") {
    // HLG/PQ → linear → BT.709 com tone mapping, sem tirar saturação (desat=0)
    // reduz para Full HD ANTES (o tone mapping em 4K é 4x mais lento e o palco é 1920 de qualquer jeito)
    filtro = `scale='min(1920,iw)':-2:flags=bicubic,zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=${tm}:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p`;
  } else if (/bt2020/.test(primaries)) {
    filtro = "zscale=p=bt709:t=bt709:m=bt709:r=tv,format=yuv420p";
  }
  return { hdr, transfer, primaries, filtro };
}

module.exports = { filtroV, filtroComplexo, versao, corDaGravacao };
