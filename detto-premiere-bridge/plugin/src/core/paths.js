// @ts-check
"use strict";

/**
 * Utilitários de caminho independentes de plataforma (UXP não expõe `path` do Node).
 */

/**
 * Normaliza um caminho para comparação: barras "/", sem barra final,
 * minúsculas (Premiere roda em Windows/macOS, ambos case-insensitive por padrão).
 * @param {string} p
 */
function normalizeForCompare(p) {
  return toForwardSlashes(String(p || ""))
    .replace(/\/+$/, "")
    .toLowerCase();
}

/** @param {string} p */
function toForwardSlashes(p) {
  return String(p).replace(/\\/g, "/").replace(/\/{2,}/g, "/");
}

/** @param {...string} parts */
function join(...parts) {
  const filtered = parts.filter((p) => p !== undefined && p !== null && p !== "");
  if (filtered.length === 0) return "";
  const joined = filtered
    .map((p, i) => {
      const s = toForwardSlashes(p);
      if (i === 0) return s.replace(/\/+$/, "");
      return s.replace(/^\/+/, "").replace(/\/+$/, "");
    })
    .join("/");
  return joined;
}

/** @param {string} p */
function basename(p) {
  const s = toForwardSlashes(p).replace(/\/+$/, "");
  const idx = s.lastIndexOf("/");
  return idx >= 0 ? s.slice(idx + 1) : s;
}

/** @param {string} p */
function dirname(p) {
  const s = toForwardSlashes(p).replace(/\/+$/, "");
  const idx = s.lastIndexOf("/");
  if (idx < 0) return "";
  if (idx === 0) return "/";
  return s.slice(0, idx);
}

/** @param {string} p */
function stripExtension(p) {
  const base = basename(p);
  const idx = base.lastIndexOf(".");
  return idx > 0 ? base.slice(0, idx) : base;
}

/** @param {string} p */
function extension(p) {
  const base = basename(p);
  const idx = base.lastIndexOf(".");
  return idx > 0 ? base.slice(idx + 1).toLowerCase() : "";
}

/**
 * Converte caminhos para o formato nativo esperado pelo Premiere
 * (no Windows, "C:/a/b" → "C:\a\b").
 * @param {string} p
 * @param {string} [platform] "win32" | "darwin"
 */
function toNative(p, platform) {
  const isWin = platform ? platform.startsWith("win") : /^[a-zA-Z]:[\\/]/.test(p);
  return isWin ? toForwardSlashes(p).replace(/\//g, "\\") : toForwardSlashes(p);
}

/** Carimbo de data seguro para nomes de arquivo: 20261007-153012 */
function fileTimestamp(date = new Date()) {
  const pad = (/** @type {number} */ n) => String(n).padStart(2, "0");
  return (
    `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}` +
    `-${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`
  );
}

module.exports = {
  normalizeForCompare,
  toForwardSlashes,
  join,
  basename,
  dirname,
  stripExtension,
  extension,
  toNative,
  fileTimestamp,
};
