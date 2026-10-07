"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { executePlan } = require("../plugin/src/core/executor");
const { PauseController } = require("../plugin/src/core/pause");
const { basePlan, scenario, fakeClock } = require("./helpers/fixtures");

/** Executa o plano no cenário e devolve tudo para as asserções. */
async function run(plan, { hostOpts, files, confirm, config, setup, pause } = {}) {
  const sc = scenario(hostOpts, files);
  if (setup) setup(sc);
  const { report, logger } = await executePlan(plan, {
    host: sc.host,
    fs: sc.fs,
    config: { ...sc.config, ...config },
    confirm: confirm || (async () => false),
    pause,
    jobId: "job-test",
    ...fakeClock(),
  });
  const entries = logger.entries;
  const find = (step, status, reason) =>
    entries.filter((e) => e.step === step && (!status || e.status === status) && (!reason || e.reason === reason));
  return { ...sc, report, logger, entries, find };
}

test("fluxo completo: plano vira estrutura editável", async () => {
  const r = await run(basePlan());
  assert.equal(r.report.status, "completed", JSON.stringify(r.report.errors));
  const seq = r.host.sequences.find((s) => s.name === "DETTO_MASTER");
  assert.ok(seq, "sequência criada");
  assert.equal(r.report.sequence.created, true);
  // settings do plano aplicados sobre a sequência recém-criada
  assert.equal(seq.fps, 30);
  assert.equal(seq.width, 1920);
  // tracks nomeadas conforme layout DETTO
  assert.deepEqual(seq.videoNames, ["PRESENTER", "B-ROLL", "GRAPHICS", "OVERLAYS", "VFX REFERENCES"]);
  assert.deepEqual(seq.audioNames, ["VOICE", "MUSIC", "SFX", "AMBIENCE"]);
  // clips
  assert.equal(seq.video[0].length, 2);
  assert.equal(seq.video[1].length, 1, "cut_003 em V2 B-ROLL");
  assert.equal(seq.audio[3].length, 1, "cut_003 em A4 AMBIENCE");
  const place = r.host.callsOf("placeClip").map((c) => c[2]);
  assert.deepEqual(place[1], { inPoint: 10, outPoint: 18.5, timelineStart: 4.3, videoTrackIndex: 0, audioTrackIndex: 0 });
  // markers: 1 marker + 1 graphic + 1 vfx
  assert.equal(seq.markers.length, 3);
  assert.equal(seq.markers[0].name, "PLAYER_MENTION");
  assert.equal(seq.markers[0].colorIndex, 1, "red");
  const gfx = seq.markers.find((m) => m.name.startsWith("GFX HEADLINE"));
  assert.equal(gfx.name, "GFX HEADLINE: AS 5 CAMISAS MAIS NOVAS");
  assert.equal(gfx.duration, 2);
  assert.equal(JSON.parse(gfx.comment).detto, "graphic_placeholder");
  assert.ok(seq.markers.find((m) => m.name === "VFX: ZOOM_PUNCH_IN"));
  // mídia importada no bin DETTO_MEDIA, projeto reutilizado e salvo
  assert.deepEqual(r.host.callsOf("ensureBin")[0], ["ensureBin", "DETTO_MEDIA"]);
  assert.equal(r.report.summary.media.imported, 2);
  assert.equal(r.report.project.created, false);
  assert.equal(r.host.saved, 1);
  // sumário
  assert.equal(r.report.summary.cuts.done, 3);
  assert.equal(r.report.summary.markers.done, 1);
  assert.equal(r.report.summary.graphics.done, 1);
  assert.equal(r.report.summary.vfx.done, 1);
});

test("cada operação é registrada no formato de log acordado", async () => {
  const r = await run(basePlan());
  for (const e of r.entries) {
    assert.equal(e.job_id, "job-test");
    assert.equal(typeof e.step, "string");
    assert.equal(typeof e.status, "string");
    assert.ok(!Number.isNaN(Date.parse(e.timestamp)));
    assert.equal(typeof e.duration_ms, "number");
  }
  const steps = new Set(r.entries.map((e) => e.step));
  for (const s of ["VALIDATE_PLAN", "DETECT_ENVIRONMENT", "CHECK_MEDIA", "ENSURE_PROJECT", "BACKUP_PROJECT", "IMPORT_MEDIA", "ENSURE_SEQUENCE", "ENSURE_TRACKS", "PLACE_CLIPS", "CREATE_MARKERS", "GRAPHICS_PLACEHOLDERS", "SAVE_PROJECT"]) {
    assert.ok(steps.has(s), `falta log do passo ${s}`);
  }
  assert.equal(r.logger.toJsonLines().trim().split("\n").length, r.entries.length);
});

