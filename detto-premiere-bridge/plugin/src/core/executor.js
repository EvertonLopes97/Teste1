// @ts-check
"use strict";

const { STEPS, LOG_STATUS } = require("./constants");
const { validateEditPlan } = require("./schema");
const { BridgeError } = require("./errors");
const { Logger } = require("./logger");
const { PauseController } = require("./pause");
const { resolveConfig } = require("./config");
const { createReport, finalizeReport } = require("./report");
const { ensureProject, backupProject } = require("./steps/project");
const { checkMedia, importMedia } = require("./steps/media");
const { ensureSequence, ensureTracks } = require("./steps/sequence");
const { placeClips } = require("./steps/clips");
const { createMarkers, createGraphicsPlaceholders, createVfxPlaceholders } = require("./steps/markers");
const { applyEffects } = require("./steps/effects");

/**
 * @typedef {Object} ExecutionState
 * @property {import("./types").ProjectInfo|null} project
 * @property {any} sequence
 * @property {import("./types").SequenceInfo|null} sequenceInfo
 * @property {Map<string, string>} availableMedia            id → caminho existente no disco
 * @property {Map<string, {item: any, path: string}>} mediaItems  id → item do projeto
 * @property {{video: Set<number>, audio: Set<number>}} availableTracks
 * @property {Array<{name: string, start: number}>|null} existingMarkers
 *
 * @typedef {Object} ExecutionContext
 * @property {any} plan
 * @property {import("./types").HostAdapter} host
 * @property {import("./types").FileSystemAdapter} fs
 * @property {Logger} logger
 * @property {import("./config").BridgeConfig} config
 * @property {(message: string) => Promise<boolean>} confirm
 * @property {PauseController} pause
 * @property {import("./report").ExecutionReport} report
 * @property {ExecutionState} state
 * @property {() => number} now
 * @property {() => Date} clock
 *
 * @typedef {Object} ExecuteOptions
 * @property {import("./types").HostAdapter} host
 * @property {import("./types").FileSystemAdapter} fs
 * @property {string} [jobId]
 * @property {Logger} [logger]
 * @property {Partial<import("./config").BridgeConfig>} [config]
 * @property {(message: string) => Promise<boolean>} [confirm]   padrão: recusa (modo seguro)
 * @property {PauseController} [pause]
 * @property {(step: string, index: number, total: number) => void} [onStep]
 * @property {() => number} [now]
 * @property {() => Date} [clock]
 */

/**
 * Ordem do pipeline da fase 1. Cada passo recebe o contexto compartilhado.
 * Exceções em passos marcados `fatal` interrompem o job.
 */
const PIPELINE = [
  { step: STEPS.CHECK_MEDIA, run: checkMedia },
  { step: STEPS.ENSURE_PROJECT, run: ensureProject },
  { step: STEPS.BACKUP_PROJECT, run: backupProject },
  { step: STEPS.IMPORT_MEDIA, run: importMedia },
  { step: STEPS.ENSURE_SEQUENCE, run: ensureSequence },
  { step: STEPS.ENSURE_TRACKS, run: ensureTracks },
  { step: STEPS.PLACE_CLIPS, run: placeClips },
  { step: STEPS.CREATE_MARKERS, run: createMarkers },
  { step: STEPS.GRAPHICS_PLACEHOLDERS, run: createGraphicsPlaceholders },
  { step: STEPS.VFX_PLACEHOLDERS, run: createVfxPlaceholders },
  { step: STEPS.APPLY_EFFECTS, run: applyEffects },
];

/**
 * Executa um EDIT_PLAN no Premiere através do adaptador `host`.
 * Nunca lança: o resultado (sucesso ou falha) está sempre no relatório.
 *
 * @param {any} plan
 * @param {ExecuteOptions} opts
 * @returns {Promise<{report: import("./report").ExecutionReport, logger: Logger}>}
 */
