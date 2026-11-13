// @ts-check
"use strict";

const { STEPS, LOG_STATUS, TRACK_LAYOUT } = require("../constants");
const { fpsEquals } = require("../time");
const paths = require("../paths");

/**
 * Reutiliza a sequência do plano se existir; senão cria.
 * Se a sequência existente já tiver clips, pede confirmação antes de editar;
 * sem confirmação, cria uma nova sequência com sufixo de data (não destrutivo).
 *
 * @param {import("../executor").ExecutionContext} ctx
 */
async function ensureSequence(ctx) {
  const { plan, host, logger, report, state, config } = ctx;
  const t0 = ctx.now();
  const wanted = plan.sequence;
  let name = wanted.name;
  let seq = await host.findSequence(name);

  if (seq) {
    const info = await host.getSequenceInfo(seq);
    if (info.clipCount > 0) {
      const ok = await ctx.confirm(
        `A sequência "${name}" já possui ${info.clipCount} clip(s). Os cortes do plano podem sobrescrever trechos dela.\n` +
          `Confirmar edição da sequência existente? (Não = criar uma nova sequência)`
      );
      if (!ok) {
        name = `${wanted.name}_${paths.fileTimestamp(ctx.clock())}`;
        seq = null;
        logger.log(STEPS.ENSURE_SEQUENCE, LOG_STATUS.INFO, {
          reason: "existing_sequence_preserved",
          message: `Sequência original preservada; criando "${name}".`,
        });
      }
    }
  }

  if (seq) {
    report.sequence.reused = true;
  } else {
    seq = await host.createSequence(name, { presetPath: wanted.preset || config.sequencePresetPath || undefined });
    report.sequence.created = true;
    const applied = await host.applySequenceSettings(seq, { fps: wanted.fps, width: wanted.width, height: wanted.height });
    if (!applied.applied) {
      logger.log(STEPS.ENSURE_SEQUENCE, LOG_STATUS.FALLBACK, {
        reason: applied.reason || "sequence_settings_not_available",
        message: "Não foi possível aplicar FPS/resolução via API; use um preset (.sqpreset) com as configurações do plano.",
      });
    }
  }

  const info = await host.getSequenceInfo(seq);
  if (info.fps && !fpsEquals(info.fps, wanted.fps)) {
    logger.log(STEPS.ENSURE_SEQUENCE, LOG_STATUS.FALLBACK, {
      reason: "fps_mismatch",
      message: `Sequência está em ${info.fps}fps e o plano pede ${wanted.fps}fps. Tempos serão posicionados em segundos.`,
      details: { sequence_fps: info.fps, plan_fps: wanted.fps },
    });
  }
  if (info.width && info.height && (info.width !== wanted.width || info.height !== wanted.height)) {
    logger.log(STEPS.ENSURE_SEQUENCE, LOG_STATUS.WARNING, {
      reason: "resolution_mismatch",
      message: `Sequência ${info.width}x${info.height}, plano ${wanted.width}x${wanted.height}.`,
    });
  }

  await host.setActiveSequence(seq);
  state.sequence = seq;
  state.sequenceInfo = info;
  report.sequence.name = info.name || name;
  logger.log(STEPS.ENSURE_SEQUENCE, LOG_STATUS.SUCCESS, {
    duration_ms: ctx.now() - t0,
    target: report.sequence.name,
    message: report.sequence.created ? "Sequência criada." : "Sequência reutilizada.",
  });
  return seq;
}

/**
 * Prepara a estrutura de tracks DETTO (V1..V5 / A1..A4): verifica se existem
 * e tenta nomeá-las. Criar tracks não tem suporte confiável na API UXP atual,
 * então tracks ausentes viram fallback (use um preset com 5V/4A).
 *
 * @param {import("../executor").ExecutionContext} ctx
 */
async function ensureTracks(ctx) {
  const { host, logger, state } = ctx;
  const t0 = ctx.now();
  const info = state.sequenceInfo || (await host.getSequenceInfo(state.sequence));
  /** @type {string[]} */
  const missing = [];
  /** @type {string[]} */
  const notRenamed = [];

  for (const kind of /** @type {const} */ (["video", "audio"])) {
    const count = kind === "video" ? info.videoTrackCount : info.audioTrackCount;
    for (const t of TRACK_LAYOUT[kind]) {
      if (t.index >= count) {
        missing.push(t.id);
        continue;
      }
      state.availableTracks[kind].add(t.index);
      let renamed = false;
      try {
        renamed = await host.renameTrack(state.sequence, kind, t.index, t.role);
      } catch (_) {
        renamed = false;
      }
      if (!renamed) notRenamed.push(t.id);
    }
  }

  if (missing.length) {
    logger.log(STEPS.ENSURE_TRACKS, LOG_STATUS.FALLBACK, {
      reason: "track_creation_not_available",
      message: `Tracks ausentes na sequência: ${missing.join(", ")}. Itens destinados a elas serão ignorados.`,
      details: { missing },
    });
  }
  if (notRenamed.length) {
    logger.log(STEPS.ENSURE_TRACKS, LOG_STATUS.FALLBACK, {
      reason: "track_rename_not_available",
      message: `Não foi possível nomear: ${notRenamed.join(", ")}. Estrutura segue o layout DETTO por índice.`,
      details: { tracks: notRenamed },
    });
  }
  logger.log(STEPS.ENSURE_TRACKS, LOG_STATUS.SUCCESS, {
    duration_ms: ctx.now() - t0,
    message: `Vídeo: ${info.videoTrackCount} tracks, Áudio: ${info.audioTrackCount} tracks.`,
  });
}

module.exports = { ensureSequence, ensureTracks };