test.describe("mídia inexistente", () => {
  test("registra erro, ignora cortes dependentes e continua", async () => {
    const r = await run(basePlan(), { setup: (sc) => sc.fs.files.delete("C:/videos/broll001.mp4") });
    assert.equal(r.report.status, "completed_with_errors");
    assert.equal(r.find("CHECK_MEDIA", "error", "media_not_found").length, 1);
    assert.equal(r.find("CHECK_MEDIA", "error")[0].target, "broll_001");
    assert.equal(r.find("PLACE_CLIPS", "error", "media_unavailable")[0].target, "cut_003");
    assert.equal(r.report.summary.media.missing, 1);
    assert.equal(r.report.summary.cuts.done, 2);
    assert.equal(r.report.summary.cuts.failed, 1);
    // nunca tenta importar arquivo ausente
    assert.ok(!r.host.callsOf("importFiles")[0][1].some((p) => p.includes("broll")));
    // markers continuam sendo criados
    assert.equal(r.report.summary.markers.done, 1);
  });
  test("Premiere falha ao importar um arquivo → erro por item", async () => {
    const r = await run(basePlan(), { hostOpts: { failImport: ["C:/videos/broll001.mp4"] } });
    assert.equal(r.find("IMPORT_MEDIA", "error", "import_failed")[0].target, "broll_001");
    assert.equal(r.report.summary.cuts.done, 2);
  });
});

test.describe("projeto inexistente", () => {
  test("sem projeto aberto e criação desativada → job falha", async () => {
    const r = await run(basePlan(), { hostOpts: { project: null }, config: { allowCreateProject: false } });
    assert.equal(r.report.status, "failed");
    assert.equal(r.report.fatal.code, "PROJECT_NOT_FOUND");
    assert.equal(r.host.callsOf("importFiles").length, 0, "nada é alterado");
  });
  test("sem projeto aberto → cria em <workspace>/projects", async () => {
    const r = await run(basePlan(), { hostOpts: { project: null } });
    assert.equal(r.report.status, "completed");
    assert.deepEqual(r.host.callsOf("createProject")[0], ["createProject", "/engine/projects/detto-video-001.prproj"]);
    assert.equal(r.report.project.created, true);
    assert.equal(r.find("BACKUP_PROJECT", "skipped", "new_project").length, 1);
  });
  test("project.path informado e inexistente → cria nesse caminho", async () => {
    const plan = basePlan();
    plan.project.path = "/clients/acme/novo.prproj";
    const r = await run(plan);
    assert.deepEqual(r.host.callsOf("createProject")[0], ["createProject", "/clients/acme/novo.prproj"]);
  });
  test("project.path informado e existente → abre (não cria nem sobrescreve)", async () => {
    const plan = basePlan();
    plan.project.path = "/clients/acme/main.prproj";
    const r = await run(plan, { files: { "/clients/acme/main.prproj": "<prproj>" } });
    assert.equal(r.host.callsOf("openProject").length, 1);
    assert.equal(r.host.callsOf("createProject").length, 0);
    assert.equal(r.report.project.opened, true);
  });
  test("Premiere desconectado → job falha sem tocar em nada", async () => {
    const r = await run(basePlan(), { hostOpts: { connected: false } });
    assert.equal(r.report.fatal.code, "PREMIERE_DISCONNECTED");
    assert.equal(r.host.calls.length, 0);
  });
});

test.describe("backup", () => {
  test("copia o .prproj antes das alterações", async () => {
    const r = await run(basePlan());
    assert.match(r.report.project.backup, /^\/engine\/backups\/existing_\d{8}-\d{6}\.prproj$/);
    assert.equal(await r.fs.readText(r.report.project.backup), "<prproj>");
    const order = r.entries.map((e) => e.step);
    assert.ok(order.indexOf("BACKUP_PROJECT") < order.indexOf("IMPORT_MEDIA"));
  });
  test("projeto nunca salvo: sem confirmação, cancela sem alterar", async () => {
    const r = await run(basePlan(), { hostOpts: { project: { name: "Untitled", path: "" } } });
    assert.equal(r.report.fatal.code, "CANCELLED_BY_USER");
    assert.equal(r.host.callsOf("importFiles").length, 0);
  });
  test("projeto nunca salvo: com confirmação, segue", async () => {
    const r = await run(basePlan(), { hostOpts: { project: { name: "Untitled", path: "" } }, confirm: async () => true });
    assert.equal(r.report.status, "completed");
    assert.equal(r.find("BACKUP_PROJECT", "warning", "project_not_saved").length, 1);
  });
});

