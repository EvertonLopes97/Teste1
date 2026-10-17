// @ts-check
"use strict";

const { STEPS, LOG_STATUS } = require("../constants");
const paths = require("../paths");

/**
 * Verifica no disco cada mídia do plano. Mídias ausentes são registradas
 * como erro, mas não interrompem o job: só os cortes que dependem delas são ignorados.
 *
 * @param {import("../executor").ExecutionContext} ctx
 */
async function checkMedia(ctx) {
  const { plan, fs, logger, report, state } = ctx;
  for (const m of plan.media) {
    const t0 = ctx.now();
    const exists = await fs.exists(m.path);
    if (exists) {
      state.availableMedia.set(m.id, m.path);
      logger.log(STEPS.CHECK_MEDIA, LOG_STATUS.SUCCESS, { duration_ms: ctx.now() - t0, target: m.id });
    } else {
      report.summary.media.missing++;
      logger.log(STEPS.CHECK_MEDIA, LOG_STATUS.ERROR, {
        duration_ms: ctx.now() - t0,
        target: m.id,
        reason: "media_not_found",
        message: `Arquivo de mídia não encontrado: ${m.path}`,
      });
    }
  }
}

/**
 * Importa para o projeto as mídias disponíveis que ainda não estão nele.
 * Arquivos já importados (mesmo caminho) são reutilizados — nunca duplicados.
 *
 * @param {import("../executor").ExecutionContext} ctx
 */
async function importMedia(ctx) {
  const { plan, host, logger, report, state, config } = ctx;
  const t0 = ctx.now();

  /** @type {Map<string, any>} caminho normalizado → item do projeto */
  const inProject = new Map();
  for (const { path, item } of await host.listMediaItems()) inProject.set(paths.normalizeForCompare(path), item);

  /** @type {Map<string, string>} caminho normalizado → caminho original (para importar) */
  const toImport = new Map();
  for (const m of plan.media) {
    const p = state.availableMedia.get(m.id);
    if (!p) continue;
    const key = paths.normalizeForCompare(p);
    if (inProject.has(key)) continue;
    toImport.set(key, p);
  }

  if (toImport.size > 0) {
    await ctx.pause.checkpoint();
    try {
      const bin = await host.ensureBin(config.mediaBinName);
      const imported = await host.importFiles([...toImport.values()], bin);
      for (const { path, item } of imported) inProject.set(paths.normalizeForCompare(path), item);
    } catch (e) {
      // segue: cada mídia não importada vira um erro individual abaixo
      logger.log(STEPS.IMPORT_MEDIA, LOG_STATUS.ERROR, {
        reason: "import_call_failed",
        message: e instanceof Error ? e.message : String(e),
      });
    }
  }

  /** @type {Set<string>} */
  const counted = new Set();
  for (const m of plan.media) {
    const p = state.availableMedia.get(m.id);
    if (!p) continue;
    const key = paths.normalizeForCompare(p);
    const item = inProject.get(key);
    if (!item) {
      report.summary.media.failed++;
      logger.log(STEPS.IMPORT_MEDIA, LOG_STATUS.ERROR, {
        target: m.id,
        reason: "import_failed",
        message: `Premiere não importou: ${p}`,
      });
      continue;
    }
    state.mediaItems.set(m.id, { item, path: p });
    if (counted.has(key)) {
      // mesmo arquivo declarado com outro id: compartilha o item já importado
      report.summary.media.skipped++;
      logger.log(STEPS.IMPORT_MEDIA, LOG_STATUS.SKIPPED, { target: m.id, reason: "duplicate_file_in_plan" });
      continue;
    }
    counted.add(key);
    if (toImport.has(key)) {
      report.summary.media.imported++;
      report.summary.media.done++;
      logger.log(STEPS.IMPORT_MEDIA, LOG_STATUS.SUCCESS, { target: m.id, message: `Importado: ${p}` });
    } else {
      report.summary.media.reused++;
      report.summary.media.done++;
      logger.log(STEPS.IMPORT_MEDIA, LOG_STATUS.SKIPPED, { target: m.id, reason: "already_in_project" });
    }
  }

  logger.log(STEPS.IMPORT_MEDIA, LOG_STATUS.INFO, {
    duration_ms: ctx.now() - t0,
    message: `${report.summary.media.imported} importadas, ${report.summary.media.reused} reutilizadas.`,
  });
}

module.exports = { checkMedia, importMedia };
