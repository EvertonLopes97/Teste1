"use strict";

/**
 * Bootstrap do painel DETTO VIDEO ENGINE.
 * Liga: UI (src/ui) ↔ BridgeController (src/core) ↔ adaptadores Premiere/UXP (src/host).
 */

const { BridgeController } = require("./core/controller");
const { STEPS, LOG_STATUS } = require("./core/constants");
const paths = require("./core/paths");
const { PremiereHost } = require("./host/premiereHost");
const { UxpFileSystem } = require("./host/uxpFs");
const panel = require("./ui/panel");
const dialogs = require("./ui/dialogs");
const { loadSettings, saveSettings } = require("./ui/settings");

const ENV_REFRESH_MS = 3000;

let platform = "";
try {
  platform = require("os").platform();
} catch (_) {
  /* indisponível em versões antigas do UXP */
}

const host = new PremiereHost();
const fs = new UxpFileSystem({ platform });
let settings = loadSettings();

const controller = new BridgeController({ host, fs, config: settings, confirm: dialogs.confirmDialog });
controller.subscribe(panel.renderState);
controller.logger.subscribe(panel.appendLog);

const $ = (id) => document.getElementById(id);

/** Envolve handlers: erros viram mensagem no painel + entrada de log, nunca exceção solta. */
function action(name, fn) {
  return async () => {
    try {
      await fn();
    } catch (e) {
      const message = e && e.message ? e.message : String(e);
      controller.logger.log(name, LOG_STATUS.ERROR, { message });
      controller.setMessage(message);
    }
  };
}

// ------------------------------------------------------------------ botões

$("btn-load").addEventListener(
  "click",
  action(STEPS.LOAD_PLAN, async () => {
    const file = await dialogs.pickFile(["json"]);
    if (!file) return;
    controller.loadPlanText(await file.read(), file.path);
  })
);

$("btn-analyze").addEventListener("click", action(STEPS.VALIDATE_PLAN, () => controller.analyze()));

const execute = action("EXECUTE", () => controller.execute());
$("btn-execute").addEventListener("click", execute);
$("btn-execute-preview").addEventListener("click", execute);

$("btn-pause").addEventListener("click", () => controller.togglePause());

$("btn-render").addEventListener("click", () => {
  // Fase 2: EncoderManager.exportSequence / fila do Media Encoder.
  controller.logger.log(STEPS.RENDER, LOG_STATUS.FALLBACK, {
    reason: "render_not_implemented",
    message: "Render/export será habilitado na fase 2 do Bridge.",
  });
  controller.setMessage("RENDERIZAR: disponível na fase 2.");
});

$("btn-open").addEventListener(
  "click",
  action("OPEN_PROJECT", async () => {
    const file = await dialogs.pickFile(["prproj"]);
    if (!file) return;
    const info = await host.openProject(file.path);
    controller.logger.log("OPEN_PROJECT", LOG_STATUS.SUCCESS, { target: info.path });
    await controller.refreshEnvironment();
  })
);

$("btn-log").addEventListener("click", panel.toggleLog);
$("btn-log-clear").addEventListener("click", () => {
  controller.logger.clear();
  panel.clearLog();
});
$("btn-log-export").addEventListener(
  "click",
  action("EXPORT_LOG", async () => {
    let dir = controller.config.workspaceRoot ? paths.join(controller.config.workspaceRoot, "logs") : await dialogs.pickFolder();
    if (!dir) return;
    await fs.mkdirp(dir);
    const target = paths.join(dir, `panel-${paths.fileTimestamp()}.log.jsonl`);
    await fs.writeText(target, controller.logger.toJsonLines());
    controller.setMessage(`Log exportado: ${target}`);
  })
);

// ------------------------------------------------------------------ configurações

function renderSettings() {
  $("cfg-root").textContent = settings.workspaceRoot || "-";
  $("cfg-preset").textContent = settings.sequencePresetPath || "-";
  $("cfg-watch").checked = settings.watchJobs !== false;
  $("cfg-autoexec").checked = !!settings.autoExecuteJobs;
  $("cfg-save").checked = settings.saveAfterExecute !== false;
  $("cfg-backup").checked = settings.backupEnabled !== false;
}

async function applySettings(patch) {
  settings = { ...settings, ...patch };
  saveSettings(settings);
  renderSettings();
  const connected = await controller.updateConfig(settings);
  if (connected) controller.setMessage(`Fila de jobs: ${paths.join(settings.workspaceRoot, "jobs")}`);
}

$("btn-cfg-root").addEventListener(
  "click",
  action("SETTINGS", async () => {
    const dir = await dialogs.pickFolder();
    if (dir) await applySettings({ workspaceRoot: dir });
  })
);
$("btn-cfg-preset").addEventListener(
  "click",
  action("SETTINGS", async () => {
    const file = await dialogs.pickFile(["sqpreset"]);
    if (file) await applySettings({ sequencePresetPath: file.path });
  })
);
for (const [id, key] of [
  ["cfg-watch", "watchJobs"],
  ["cfg-autoexec", "autoExecuteJobs"],
  ["cfg-save", "saveAfterExecute"],
  ["cfg-backup", "backupEnabled"],
]) {
  $(id).addEventListener("change", action("SETTINGS", () => applySettings({ [key]: $(id).checked })));
}

// ------------------------------------------------------------------ inicialização

async function start() {
  renderSettings();
  const env = await controller.refreshEnvironment();
  controller.logger.log(STEPS.DETECT_ENVIRONMENT, env.connected ? LOG_STATUS.SUCCESS : LOG_STATUS.ERROR, {
    message: `Premiere ${env.premiereVersion || "?"} · UXP ${env.uxpVersion || "?"}`,
  });
  if (settings.workspaceRoot) await controller.connectQueue();

  setInterval(() => {
    if (!controller.busy) controller.refreshEnvironment();
  }, ENV_REFRESH_MS);
}

start().catch((e) => controller.setMessage(String(e && e.message)));
