"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { JobQueue, JobWatcher } = require("../plugin/src/core/jobQueue");
const { BridgeController } = require("../plugin/src/core/controller");
const { STATUS } = require("../plugin/src/core/constants");
const { basePlan, scenario } = require("./helpers/fixtures");

const ROOT = "/engine";

async function queueWith(files) {
  const sc = scenario({}, files);
  const queue = new JobQueue({ fs: sc.fs, root: ROOT });
  await queue.init();
  return { ...sc, queue };
}

test("init cria a estrutura de pastas", async () => {
  const { fs } = await queueWith();
  for (const d of ["pending", "processing", "completed", "failed"]) assert.ok(await fs.exists(`${ROOT}/jobs/${d}`));
  assert.ok(await fs.exists(`${ROOT}/logs`));
});

test("lista apenas .json pendentes em ordem", async () => {
  const { queue } = await queueWith({
    [`${ROOT}/jobs/pending/job-002.json`]: "{}",
    [`${ROOT}/jobs/pending/job-001.json`]: "{}",
    [`${ROOT}/jobs/pending/notes.txt`]: "x",
  });
  assert.deepEqual(await queue.listPending(), ["job-001.json", "job-002.json"]);
});

test.describe("formatos de job", () => {
  test("arquivo é o próprio EDIT_PLAN (job_id do plano)", async () => {
    const { queue } = await queueWith({ [`${ROOT}/jobs/pending/job-001.json`]: JSON.stringify(basePlan()) });
    const job = await queue.load("job-001.json");
    assert.equal(job.jobId, "job-001");
    assert.equal(job.plan.sequence.name, "DETTO_MASTER");
  });
  test("envelope com plan embutido", async () => {
    const { queue } = await queueWith({
      [`${ROOT}/jobs/pending/a.json`]: JSON.stringify({ job_id: "job-777", plan: basePlan() }),
    });
    const job = await queue.load("a.json");
    assert.equal(job.jobId, "job-777");
    assert.equal(job.plan.project.name, "detto-video-001");
  });
  test("envelope com edit_plan_path", async () => {
    const { queue } = await queueWith({
      "/plans/EDIT_PLAN.json": JSON.stringify(basePlan()),
      [`${ROOT}/jobs/pending/job-003.json`]: JSON.stringify({ job_id: "job-003", edit_plan_path: "/plans/EDIT_PLAN.json" }),
    });
    const job = await queue.load("job-003.json");
    assert.equal(job.planSource, "/plans/EDIT_PLAN.json");
    assert.equal(job.plan.cuts.length, 3);
  });
  test("edit_plan_path inexistente → PLAN_NOT_FOUND", async () => {
    const { queue } = await queueWith({
      [`${ROOT}/jobs/pending/job-004.json`]: JSON.stringify({ job_id: "job-004", edit_plan_path: "/nope.json" }),
    });
    await assert.rejects(queue.load("job-004.json"), { code: "PLAN_NOT_FOUND" });
  });
  test("JSON inválido → INVALID_JSON", async () => {
    const { queue } = await queueWith({ [`${ROOT}/jobs/pending/bad.json`]: "{oops" });
    await assert.rejects(queue.load("bad.json"), { code: "INVALID_JSON" });
  });
});

test("transições pending → processing → completed com relatório e log", async () => {
  const { queue, fs } = await queueWith({ [`${ROOT}/jobs/pending/job-001.json`]: JSON.stringify(basePlan()) });
  const job = await queue.load("job-001.json");
  await queue.start(job);
  assert.equal(job.state, "processing");
  assert.ok(await fs.exists(`${ROOT}/jobs/processing/job-001.json`));
  assert.ok(!(await fs.exists(`${ROOT}/jobs/pending/job-001.json`)));
  await queue.complete(job, { status: "completed" }, '{"step":"X"}\n');
  assert.equal(job.state, "completed");
  assert.ok(await fs.exists(`${ROOT}/jobs/completed/job-001.json`));
  assert.deepEqual(JSON.parse(await fs.readText(`${ROOT}/jobs/completed/job-001.report.json`)), { status: "completed" });
  assert.ok(await fs.exists(`${ROOT}/jobs/completed/job-001.log.jsonl`));
  assert.ok(await fs.exists(`${ROOT}/logs/job-001.log.jsonl`));
});

test("transição inválida é recusada", async () => {
  const { queue } = await queueWith({ [`${ROOT}/jobs/pending/job-001.json`]: "{}" });
  const job = await queue.load("job-001.json");
  await assert.rejects(queue.complete(job, {}, ""), { code: "INVALID_JOB_TRANSITION" });
});

