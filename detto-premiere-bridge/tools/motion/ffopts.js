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

module.exports = { filtroV, filtroComplexo, versao };
