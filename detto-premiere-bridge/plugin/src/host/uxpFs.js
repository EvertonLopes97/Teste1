// @ts-check
"use strict";

/**
 * Adaptador de filesystem sobre o módulo `fs` do UXP (requer
 * `"localFileSystem": "fullAccess"` no manifest). Implementa `FileSystemAdapter`.
 */

const paths = require("../core/paths");

/**
 * O `fs` do UXP aceita callback e, nas versões recentes, também devolve Promise.
 * Este helper suporta os dois estilos sem resolver duas vezes.
 * @param {Function} fn
 * @param {any[]} args
 * @returns {Promise<any>}
 */
function call(fn, args) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const done = (/** @type {any} */ err, /** @type {any} */ value) => {
      if (settled) return;
      settled = true;
      if (err) reject(err);
      else resolve(value);
    };
    try {
      const ret = fn(...args, done);
      if (ret && typeof ret.then === "function") ret.then((/** @type {any} */ v) => done(null, v), done);
    } catch (e) {
      done(e, undefined);
    }
  });
}

class UxpFileSystem {
  /** @param {{fs?: any, platform?: string}} [deps] */
  constructor(deps = {}) {
    this.fs = deps.fs || require("fs");
    this.platform = deps.platform || "";
  }

  /** @param {string} p */
  _p(p) {
    return paths.toNative(p, this.platform || undefined);
  }

  /** @param {string} p */
  async exists(p) {
    try {
      await call(this.fs.lstat.bind(this.fs), [this._p(p)]);
      return true;
    } catch (_) {
      return false;
    }
  }

  /** @param {string} p */
  async readText(p) {
    const data = await call(this.fs.readFile.bind(this.fs), [this._p(p), { encoding: "utf-8" }]);
    return typeof data === "string" ? data : new TextDecoder("utf-8").decode(data);
  }

  /** @param {string} p @param {string} text */
  async writeText(p, text) {
    await call(this.fs.writeFile.bind(this.fs), [this._p(p), text, { encoding: "utf-8" }]);
  }

  /** @param {string} p */
  async readdir(p) {
    const names = await call(this.fs.readdir.bind(this.fs), [this._p(p)]);
    return (names || []).map((/** @type {any} */ n) => String(n));
  }

  /** @param {string} p */
  async mkdirp(p) {
    if (await this.exists(p)) return;
    try {
      await call(this.fs.mkdir.bind(this.fs), [this._p(p), { recursive: true }]);
      if (await this.exists(p)) return;
    } catch (_) {
      /* tenta segmento a segmento */
    }
    const parent = paths.dirname(p);
    if (parent && parent !== p) await this.mkdirp(parent);
    if (!(await this.exists(p))) await call(this.fs.mkdir.bind(this.fs), [this._p(p), {}]);
  }

  /** @param {string} from @param {string} to */
  async move(from, to) {
    await call(this.fs.rename.bind(this.fs), [this._p(from), this._p(to)]);
  }

  /** @param {string} from @param {string} to */
  async copyFile(from, to) {
    if (await this.exists(to)) throw new Error(`Destino já existe: ${to}`);
    if (typeof this.fs.copyFile === "function") {
      await call(this.fs.copyFile.bind(this.fs), [this._p(from), this._p(to), 0]);
      return;
    }
    const data = await call(this.fs.readFile.bind(this.fs), [this._p(from), {}]);
    await call(this.fs.writeFile.bind(this.fs), [this._p(to), data, {}]);
  }
}

module.exports = { UxpFileSystem, call };