test("job repetido não sobrescreve execução anterior em completed/", async () => {
  const { queue, fs } = await queueWith({
    [`${ROOT}/jobs/pending/job-001.json`]: "{}",
    [`${ROOT}/jobs/completed/job-001.json`]: "old",
  });
  const job = await queue.load("job-001.json");
  await queue.start(job);
  await queue.complete(job, {}, "");
  assert.equal(await fs.readText(`${ROOT}/jobs/completed/job-001.json`), "old");
  assert.match(job.fileName, /^job-001\.\d{8}-\d{6}\.json$/);
});

test("reject move arquivo inválido direto para failed/", async () => {
  const { queue, fs } = await queueWith({ [`${ROOT}/jobs/pending/bad.json`]: "{oops" });
  await queue.reject("bad.json", { code: "INVALID_JSON", message: "x" });
  assert.ok(await fs.exists(`${ROOT}/jobs/failed/bad.json`));
  assert.equal(JSON.parse(await fs.readText(`${ROOT}/jobs/failed/bad.report.json`)).fatal.code, "INVALID_JSON");
});

test("watcher entrega cada job uma vez e respeita isBusy", async () => {
  const { queue } = await queueWith({ [`${ROOT}/jobs/pending/job-001.json`]: "{}" });
  const delivered = [];
  let busy = true;
  const w = new JobWatcher({ queue, intervalMs: 10, isBusy: () => busy, onJob: async (f) => delivered.push(f) });
  assert.equal(await w.tick(), null);
  busy = false;
  assert.equal(await w.tick(), "job-001.json");
  assert.equal(await w.tick(), null, "não reentrega");
  assert.deepEqual(delivered, ["job-001.json"]);
});

test.describe("controller + fila", () => {
  async function controllerWith(files, config = {}) {
    const sc = scenario({}, files);
    const c = new BridgeController({ host: sc.host, fs: sc.fs, config: { workspaceRoot: ROOT, watchJobs: false, ...config } });
    await c.connectQueue();
    return { ...sc, c };
  }

  test("job válido: pending → processing → completed", async () => {
    const { c, fs, host } = await controllerWith({ [`${ROOT}/jobs/pending/job-001.json`]: JSON.stringify(basePlan()) });
    await c.watcher.tick();
    assert.equal(c.state.jobId, "job-001");
    assert.equal(c.state.preview.counts.cuts, 3);
    assert.equal(c.state.status, STATUS.IDLE);
    const report = await c.execute();
    assert.equal(report.status, "completed");
    assert.equal(c.state.status, STATUS.COMPLETE);
    assert.ok(await fs.exists(`${ROOT}/jobs/completed/job-001.json`));
    const saved = JSON.parse(await fs.readText(`${ROOT}/jobs/completed/job-001.report.json`));
    assert.equal(saved.job_id, "job-001");
    const log = (await fs.readText(`${ROOT}/logs/job-001.log.jsonl`)).trim().split("\n").map((l) => JSON.parse(l));
    assert.ok(log.every((e) => e.job_id === "job-001" && e.timestamp && typeof e.duration_ms === "number"));
    assert.equal(host.sequences.length, 1);
  });

  test("job com falha fatal: processing → failed", async () => {
    const plan = basePlan();
    plan.sequence.fps = 25; // FPS incompatível
    const { c, fs } = await controllerWith({ [`${ROOT}/jobs/pending/job-009.json`]: JSON.stringify(plan) });
    await c.loadJob("job-009.json");
    assert.equal(c.state.status, STATUS.ERROR);
    const report = await c.execute();
    assert.equal(report.status, "failed");
    assert.ok(await fs.exists(`${ROOT}/jobs/failed/job-009.json`));
    assert.ok(await fs.exists(`${ROOT}/jobs/failed/job-009.report.json`));
  });

  test("JSON inválido na fila vai para failed/ sem travar a fila", async () => {
    const { c, fs } = await controllerWith({
      [`${ROOT}/jobs/pending/job-001.json`]: "{oops",
      [`${ROOT}/jobs/pending/job-002.json`]: JSON.stringify(basePlan()),
    });
    await c.watcher.tick();
    assert.ok(await fs.exists(`${ROOT}/jobs/failed/job-001.json`));
    await c.watcher.tick();
    assert.equal(c.state.jobId, "job-002");
  });

  test("autoExecuteJobs executa assim que o job chega", async () => {
    const { c, fs } = await controllerWith({ [`${ROOT}/jobs/pending/job-001.json`]: JSON.stringify(basePlan()) }, { autoExecuteJobs: true });
    await c.watcher.tick();
    assert.ok(await fs.exists(`${ROOT}/jobs/completed/job-001.json`));
  });

  test("plano manual com JSON inválido → status ERROR", async () => {
    const { c } = await controllerWith({});
    assert.equal(c.loadPlanText("{x", "C:/plan.json"), false);
    assert.equal(c.state.status, STATUS.ERROR);
    assert.equal(c.state.planFile, "C:/plan.json");
    assert.equal(await c.execute(), null);
  });
});
