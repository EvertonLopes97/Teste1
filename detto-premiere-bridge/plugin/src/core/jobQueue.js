// @ts-check
"use strict";

const paths = require("./paths");
const { parseEditPlan } = require("./schema");
const { BridgeError } = require("./errors");

const QUEUE_DIRS = Object.freeze(["pending", "processing", "completed", "failed"]);

/**
 * @typedef {Object} Job
 * @property {string} jobId
 * @property {string} fileName      ex.: job-001.json
 * @property {"pending"|"processing"|"completed"|"failed"} state
 * @property {any} plan
 * @property {string} planSource    caminho de onde o plano foi lido
 */

/**
 * Fila de jobs baseada em pastas, compartilhada com o DETTO ORCHESTRATOR:
 *
 *   detto-video-engine/jobs/{pending,processing,completed,failed}
 *
 * Um job pode ser o próprio EDIT_PLAN (job_id = nome do arquivo) ou um envelope:
 *   { "job_id": "job-001", "plan": { ... } }
 *   { "job_id": "job-001", "edit_plan_path": "C:/.../EDIT_PLAN.json" }
 */
class JobQueue {
  /**
   * @param {{fs: import("./types").FileSystemAdapter, root: string}} opts  root = pasta detto-video-engine
   */
  constructor(opts) {
    this.fs = opts.fs;
    this.root = opts.root;
    this.jobsDir = paths.join(opts.root, "jobs");
    this.logsDir = paths.join(opts.root, "logs");
  }

  /** @param {string} state */
  dir(state) {
    return paths.join(this.jobsDir, state);
  }

  async init() {
    for (const d of QUEUE_DIRS) await this.fs.mkdirp(this.dir(d));
    await this.fs.mkdirp(this.logsDir);
  }

  /** Arquivos .json em pending/, em ordem alfabética (job-001, job-002...). */
  async listPending() {
    const names = await this.fs.readdir(this.dir("pending"));
    return names.filter((n) => /\.json$/i.test(n) && !/\.report\.json$/i.test(n)).sort();
  }

  /**
   * Lê um job de pending/ sem movê-lo.
   * @param {string} fileName
   * @returns {Promise<Job>}
   */
  async load(fileName) {
    const filePath = paths.join(this.dir("pending"), fileName);
    const parsed = parseEditPlan(await this.fs.readText(filePath));
    if (!parsed.ok) throw new BridgeError(parsed.error.code, `${fileName}: ${parsed.error.message}`);

    const data = parsed.plan;
    let plan = data;
    let planSource = filePath;
    let jobId = paths.stripExtension(fileName);
    if (data && typeof data === "object" && !Array.isArray(data) && !data.project) {
      if (data.job_id) jobId = String(data.job_id);
      if (data.plan && typeof data.plan === "object") {
        plan = data.plan;
      } else if (typeof data.edit_plan_path === "string") {
        planSource = data.edit_plan_path;
        if (!(await this.fs.exists(planSource))) {
          throw new BridgeError("PLAN_NOT_FOUND", `${fileName}: edit_plan_path não encontrado: ${planSource}`);
        }
        const inner = parseEditPlan(await this.fs.readText(planSource));
        if (!inner.ok) throw new BridgeError(inner.error.code, `${planSource}: ${inner.error.message}`);
        plan = inner.plan;
      }
    }
    // plano "cru": o nome do arquivo identifica o job (é ele que circula entre as pastas)
    return { jobId, fileName, state: "pending", plan, planSource };
  }

  /** pending → processing @param {Job} job */
  async start(job) {
    await this.transition(job, "pending", "processing");
  }

  /**
   * processing → completed, gravando relatório e log ao lado do job.
   * @param {Job} job @param {any} report @param {string} logJsonl
   */
  async complete(job, report, logJsonl) {
    await this.transition(job, "processing", "completed");
    await this.writeArtifacts(job, "completed", report, logJsonl);
  }

