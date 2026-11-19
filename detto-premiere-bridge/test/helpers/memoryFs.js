"use strict";

const paths = require("../../plugin/src/core/paths");

/**
 * FileSystemAdapter em memória para testes.
 */
class MemoryFs {
  /** @param {Record<string, string>} [files] */
  constructor(files = {}) {
    /** @type {Map<string, string>} */
    this.files = new Map();
    /** @type {Set<string>} */
    this.dirs = new Set();
    for (const [p, c] of Object.entries(files)) this.put(p, c);
  }

  _k(p) {
    return paths.toForwardSlashes(p).replace(/\/+$/, "");
  }

  put(p, content = "") {
    const k = this._k(p);
    this.files.set(k, content);
    let d = paths.dirname(k);
    while (d && d !== "/" && !this.dirs.has(d)) {
      this.dirs.add(d);
      d = paths.dirname(d);
    }
  }

  async exists(p) {
    const k = this._k(p);
    return this.files.has(k) || this.dirs.has(k);
  }
  async readText(p) {
    const k = this._k(p);
    if (!this.files.has(k)) throw new Error(`ENOENT: ${p}`);
    return this.files.get(k);
  }
  async writeText(p, text) {
    this.put(p, text);
  }
  async readdir(p) {
    const k = this._k(p);
    if (!this.dirs.has(k)) throw new Error(`ENOENT: ${p}`);
    const out = new Set();
    for (const f of [...this.files.keys(), ...this.dirs]) {
      if (paths.dirname(f) === k) out.add(paths.basename(f));
    }
    return [...out];
  }
  async mkdirp(p) {
    let d = this._k(p);
    while (d && d !== "/") {
      this.dirs.add(d);
      d = paths.dirname(d);
    }
  }
  async move(from, to) {
    const a = this._k(from);
    if (!this.files.has(a)) throw new Error(`ENOENT: ${from}`);
    const content = this.files.get(a);
    this.files.delete(a);
    this.put(to, content);
  }
  async copyFile(from, to) {
    const a = this._k(from);
    if (!this.files.has(a)) throw new Error(`ENOENT: ${from}`);
    if (this.files.has(this._k(to))) throw new Error(`EEXIST: ${to}`);
    this.put(to, this.files.get(a));
  }
}

module.exports = { MemoryFs };