async function executePlan(plan, opts) {
  const now = opts.now || (() => Date.now());
  const clock = opts.clock || (() => new Date());
  const jobId = opts.jobId || (plan && plan.job_id) || "manual";
  const logger = opts.logger || new Logger({ jobId, now, clock });
  logger.setJobId(jobId);
  const firstEntry = logger.entries.length;
  const report = createReport(jobId, plan, clock());

  /** @type {ExecutionContext} */
  const ctx = {
    plan,
    host: opts.host,
    fs: opts.fs,
    logger,
    config: resolveConfig(opts.config),
    confirm: opts.confirm || (async () => false),
    pause: opts.pause || new PauseController(),
    report,
    now,
    clock,
    state: {
      project: null,
      sequence: null,
      sequenceInfo: null,
      availableMedia: new Map(),
      mediaItems: new Map(),
      availableTracks: { video: new Set(), audio: new Set() },
      existingMarkers: null,
    },
  };

  const total = PIPELINE.length + 3;
  try {
    // 1. validação
    opts.onStep && opts.onStep(STEPS.VALIDATE_PLAN, 0, total);
    const t0 = now();
    const validation = validateEditPlan(plan);
    report.validation_warnings = validation.warnings;
    if (!validation.valid) {
      logger.log(STEPS.VALIDATE_PLAN, LOG_STATUS.ERROR, {
        duration_ms: now() - t0,
        reason: "invalid_plan",
        message: validation.errors.map((e) => `${e.path}: ${e.message}`).join(" | "),
        details: validation.errors,
      });
      throw new BridgeError("INVALID_PLAN", `EDIT_PLAN inválido (${validation.errors.length} erro(s)).`, validation.errors);
    }
    logger.log(STEPS.VALIDATE_PLAN, LOG_STATUS.SUCCESS, {
      duration_ms: now() - t0,
      message: `${validation.warnings.length} aviso(s).`,
      ...(validation.warnings.length ? { details: validation.warnings } : {}),
    });

    // 2. ambiente
    opts.onStep && opts.onStep(STEPS.DETECT_ENVIRONMENT, 1, total);
    const env = await logger.time(STEPS.DETECT_ENVIRONMENT, () => opts.host.getEnvironment());
    report.environment = env;
    if (!env.connected) throw new BridgeError("PREMIERE_DISCONNECTED", "Premiere Pro não está conectado.");

    // 3. pipeline
    for (let i = 0; i < PIPELINE.length; i++) {
      await ctx.pause.checkpoint();
      opts.onStep && opts.onStep(PIPELINE[i].step, i + 2, total);
      try {
        await PIPELINE[i].run(ctx);
      } catch (e) {
        if (!(e instanceof BridgeError)) {
          // erro inesperado da API: registra no passo e interrompe (estado incerto)
          logger.log(PIPELINE[i].step, LOG_STATUS.ERROR, {
            reason: "exception",
            message: e instanceof Error ? e.message : String(e),
          });
          throw new BridgeError("STEP_FAILED", `Falha em ${PIPELINE[i].step}: ${e instanceof Error ? e.message : e}`);
        }
        throw e;
      }
    }

    // 4. salvar
    opts.onStep && opts.onStep(STEPS.SAVE_PROJECT, total - 1, total);
    if (ctx.config.saveAfterExecute) {
      try {
        await logger.time(STEPS.SAVE_PROJECT, () => opts.host.saveProject());
      } catch (_) {
        /* já registrado; o trabalho na timeline continua válido */
      }
    } else {
      logger.log(STEPS.SAVE_PROJECT, LOG_STATUS.SKIPPED, { reason: "save_disabled" });
    }
  } catch (e) {
    const code = e instanceof BridgeError ? e.code : "UNEXPECTED";
    const message = e instanceof Error ? e.message : String(e);
    report.fatal = { code, message };
    logger.log("JOB", LOG_STATUS.ERROR, { reason: code, message });
  }

  finalizeReport(report, logger.entries.slice(firstEntry), clock());
  return { report, logger };
}

module.exports = { executePlan, PIPELINE };