  /**
   * processing (ou pending) → failed.
   * @param {Job} job @param {any} report @param {string} logJsonl
   */
  async fail(job, report, logJsonl) {
    await this.transition(job, job.state === "pending" ? "pending" : "processing", "failed");
    await this.writeArtifacts(job, "failed", report, logJsonl);
  }

  /**
   * Move um arquivo inválido direto de pending/ para failed/ (evita reprocessar em loop).
   * @param {string} fileName @param {{code: string, message: string}} error
   */
  async reject(fileName, error) {
    /** @type {Job} */
    const job = { jobId: paths.stripExtension(fileName), fileName, state: "pending", plan: null, planSource: "" };
    const report = { job_id: job.jobId, status: "failed", fatal: error, finished_at: new Date().toISOString() };
    await this.fail(job, report, "");
  }

  /**
   * @param {Job} job
   * @param {"pending"|"processing"} from
   * @param {"processing"|"completed"|"failed"} to
   */
  async transition(job, from, to) {
    if (job.state !== from) {
      throw new BridgeError("INVALID_JOB_TRANSITION", `Job ${job.jobId}: transição ${job.state} → ${to} não permitida.`);
    }
    const src = paths.join(this.dir(from), job.fileName);
    let dest = paths.join(this.dir(to), job.fileName);
    if (await this.fs.exists(dest)) {
      // não sobrescrever execuções anteriores do mesmo job
      dest = paths.join(this.dir(to), `${paths.stripExtension(job.fileName)}.${paths.fileTimestamp()}.json`);
    }
    await this.fs.move(src, dest);
    job.fileName = paths.basename(dest);
    job.state = to;
  }

  /** @param {Job} job @param {string} state @param {any} report @param {string} logJsonl */
  async writeArtifacts(job, state, report, logJsonl) {
    const stem = paths.stripExtension(job.fileName);
    await this.fs.writeText(paths.join(this.dir(state), `${stem}.report.json`), JSON.stringify(report, null, 2));
    if (logJsonl) {
      await this.fs.writeText(paths.join(this.dir(state), `${stem}.log.jsonl`), logJsonl);
      await this.fs.writeText(paths.join(this.logsDir, `${stem}.log.jsonl`), logJsonl);
    }
  }
}

/**
 * Observa jobs/pending por polling (UXP não oferece watcher de arquivos confiável).
 * Chama `onJob(fileName)` para cada arquivo novo quando o Bridge está livre.
 */
class JobWatcher {
  /**
   * @param {{queue: JobQueue, intervalMs: number, isBusy: () => boolean, onJob: (fileName: string) => Promise<unknown>, onError?: (e: any) => void}} opts
   */
  constructor(opts) {
    this.opts = opts;
    /** @type {Set<string>} */
    this.seen = new Set();
    /** @type {any} */
    this._timer = null;
    this.running = false;
  }

  start() {
    if (this.running) return;
    this.running = true;
    const loop = async () => {
      if (!this.running) return;
      await this.tick();
      if (this.running) this._timer = setTimeout(loop, this.opts.intervalMs);
    };
    loop();
  }

  stop() {
    this.running = false;
    if (this._timer) clearTimeout(this._timer);
    this._timer = null;
  }

  /** Uma varredura. Retorna o arquivo entregue, se houver. */
  async tick() {
    if (this.opts.isBusy()) return null;
    try {
      const pending = await this.opts.queue.listPending();
      // esquece arquivos que saíram de pending (permite reenviar o mesmo nome)
      for (const s of [...this.seen]) if (!pending.includes(s)) this.seen.delete(s);
      const next = pending.find((n) => !this.seen.has(n));
      if (!next) return null;
      this.seen.add(next);
      await this.opts.onJob(next);
      return next;
    } catch (e) {
      this.opts.onError && this.opts.onError(e);
      return null;
    }
  }
}

module.exports = { JobQueue, JobWatcher, QUEUE_DIRS };