test.describe("sequência inexistente / existente", () => {
  test("sequência inexistente é criada com preset configurado", async () => {
    const r = await run(basePlan(), { config: { sequencePresetPath: "C:/presets/detto.sqpreset" } });
    assert.deepEqual(r.host.callsOf("createSequence")[0], ["createSequence", "DETTO_MASTER", { presetPath: "C:/presets/detto.sqpreset" }]);
  });
  test("sem API de settings → fallback, processo continua", async () => {
    const r = await run(basePlan(), { hostOpts: { supportsSettings: false } });
    assert.equal(r.find("ENSURE_SEQUENCE", "fallback", "sequence_settings_not_available").length, 1);
    assert.equal(r.report.summary.cuts.done, 3);
  });
  test("sequência existente vazia é reutilizada", async () => {
    const r = await run(basePlan(), { setup: (sc) => sc.host.addSequence("DETTO_MASTER") });
    assert.equal(r.host.callsOf("createSequence").length, 0);
    assert.equal(r.report.sequence.reused, true);
  });
  test("sequência existente com clips: sem confirmação cria nova (original preservada)", async () => {
    const r = await run(basePlan(), {
      setup: (sc) => sc.host.addSequence("DETTO_MASTER", { clips: [{ start: 0, end: 50, mediaPath: "C:/old.mp4" }] }),
    });
    const original = r.host.sequences.find((s) => s.name === "DETTO_MASTER");
    assert.equal(original.video[0].length, 1, "original intocada");
    assert.match(r.report.sequence.name, /^DETTO_MASTER_\d{8}-\d{6}$/);
    assert.equal(r.report.sequence.created, true);
  });
  test("sequência existente com clips: com confirmação edita a existente", async () => {
    const r = await run(basePlan(), {
      confirm: async () => true,
      setup: (sc) => sc.host.addSequence("DETTO_MASTER", { clips: [{ start: 100, end: 110, mediaPath: "C:/old.mp4" }] }),
    });
    assert.equal(r.report.sequence.name, "DETTO_MASTER");
    assert.equal(r.host.sequences.length, 1);
  });
});

test.describe("clip fora do intervalo", () => {
  test("duração real da mídia (detectada no Premiere) menor que o corte → erro e continua", async () => {
    const r = await run(basePlan(), { hostOpts: { mediaDurations: { "C:/videos/camera001.mp4": 15, "C:/videos/broll001.mp4": 30 } } });
    const err = r.find("PLACE_CLIPS", "error", "clip_out_of_range");
    assert.equal(err.length, 1);
    assert.equal(err[0].target, "cut_002");
    assert.equal(r.report.summary.cuts.done, 2);
    assert.equal(r.report.status, "completed_with_errors");
  });
  test("plano com corte fora da duração declarada nem começa", async () => {
    const plan = basePlan();
    plan.cuts[0].end = 500;
    const r = await run(plan);
    assert.equal(r.report.fatal.code, "INVALID_PLAN");
    assert.equal(r.host.calls.length, 0);
  });
});

test.describe("FPS incompatível", () => {
  test("plano com project/sequence fps diferentes é rejeitado", async () => {
    const plan = basePlan();
    plan.sequence.fps = 24;
    const r = await run(plan);
    assert.equal(r.report.status, "failed");
    assert.equal(r.report.fatal.code, "INVALID_PLAN");
    assert.ok(r.find("VALIDATE_PLAN", "error")[0].message.includes("FPS incompatível"));
  });
  test("sequência existente em outro fps → fallback registrado, cortes alinhados ao fps do plano", async () => {
    const plan = basePlan();
    plan.cuts[0].end = 4.321; // fora da grade de 30fps
    const r = await run(plan, { setup: (sc) => sc.host.addSequence("DETTO_MASTER", { fps: 25 }) });
    const fb = r.find("ENSURE_SEQUENCE", "fallback", "fps_mismatch");
    assert.equal(fb.length, 1);
    assert.deepEqual(fb[0].details, { sequence_fps: 25, plan_fps: 30 });
    assert.equal(r.host.callsOf("placeClip")[0][2].outPoint, 130 / 30);
  });
});

