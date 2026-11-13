// @ts-check
"use strict";

const { STATUS, STEPS, LOG_STATUS } = require("./constants");
const { parseEditPlan } = require("./schema");
const { analyzePlan } = require("./analyze");
const { executePlan } = require("./executor");
const { Logger } = require("./logger");
const { PauseController } = require("./pause");
const { resolveConfig } = require("./config");
const { JobQueue, JobWatcher } = require("./jobQueue");

/**
 * Estado observável exibido pelo painel.
 * @typedef {Object} BridgeState
 * @property {boolean} connected
 * @property {string} premiereVersion
 * @property {string} uxpVersion
 * @property {string} projectName
 * @property {string} sequenceName
 * @property {string} planFile
 * @property {string} status          IDLE | PROCESSING | PAUSED | COMPLETE | ERROR
 * @property {string} currentStep
 * @property {number} progress        0..1
 * @property {import("./analyze").PlanPreview|null} preview
 * @property {import("./report").ExecutionReport|null} report
 * @property {string} jobId
 * @property {string} message
 */

/**
 * Orquestra o fluxo do painel sem depender de DOM nem de Premiere:
 * carregar → analisar → executar → relatório, além da fila de jobs.
 */
class BridgeController {
  /**
   * @param {{
   *   host: import("./types").HostAdapter,
   *   fs: import("./types").FileSystemAdapter,
   *   config?: Partial<import("./config").BridgeConfig>,
   *   confirm?: (message: string) => Promise<boolean>,
   * }} opts
   */
  constructor(opts) {
    this.host = opts.host;
    this.fs = opts.fs;
    this.config = resolveConfig(opts.config);
    this.confirm = opts.confirm || (async () => false);
    this.logger = new Logger();
    this.pause = new PauseController();
    /** @type {any} */
    this.plan = null;
    /** @type {import("./jobQueue").Job|null} */
    this.job = null;
    /** @type {JobQueue|null} */
    this.queue = null;
    /** @type {JobWatcher|null} */
    this.watcher = null;
    /** @type {BridgeState} */
    this.state = {
      connected: false,
      premiereVersion: "",
      uxpVersion: "",
      projectName: "",
      sequenceName: "",
      planFile: "",
      status: STATUS.IDLE,
      currentStep: "",
      progress: 0,
      preview: null,
      report: null,
      jobId: "",
      message: "",
    };
    /** @type {Set<(s: BridgeState) => void>} */
    this._listeners = new Set();
    this.pause.subscribe((paused) => {
      if (this.state.status === STATUS.PROCESSING || this.state.status === STATUS.PAUSED) {
        this._set({ status: paused ? STATUS.PAUSED : STATUS.PROCESSING });
      }
    });
  }

  /** @param {(s: BridgeState) => void} fn */
  subscribe(fn) {
    this._listeners.add(fn);
    fn(this.state);
    return () => this._listeners.delete(fn);
  }

  /** @param {Partial<BridgeState>} patch */
  _set(patch) {
    this.state = { ...this.state, ...patch };
    this._listeners.forEach((fn) => fn(this.state));
  }

  /** @param {string} message */
  setMessage(message) {
    this._set({ message });
  }

  get busy() {
    return this.state.status === STATUS.PROCESSING || this.state.status === STATUS.PAUSED;
  }

  /** Atualiza CONNECTED/DISCONNECTED, projeto e sequência ativos. */
  async refreshEnvironment() {
    try {
      const env = await this.host.getEnvironment();
      const project = env.connected ? await this.host.getActiveProject() : null;
      const seq = project ? await this.host.getActiveSequence() : null;
      this._set({
        connected: env.connected,
        premiereVersion: env.premiereVersion,
        uxpVersion: env.uxpVersion,
        projectName: project ? project.name : "",
        sequenceName: seq ? seq.name : "",
      });
    } catch (_) {
      this._set({ connected: false, projectName: "", sequenceName: "" });
    }
    return this.state;
  }

  /**
   * Carrega um EDIT_PLAN a partir do texto do arquivo.
   * @param {string} text
   * @param {string} source nome/caminho exibido no painel
   */
  loadPlanText(text, source) {
    if (this.busy) throw new Error("Execução em andamento.");
    this.job = null;
    const parsed = parseEditPlan(text);
    this.logger.setJobId("manual");
    if (!parsed.ok) {
      this.plan = null;
      this.logger.log(STEPS.LOAD_PLAN, LOG_STATUS.ERROR, { reason: parsed.error.code, message: parsed.error.message, target: source });
      this._set({ planFile: source, status: STATUS.ERROR, preview: null, report: null, jobId: "", message: parsed.error.message });
      return false;
    }
    this.plan = parsed.plan;
    this.logger.log(STEPS.LOAD_PLAN, LOG_STATUS.SUCCESS, { target: source });
    this._set({ planFile: source, status: STATUS.IDLE, preview: null, report: null, jobId: "", message: "Plano carregado." });
    return true;
  }

