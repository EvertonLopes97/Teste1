"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const os = require("os");
const nodePath = require("path");
const nodeFs = require("fs");
const { UxpFileSystem, call } = require("../plugin/src/host/uxpFs");
const { JobQueue } = require("../plugin/src/core/jobQueue");

// O fs do UXP segue a API callback do Node; usamos o fs real como stand-in.
const tmp = () => nodeFs.mkdtempSync(nodePath.join(os.tmpdir(), "detto-")).replace(/\\/g, "/");

test("call() aceita callback e promise sem resolver duas vezes", async () => {
  assert.equal(await call((a, cb) => cb(null, a + 1), [1]), 2);
  assert.equal(await call((a) => Promise.resolve(a * 2), [4]), 8);
  await assert.rejects(call((cb) => cb(new Error("x")), []), /x/);
});

test("UxpFileSystem: mkdirp, write/read, readdir, move, copy sem sobrescrever", async () => {
  const fs = new UxpFileSystem({ fs: nodeFs, platform: process.platform });
  const root = tmp();
  await fs.mkdirp(`${root}/a/b/c`);
  assert.equal(await fs.exists(`${root}/a/b/c`), true);
  await fs.writeText(`${root}/a/x.json`, "{\"ok\":true}");
  assert.equal(await fs.readText(`${root}/a/x.json`), "{\"ok\":true}");
  assert.deepEqual((await fs.readdir(`${root}/a`)).sort(), ["b", "x.json"]);
  await fs.copyFile(`${root}/a/x.json`, `${root}/a/y.json`);
  await assert.rejects(fs.copyFile(`${root}/a/x.json`, `${root}/a/y.json`), /já existe/);
  await fs.move(`${root}/a/x.json`, `${root}/a/b/x.json`);
  assert.equal(await fs.exists(`${root}/a/x.json`), false);
  assert.equal(await fs.exists(`${root}/a/b/x.json`), true);
});

test("fila de jobs sobre disco real", async () => {
  const fs = new UxpFileSystem({ fs: nodeFs, platform: process.platform });
  const root = tmp();
  const q = new JobQueue({ fs, root });
  await q.init();
  nodeFs.writeFileSync(`${root}/jobs/pending/job-001.json`, JSON.stringify({ job_id: "job-001", plan: { project: {} } }));
  const job = await q.load("job-001.json");
  await q.start(job);
  await q.fail(job, { status: "failed" }, "{}\n");
  assert.ok(nodeFs.existsSync(`${root}/jobs/failed/job-001.json`));
  assert.ok(nodeFs.existsSync(`${root}/jobs/failed/job-001.report.json`));
  assert.ok(nodeFs.existsSync(`${root}/logs/job-001.log.jsonl`));
});
