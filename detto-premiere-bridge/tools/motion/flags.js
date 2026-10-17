"use strict";

/**
 * Bandeiras das seleções (flagcdn.com, domínio público) com cache local.
 */

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

/** nome (normalizado, sem acento) → código flagcdn */
const COUNTRIES = {
  argentina: "ar",
  hungria: "hu",
  nigeria: "ng",
  "servia e montenegro": "rs",
  servia: "rs",
  alemanha: "de",
  brasil: "br",
  uruguai: "uy",
  holanda: "nl",
  chile: "cl",
  equador: "ec",
  islandia: "is",
  croacia: "hr",
  franca: "fr",
  italia: "it",
  "arabia saudita": "sa",
  mexico: "mx",
  polonia: "pl",
  australia: "au",
  colombia: "co",
  inglaterra: "gb-eng",
  espanha: "es",
  benin: "bj",
};

/** @param {string} s */
function norm(s) {
  return s
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/** @param {string} name */
function flagCode(name) {
  const n = norm(name);
  if (COUNTRIES[n]) return COUNTRIES[n];
  const hit = Object.keys(COUNTRIES)
    .sort((a, b) => b.length - a.length)
    .find((k) => n.includes(k));
  return hit ? COUNTRIES[hit] : null;
}

/** curl respeita o proxy do ambiente (HTTPS_PROXY); o módulo https do Node não. */
function download(url, dest) {
  const r = spawnSync("curl", ["-sSfL", "-A", "DettoPreview/0.1", "-o", dest, url]);
  if (r.status !== 0) throw new Error(`${url}: ${String(r.stderr).trim()}`);
  return dest;
}

/**
 * Garante as bandeiras no cache. Falhas viram aviso (a placa usa um círculo neutro).
 * @param {string[]} codes
 * @param {string} dir
 */
async function ensureFlags(codes, dir) {
  fs.mkdirSync(dir, { recursive: true });
  const missing = [];
  for (const code of new Set(codes.filter(Boolean))) {
    const dest = path.join(dir, `${code}.png`);
    if (fs.existsSync(dest) && fs.statSync(dest).size > 0) continue;
    try {
      download(`https://flagcdn.com/w320/${code}.png`, dest);
    } catch (e) {
      missing.push(code);
    }
  }
  return missing;
}

module.exports = { flagCode, ensureFlags, COUNTRIES };
