// @ts-check
"use strict";

const { LOG_STATUS } = require("./constants");

/**
 * @typedef {Object} LogEntry
 * @property {string} job_id
 * @property {string} step
 * @property {string} status       success | error | warning | fallback | skipped | info
 * @property {string} timestamp    ISO 8601
 * @property {number} duration_ms
 * @property {string} [message]
 * @property {string} [reason]     código curto, ex.: "effect_not_available"
 * @property {string} [target]     item afetado (id de mídia, índice do corte...)
 * @property {any}    [details]
 */

/**
 * Logger estruturado. Cada operação gera uma entrada JSON no formato
 * acordado com o DETTO ORCHESTRATOR.
 */
class Logger {
  /**
   * @param {{jobId?: string, now?: () => number, clock?: () => Date}} [opts]
   */
  constructor(opts = {}) {
    this.jobId = opts.jobId || "manual";
    this._now = opts.now || (() => Date.now());
    this._clock = opts.clock || (() => new Date());
    /** @type {LogEntry[]} */
    this.entries = [];
    /** @type {Set<(e: LogEntry) => void>} */
    this._listeners = new Set();
  }

  /** @param {string} jobId */
  setJobId(jobId) {
    this.jobId = jobId;
  }

  /** @param {(e: LogEntry) => void} fn */
  subscribe(fn) {
    this._listeners.add(fn);
    return () => this._listeners.delete(fn);
  }

  /**
   * @param {string} step
   * @param {string} status
   * @param {Partial<LogEntry>} [extra]
   * @returns {LogEntry}
   */
  log(step, status, extra = {}) {
    /** @type {LogEntry} */
    const entry = {
      job_id: this.jobId,
      step,
      status,
      timestamp: this._clock().toISOString(),
      duration_ms: 0,
      ...extra,
    };
    this.entries.push(entry);
    for (const fn of this._listeners) {
      try {
        fn(entry);
      } catch (_) {
        /* listener de UI nunca deve derrubar o pipeline */
      }
    }
    return entry;
  }

  /**
   * Mede uma operação e registra o resultado. Se `fn` retornar
   * `{status, reason, message, details}`, esses campos são usados no log.
   * Exceções são registradas como erro e relançadas.
   * @template T
   * @param {string} step
   * @param {() => Promise<T>} fn
   * @param {{target?: string, message?: string}} [meta]
   * @returns {Promise<T>}
   */
  async time(step, fn, meta = {}) {
    const t0 = this._now();
    try {
      const result = await fn();
      const r = /** @type {any} */ (result);
      const outcome = r && typeof r === "object" && typeof r.status === "string" ? r : null;
      this.log(step, outcome ? outcome.status : LOG_STATUS.SUCCESS, {
        duration_ms: this._now() - t0,
        ...meta,
        ...(outcome && outcome.reason ? { reason: outcome.reason } : {}),
        ...(outcome && outcome.message ? { message: outcome.message } : {}),
        ...(outcome && outcome.details !== undefined ? { details: outcome.details } : {}),
      });
      return result;
    } catch (e) {
      this.log(step, LOG_STATUS.ERROR, {
        duration_ms: this._now() - t0,
        ...meta,
        reason: (e && /** @type {any} */ (e).code) || "exception",
        message: e instanceof Error ? e.message : String(e),
      });
      throw e;
    }
  }

  /** @param {string} status */
  count(status) {
    return this.entries.filter((e) => e.status === status).length;
  }

  /** Serializa como JSON Lines (uma entrada por linha). */
  toJsonLines() {
    return this.entries.map((e) => JSON.stringify(e)).join("\n") + (this.entries.length ? "\n" : "");
  }

  clear() {
    this.entries = [];
  }
}

module.exports = { Logger };
