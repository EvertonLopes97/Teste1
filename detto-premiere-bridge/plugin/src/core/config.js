// @ts-check
"use strict";

const paths = require("./paths");

/**
 * @typedef {Object} BridgeConfig
 * @property {string}  workspaceRoot        pasta "detto-video-engine" (contém jobs/, logs/, backups/, projects/)
 * @property {string}  projectsDir          onde criar projetos novos
 * @property {string}  backupDir            onde copiar backups do .prproj ("" = ao lado do projeto)
 * @property {boolean} backupEnabled
 * @property {boolean} allowCreateProject   criar projeto se nenhum estiver aberto
 * @property {boolean} saveAfterExecute     salvar o projeto ao final
 * @property {string}  sequencePresetPath   .sqpreset usado ao criar sequências (recomendado: 5V/4A)
 * @property {string}  mediaBinName         bin onde a mídia é importada
 * @property {boolean} watchJobs            observar jobs/pending
 * @property {boolean} autoExecuteJobs      executar automaticamente jobs carregados da fila
 * @property {number}  pollIntervalMs
 */

/** @type {BridgeConfig} */
const DEFAULT_CONFIG = Object.freeze({
  workspaceRoot: "",
  projectsDir: "",
  backupDir: "",
  backupEnabled: true,
  allowCreateProject: true,
  saveAfterExecute: true,
  sequencePresetPath: "",
  mediaBinName: "DETTO_MEDIA",
  watchJobs: true,
  autoExecuteJobs: false,
  pollIntervalMs: 3000,
});

/**
 * Mescla a configuração do usuário com os padrões e deriva pastas
 * a partir de `workspaceRoot` quando não informadas.
 * @param {Partial<BridgeConfig>} [overrides]
 * @returns {BridgeConfig}
 */
function resolveConfig(overrides = {}) {
  /** @type {BridgeConfig} */
  const cfg = { ...DEFAULT_CONFIG, ...stripUndefined(overrides) };
  if (cfg.workspaceRoot) {
    if (!cfg.projectsDir) cfg.projectsDir = paths.join(cfg.workspaceRoot, "projects");
    if (!cfg.backupDir) cfg.backupDir = paths.join(cfg.workspaceRoot, "backups");
  }
  return cfg;
}

/** @param {Record<string, any>} o */
function stripUndefined(o) {
  /** @type {Record<string, any>} */
  const out = {};
  for (const [k, v] of Object.entries(o || {})) if (v !== undefined) out[k] = v;
  return out;
}

module.exports = { DEFAULT_CONFIG, resolveConfig };
