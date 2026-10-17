// @ts-check
"use strict";

/**
 * Controle de pausa cooperativa: o executor chama `checkpoint()` entre
 * operações; se pausado, aguarda até `resume()`.
 */
class PauseController {
  constructor() {
    this._paused = false;
    /** @type {Array<() => void>} */
    this._waiters = [];
    /** @type {Set<(paused: boolean) => void>} */
    this._listeners = new Set();
  }

  get paused() {
    return this._paused;
  }

  pause() {
    if (this._paused) return;
    this._paused = true;
    this._emit();
  }

  resume() {
    if (!this._paused) return;
    this._paused = false;
    const waiters = this._waiters.splice(0);
    waiters.forEach((w) => w());
    this._emit();
  }

  toggle() {
    if (this._paused) this.resume();
    else this.pause();
    return this._paused;
  }

  /** @returns {Promise<void>} */
  checkpoint() {
    if (!this._paused) return Promise.resolve();
    return new Promise((resolve) => this._waiters.push(resolve));
  }

  /** @param {(paused: boolean) => void} fn */
  subscribe(fn) {
    this._listeners.add(fn);
    return () => this._listeners.delete(fn);
  }

  _emit() {
    this._listeners.forEach((fn) => fn(this._paused));
  }
}

module.exports = { PauseController };
