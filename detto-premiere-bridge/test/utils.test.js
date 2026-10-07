"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const time = require("../plugin/src/core/time");
const paths = require("../plugin/src/core/paths");
const { resolveTrack, tracksForCut } = require("../plugin/src/core/tracks");
const { resolveConfig } = require("../plugin/src/core/config");
const { Logger } = require("../plugin/src/core/logger");

test("time", () => {
  assert.equal(time.snapToFrame(4.321, 30), 130 / 30);
  assert.equal(time.isFrameAligned(4.3, 30), true);
  assert.equal(time.isFrameAligned(4.321, 30), false);
  assert.equal(time.fpsEquals(29.97, 30000 / 1001), true);
  assert.equal(time.fpsEquals(25, 24), false);
  assert.equal(time.toTimecode(3661.5, 30), "01:01:01:15");
});

test("paths", () => {
  assert.equal(paths.normalizeForCompare("C:\\Videos\\A.MP4"), "c:/videos/a.mp4");
  assert.equal(paths.join("C:/engine/", "/jobs", "pending"), "C:/engine/jobs/pending");
  assert.equal(paths.basename("C:\\x\\job-001.json"), "job-001.json");
  assert.equal(paths.dirname("/a/b/c.prproj"), "/a/b");
  assert.equal(paths.stripExtension("/a/b/c.prproj"), "c");
  assert.equal(paths.toNative("C:/a/b.mp4", "win32"), "C:\\a\\b.mp4");
  assert.equal(paths.toNative("/Users/a/b.mp4", "darwin"), "/Users/a/b.mp4");
  assert.equal(paths.fileTimestamp(new Date(2026, 0, 2, 3, 4, 5)), "20260102-030405");
});

test("tracks: layout DETTO", () => {
  assert.equal(resolveTrack("video", "B-ROLL").index, 1);
  assert.equal(resolveTrack("video", "b_roll").id, "V2");
  assert.equal(resolveTrack("video", 5).role, "VFX REFERENCES");
  assert.equal(resolveTrack("audio", "ambience").index, 3);
  assert.equal(resolveTrack("video", "V6"), null);
  const t = tracksForCut({});
  assert.deepEqual([t.video.id, t.audio.id], ["V1", "A1"]);
});

test("config deriva pastas do workspace", () => {
  const c = resolveConfig({ workspaceRoot: "C:/detto-video-engine" });
  assert.equal(c.projectsDir, "C:/detto-video-engine/projects");
  assert.equal(c.backupDir, "C:/detto-video-engine/backups");
  assert.equal(c.mediaBinName, "DETTO_MEDIA");
});

test("logger.time registra sucesso, resultado de fallback e exceções", async () => {
  let t = 0;
  const log = new Logger({ jobId: "job-001", now: () => (t += 100) });
  await log.time("A", async () => 1);
  await log.time("B", async () => ({ status: "fallback", reason: "effect_not_available" }));
  await assert.rejects(log.time("C", async () => { throw Object.assign(new Error("boom"), { code: "X" }); }));
  assert.deepEqual(
    log.entries.map((e) => [e.step, e.status, e.reason, e.duration_ms]),
    [["A", "success", undefined, 100], ["B", "fallback", "effect_not_available", 100], ["C", "error", "X", 100]]
  );
  assert.equal(log.count("error"), 1);
});