test.describe("arquivo duplicado", () => {
  test("mídia já presente no projeto não é reimportada", async () => {
    const r = await run(basePlan(), { setup: (sc) => sc.host.addProjectItem("c:\\Videos\\CAMERA001.mp4") });
    assert.deepEqual(r.host.callsOf("importFiles")[0][1], ["C:/videos/broll001.mp4"]);
    assert.equal(r.report.summary.media.reused, 1);
    assert.equal(r.find("IMPORT_MEDIA", "skipped", "already_in_project")[0].target, "camera_001");
  });
  test("mesmo arquivo com dois ids é importado uma vez", async () => {
    const plan = basePlan();
    plan.media.push({ id: "camera_alt", path: "C:/videos/camera001.mp4" });
    plan.cuts.push({ source: "camera_alt", start: 20, end: 22, timeline: 20 });
    const r = await run(plan);
    assert.equal(r.host.callsOf("importFiles")[0][1].length, 2);
    assert.equal(r.host.items.length, 2);
    assert.equal(r.report.summary.cuts.done, 4);
  });
  test("reexecutar o mesmo plano não duplica clips nem markers", async () => {
    const sc = scenario();
    const opts = { host: sc.host, fs: sc.fs, config: sc.config, confirm: async () => true, ...fakeClock() };
    await executePlan(basePlan(), opts);
    const { report } = await executePlan(basePlan(), opts);
    const seq = sc.host.sequences[0];
    assert.equal(sc.host.sequences.length, 1);
    assert.equal(seq.video[0].length, 2);
    assert.equal(seq.markers.length, 3);
    assert.equal(sc.host.items.length, 2, "sem reimportação");
    assert.equal(report.summary.cuts.skipped, 3);
    assert.equal(report.summary.markers.skipped, 1);
    assert.equal(report.status, "completed");
  });
  test("corte idêntico repetido no plano é inserido uma vez", async () => {
    const plan = basePlan();
    plan.cuts.push({ ...plan.cuts[0] });
    const r = await run(plan);
    assert.equal(r.host.callsOf("placeClip").length, 3);
    assert.equal(r.find("PLACE_CLIPS", "skipped", "duplicate_in_plan").length, 1);
  });
});

test.describe("fallbacks", () => {
  test("efeito indisponível não quebra o processo", async () => {
    const plan = basePlan();
    plan.effects.push({ name: "Gaussian Blur" });
    const r = await run(plan);
    const fb = r.find("APPLY_EFFECTS", "fallback", "effect_not_available");
    assert.equal(fb.length, 1);
    assert.equal(fb[0].status, "fallback");
    assert.equal(r.report.summary.effects.done, 1);
    assert.equal(r.report.summary.effects.fallback, 1);
    assert.equal(r.report.status, "completed");
    assert.deepEqual(r.report.fallbacks.find((f) => f.step === "APPLY_EFFECTS").reason, "effect_not_available");
  });
  test("sequência sem tracks suficientes: itens dessas tracks falham, resto continua", async () => {
    const r = await run(basePlan(), { hostOpts: { videoTracks: 1, audioTracks: 2 } });
    assert.deepEqual(r.find("ENSURE_TRACKS", "fallback", "track_creation_not_available")[0].details.missing, ["V2", "V3", "V4", "V5", "A3", "A4"]);
    assert.equal(r.find("PLACE_CLIPS", "error", "track_unavailable")[0].target, "cut_003");
    assert.equal(r.report.summary.cuts.done, 2);
  });
  test("API sem renomear tracks → fallback único", async () => {
    const r = await run(basePlan(), { hostOpts: { supportsRename: false } });
    assert.equal(r.find("ENSURE_TRACKS", "fallback", "track_rename_not_available").length, 1);
  });
  test("cor de marker indisponível → fallback, marker criado", async () => {
    const r = await run(basePlan(), { hostOpts: { supportsMarkerColor: false } });
    assert.ok(r.find("CREATE_MARKERS", "fallback", "marker_color_not_available").length >= 1);
    assert.equal(r.report.summary.markers.done, 1);
  });
});

test("pausa interrompe entre operações e retoma", async () => {
  const pause = new PauseController();
  const sc = scenario();
  let placed = 0;
  const original = sc.host.placeClip.bind(sc.host);
  sc.host.placeClip = async (...args) => {
    await original(...args);
    placed++;
    if (placed === 1) pause.pause();
  };
  const promise = executePlan(basePlan(), { host: sc.host, fs: sc.fs, config: sc.config, pause });
  await new Promise((r) => setTimeout(r, 20));
  assert.equal(placed, 1, "parou após o primeiro clip");
  pause.resume();
  const { report } = await promise;
  assert.equal(placed, 3);
  assert.equal(report.status, "completed");
});