  /** MODO PREVIEW: valida e conta os itens do plano. */
  async analyze() {
    if (!this.plan) {
      this._set({ message: "Nenhum EDIT_PLAN carregado." });
      return null;
    }
    const t0 = Date.now();
    const preview = await analyzePlan(this.plan, this.fs);
    this.logger.log(STEPS.VALIDATE_PLAN, preview.validation.valid ? LOG_STATUS.SUCCESS : LOG_STATUS.ERROR, {
      duration_ms: Date.now() - t0,
      message: `${preview.validation.errors.length} erro(s), ${preview.validation.warnings.length} aviso(s)`,
    });
    this._set({
      preview,
      status: preview.validation.valid ? STATUS.IDLE : STATUS.ERROR,
      message: preview.validation.valid ? "Plano válido. Revise o preview e clique em EXECUTAR." : "Plano inválido.",
    });
    return preview;
  }

  /** Executa o plano carregado (manual ou job da fila). */
  async execute() {
    if (this.busy) return this.state.report;
    if (!this.plan) {
      this._set({ message: "Nenhum EDIT_PLAN carregado." });
      return null;
    }
    const job = this.job;
    const jobId = job ? job.jobId : (this.plan && this.plan.job_id) || "manual";
    this._set({ status: STATUS.PROCESSING, progress: 0, currentStep: "", report: null, jobId, message: "Executando..." });

    if (job && this.queue) {
      try {
        await this.queue.start(job);
        this.logger.log(STEPS.JOB_QUEUE, LOG_STATUS.SUCCESS, { target: job.fileName, message: "pending → processing" });
      } catch (e) {
        this.logger.log(STEPS.JOB_QUEUE, LOG_STATUS.ERROR, { target: job.fileName, message: String(e && /** @type {any} */ (e).message) });
      }
    }

    const { report, logger } = await executePlan(this.plan, {
      host: this.host,
      fs: this.fs,
      jobId,
      logger: new Logger({ jobId }),
      config: this.config,
      confirm: this.confirm,
      pause: this.pause,
      onStep: (step, i, total) => this._set({ currentStep: step, progress: i / total }),
    });
    // espelha as entradas do job no log do painel
    for (const e of logger.entries) this.logger.log(e.step, e.status, e);

    if (job && this.queue && job.state === "processing") {
      try {
        if (report.status === "failed") await this.queue.fail(job, report, logger.toJsonLines());
        else await this.queue.complete(job, report, logger.toJsonLines());
        this.logger.log(STEPS.JOB_QUEUE, LOG_STATUS.SUCCESS, { target: job.fileName, message: `processing → ${job.state}` });
      } catch (e) {
        this.logger.log(STEPS.JOB_QUEUE, LOG_STATUS.ERROR, { target: job.fileName, message: String(e && /** @type {any} */ (e).message) });
      }
    }

    this._set({
      status: report.status === "failed" ? STATUS.ERROR : STATUS.COMPLETE,
      progress: 1,
      currentStep: "",
      report,
      message: report.fatal ? report.fatal.message : "Execução concluída.",
    });
    if (job) this.job = null;
    await this.refreshEnvironment();
    return report;
  }

  togglePause() {
    if (!this.busy) return false;
    return this.pause.toggle();
  }

  // ------------------------------------------------------------ fila de jobs

  /**
   * Aplica novas configurações e religa a fila de jobs.
   * @param {Partial<import("./config").BridgeConfig>} overrides
   */
  async updateConfig(overrides) {
    this.config = resolveConfig(overrides);
    return this.connectQueue();
  }

  /** Liga a fila em `<workspaceRoot>/jobs`. */
  async connectQueue() {
    if (this.watcher) this.watcher.stop();
    this.watcher = null;
    this.queue = null;
    if (!this.config.workspaceRoot) return false;
    this.queue = new JobQueue({ fs: this.fs, root: this.config.workspaceRoot });
    await this.queue.init();
    this.watcher = new JobWatcher({
      queue: this.queue,
      intervalMs: this.config.pollIntervalMs,
      // não troca o plano enquanto há execução ou um job já carregado esperando
      isBusy: () => this.busy || this.job !== null,
      onJob: (fileName) => this.loadJob(fileName),
      onError: (e) => this.logger.log(STEPS.JOB_QUEUE, LOG_STATUS.ERROR, { message: String(e && e.message) }),
    });
    if (this.config.watchJobs) this.watcher.start();
    return true;
  }

  /** @param {string} fileName arquivo em jobs/pending */
  async loadJob(fileName) {
    if (!this.queue) return false;
    try {
      const job = await this.queue.load(fileName);
      this.job = job;
      this.plan = job.plan;
      this.logger.setJobId(job.jobId);
      this.logger.log(STEPS.LOAD_PLAN, LOG_STATUS.SUCCESS, { target: fileName, message: "Job carregado da fila." });
      this._set({ planFile: `jobs/pending/${fileName}`, jobId: job.jobId, status: STATUS.IDLE, report: null, message: `Job ${job.jobId} carregado.` });
      const preview = await this.analyze();
      if (this.config.autoExecuteJobs && preview && preview.canExecute) await this.execute();
      return true;
    } catch (e) {
      const err = /** @type {any} */ (e);
      this.logger.log(STEPS.LOAD_PLAN, LOG_STATUS.ERROR, { target: fileName, reason: err.code || "load_failed", message: err.message });
      try {
        await this.queue.reject(fileName, { code: err.code || "LOAD_FAILED", message: err.message });
      } catch (_) {
        /* ignora */
      }
      return false;
    }
  }

  dispose() {
    if (this.watcher) this.watcher.stop();
  }
}

module.exports = { BridgeController };
