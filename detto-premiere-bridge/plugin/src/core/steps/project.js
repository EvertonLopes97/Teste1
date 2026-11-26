// @ts-check
"use strict";

const { STEPS, LOG_STATUS } = require("../constants");
const { BridgeError } = require("../errors");
const paths = require("../paths");

/**
 * Garante que existe um projeto aberto para receber o plano:
 *  1. `plan.project.path` informado → reutiliza se já ativo, abre se existir, cria se não existir;
 *  2. sem caminho → reutiliza o projeto ativo;
 *  3. nenhum projeto ativo → cria em `config.projectsDir` (se permitido).
 * Nunca fecha nem sobrescreve o projeto do usuário.
 *
 * @param {import("../executor").ExecutionContext} ctx
 */
async function ensureProject(ctx) {
  const { host, fs, plan, config, report, logger } = ctx;
  const t0 = ctx.now();
  const wantedPath = plan.project.path ? String(plan.project.path) : "";
  const active = await host.getActiveProject();

  /** @type {import("../types").ProjectInfo} */
  let project;
  let action = "reused";

  if (wantedPath) {
    if (active && active.path && paths.normalizeForCompare(active.path) === paths.normalizeForCompare(wantedPath)) {
      project = active;
    } else if (await fs.exists(wantedPath)) {
      project = await host.openProject(wantedPath);
      action = "opened";
    } else {
      project = await createNewProject(ctx, wantedPath);
      action = "created";
    }
  } else if (active) {
    project = active;
    if (active.name && stripPrproj(active.name) !== plan.project.name) {
      logger.log(STEPS.ENSURE_PROJECT, LOG_STATUS.WARNING, {
        reason: "project_name_differs",
        message: `Usando o projeto ativo "${active.name}" (plano pede "${plan.project.name}").`,
      });
    }
  } else {
    const target = paths.join(config.projectsDir || "", `${plan.project.name}.prproj`);
    if (!config.allowCreateProject || !config.projectsDir) {
      throw new BridgeError(
        "PROJECT_NOT_FOUND",
        "Nenhum projeto aberto no Premiere e a criação automática de projetos está desativada."
      );
    }
    project = await createNewProject(ctx, target);
    action = "created";
  }

  ctx.state.project = project;
  report.project.name = project.name;
  report.project.path = project.path;
  report.project.created = action === "created";
  report.project.opened = action === "opened";
  logger.log(STEPS.ENSURE_PROJECT, LOG_STATUS.SUCCESS, {
    duration_ms: ctx.now() - t0,
    target: project.path || project.name,
    message: `Projeto ${action === "created" ? "criado" : action === "opened" ? "aberto" : "reutilizado"}: ${project.name}`,
    details: { action },
  });
  return project;
}

/**
 * @param {import("../executor").ExecutionContext} ctx
 * @param {string} target
 */
async function createNewProject(ctx, target) {
  if (!ctx.config.allowCreateProject) {
    throw new BridgeError("PROJECT_NOT_FOUND", `Projeto não encontrado: ${target}`);
  }
  if (await ctx.fs.exists(target)) {
    // nunca sobrescrever um arquivo existente
    throw new BridgeError("PROJECT_EXISTS", `Já existe um arquivo em ${target}; não será sobrescrito.`);
  }
  const dir = paths.dirname(target);
  if (dir) await ctx.fs.mkdirp(dir);
  return ctx.host.createProject(target);
}

/**
 * Copia o .prproj salvo em disco para a pasta de backups antes das alterações.
 * Não salva o projeto (isso alteraria o original); copia o último estado salvo.
 * Se o backup falhar, pede confirmação para seguir sem ele.
 *
 * @param {import("../executor").ExecutionContext} ctx
 */
async function backupProject(ctx) {
  const { fs, config, report, logger } = ctx;
  const project = ctx.state.project;
  const t0 = ctx.now();

  if (!config.backupEnabled) {
    logger.log(STEPS.BACKUP_PROJECT, LOG_STATUS.SKIPPED, { reason: "backup_disabled" });
    return;
  }
  if (report.project.created) {
    logger.log(STEPS.BACKUP_PROJECT, LOG_STATUS.SKIPPED, { reason: "new_project" });
    return;
  }
  if (!project || !project.path || !(await fs.exists(project.path))) {
    const ok = await ctx.confirm(
      "O projeto ativo ainda não foi salvo em disco, então não é possível criar backup. Continuar mesmo assim?"
    );
    if (!ok) throw new BridgeError("CANCELLED_BY_USER", "Execução cancelada: projeto sem backup.");
    logger.log(STEPS.BACKUP_PROJECT, LOG_STATUS.WARNING, { reason: "project_not_saved", message: "Seguindo sem backup (confirmado)." });
    return;
  }

  const backupDir = config.backupDir || paths.join(paths.dirname(project.path), "detto-backups");
  const stem = `${paths.stripExtension(project.path)}_${paths.fileTimestamp(ctx.clock())}`;
  let target = paths.join(backupDir, `${stem}.prproj`);
  try {
    await fs.mkdirp(backupDir);
    // nunca sobrescreve um backup anterior (duas execuções no mesmo segundo)
    for (let n = 1; await fs.exists(target); n++) target = paths.join(backupDir, `${stem}-${n}.prproj`);
    await fs.copyFile(project.path, target);
    report.project.backup = target;
    logger.log(STEPS.BACKUP_PROJECT, LOG_STATUS.SUCCESS, { duration_ms: ctx.now() - t0, target });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    logger.log(STEPS.BACKUP_PROJECT, LOG_STATUS.ERROR, { duration_ms: ctx.now() - t0, reason: "backup_failed", message });
    const ok = await ctx.confirm(`Falha ao criar backup (${message}). Continuar sem backup?`);
    if (!ok) throw new BridgeError("CANCELLED_BY_USER", "Execução cancelada: backup falhou.");
  }
}

/** @param {string} name */
function stripPrproj(name) {
  return name.replace(/\.prproj$/i, "");
}

module.exports = { ensureProject, backupProject };
