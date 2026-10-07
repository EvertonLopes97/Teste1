// @ts-check
"use strict";

const { STEPS, LOG_STATUS } = require("../constants");
const { snapToFrame, timesEqual } = require("../time");
const { tracksForCut } = require("../tracks");
const { ApiNotAvailableError } = require("../errors");
const paths = require("../paths");

/**
 * Insere os cortes do plano na timeline (overwrite nas tracks DETTO).
 * Cada corte é independente: falhas são registradas e o processo continua.
 * Clips já presentes (mesma mídia, mesma posição e duração) não são duplicados.
 *
 * @param {import("../executor").ExecutionContext} ctx
 */
async function placeClips(ctx) {
  const { plan, host, logger, report, state } = ctx;
  const counter = report.summary.cuts;
  const fps = plan.sequence.fps;
  const halfFrame = 0.5 / fps;
  /** @type {Map<any, number|null>} */
  const durations = new Map();
  /** @type {Map<number, import("../types").TimelineClip[]>} */
  const trackCache = new Map();
  /** @type {Set<string>} */
  const seen = new Set();

  const cuts = Array.isArray(plan.cuts) ? plan.cuts : [];
  for (let i = 0; i < cuts.length; i++) {
    await ctx.pause.checkpoint();
    const cut = cuts[i];
    const target = cut.id ? String(cut.id) : `cuts[${i}]`;
    const t0 = ctx.now();
    const fail = (/** @type {string} */ status, /** @type {string} */ reason, /** @type {string} */ message) => {
      if (status === LOG_STATUS.ERROR) counter.failed++;
      else if (status === LOG_STATUS.FALLBACK) counter.fallback++;
      else counter.skipped++;
      logger.log(STEPS.PLACE_CLIPS, status, { duration_ms: ctx.now() - t0, target, reason, message });
    };

    const media = state.mediaItems.get(cut.source);
    if (!media) {
      fail(LOG_STATUS.ERROR, "media_unavailable", `Mídia "${cut.source}" indisponível (ausente ou não importada).`);
      continue;
    }

    const { video, audio } = tracksForCut(cut);
    if (!video || !state.availableTracks.video.has(video.index)) {
      fail(LOG_STATUS.ERROR, "track_unavailable", `Track de vídeo ${video ? video.id : cut.track} não existe na sequência.`);
      continue;
    }
    if (!audio || !state.availableTracks.audio.has(audio.index)) {
      fail(LOG_STATUS.ERROR, "track_unavailable", `Track de áudio ${audio ? audio.id : cut.audioTrack} não existe na sequência.`);
      continue;
    }

    const inPoint = snapToFrame(cut.start, fps);
    const outPoint = snapToFrame(cut.end, fps);
    const timelineStart = snapToFrame(cut.timeline, fps);
    if (outPoint <= inPoint) {
      fail(LOG_STATUS.ERROR, "invalid_range", `Intervalo vazio após alinhar a ${fps}fps (${cut.start}–${cut.end}).`);
      continue;
    }

    if (!durations.has(media.item)) {
      let d = null;
      try {
        d = await host.getMediaDuration(media.item);
      } catch (_) {
        d = null;
      }
      durations.set(media.item, d);
    }
    const mediaDuration = durations.get(media.item);
    if (typeof mediaDuration === "number" && outPoint > mediaDuration + halfFrame) {
      fail(
        LOG_STATUS.ERROR,
        "clip_out_of_range",
        `Corte fora do intervalo: end=${outPoint.toFixed(3)}s, mídia "${cut.source}" tem ${mediaDuration.toFixed(3)}s.`
      );
      continue;
    }

    const key = [paths.normalizeForCompare(media.path), inPoint, outPoint, timelineStart, video.index].join("|");
    if (seen.has(key)) {
      fail(LOG_STATUS.SKIPPED, "duplicate_in_plan", "Corte idêntico já processado neste plano.");
      continue;
    }
    seen.add(key);

    if (!trackCache.has(video.index)) {
      /** @type {import("../types").TimelineClip[]} */
      let clips = [];
      try {
        clips = await host.listTrackClips(state.sequence, "video", video.index);
      } catch (_) {
        clips = [];
      }
      trackCache.set(video.index, clips);
    }
    const existing = /** @type {import("../types").TimelineClip[]} */ (trackCache.get(video.index));
    const length = outPoint - inPoint;
    const already = existing.some(
      (c) =>
        paths.normalizeForCompare(c.mediaPath) === paths.normalizeForCompare(media.path) &&
        timesEqual(c.start, timelineStart, halfFrame) &&
        timesEqual(c.end - c.start, length, halfFrame)
    );
    if (already) {
      fail(LOG_STATUS.SKIPPED, "already_exists", `Clip já existe em ${video.id} @ ${timelineStart.toFixed(3)}s.`);
      continue;
    }

    try {
      await host.placeClip(state.sequence, media.item, {
        inPoint,
        outPoint,
        timelineStart,
        videoTrackIndex: video.index,
        audioTrackIndex: audio.index,
      });
      existing.push({ start: timelineStart, end: timelineStart + length, mediaPath: media.path });
      counter.done++;
      logger.log(STEPS.PLACE_CLIPS, LOG_STATUS.SUCCESS, {
        duration_ms: ctx.now() - t0,
        target,
        message: `${cut.source} [${inPoint.toFixed(3)}–${outPoint.toFixed(3)}] → ${video.id}/${audio.id} @ ${timelineStart.toFixed(3)}s`,
      });
    } catch (e) {
      const unavailable = e instanceof ApiNotAvailableError;
      fail(
        unavailable ? LOG_STATUS.FALLBACK : LOG_STATUS.ERROR,
        unavailable ? /** @type {any} */ (e).code : "place_failed",
        e instanceof Error ? e.message : String(e)
      );
    }
  }
}

module.exports = { placeClips };
