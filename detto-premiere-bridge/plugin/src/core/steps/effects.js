// @ts-check
"use strict";

const { STEPS, LOG_STATUS } = require("../constants");

/**
 * Efeitos ainda não fazem parte da fase 1. O adaptador do host decide se o
 * efeito existe; se não, registra `{status: "fallback", reason: "effect_not_available"}`
 * e o job continua.
 *
 * @param {import("../executor").ExecutionContext} ctx
 */
async function applyEffects(ctx) {
  const { plan, host, logger, report, state } = ctx;
  const counter = report.summary.effects;
  const effects = Array.isArray(plan.effects) ? plan.effects : [];
  for (let i = 0; i < effects.length; i++) {
    await ctx.pause.checkpoint();
    const effect = effects[i];
    const target = effect.id ? String(effect.id) : `effects[${i}]`;
    const t0 = ctx.now();
    try {
      const r = await host.applyEffect(state.sequence, effect);
      if (r.applied) {
        counter.done++;
        logger.log(STEPS.APPLY_EFFECTS, LOG_STATUS.SUCCESS, { duration_ms: ctx.now() - t0, target, message: effect.name });
      } else {
        counter.fallback++;
        logger.log(STEPS.APPLY_EFFECTS, LOG_STATUS.FALLBACK, {
          duration_ms: ctx.now() - t0,
          target,
          reason: r.reason || "effect_not_available",
          message: `Efeito "${effect.name}" não disponível; ignorado.`,
        });
      }
    } catch (e) {
      counter.fallback++;
      logger.log(STEPS.APPLY_EFFECTS, LOG_STATUS.FALLBACK, {
        duration_ms: ctx.now() - t0,
        target,
        reason: "effect_not_available",
        message: e instanceof Error ? e.message : String(e),
      });
    }
  }
}

module.exports = { applyEffects };
