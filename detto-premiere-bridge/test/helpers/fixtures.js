"use strict";

const fsNode = require("fs");
const pathNode = require("path");
const { MemoryFs } = require("./memoryFs");
const { MockHost } = require("./mockHost");

const EXAMPLE = pathNode.join(__dirname, "..", "..", "examples", "EDIT_PLAN.example.json");

/** Cópia profunda do plano de exemplo. */
function basePlan() {
  return JSON.parse(fsNode.readFileSync(EXAMPLE, "utf-8"));
}

/** Cenário padrão: mídias existem no disco, projeto salvo aberto no Premiere. */
function scenario(hostOpts = {}, extraFiles = {}) {
  const fs = new MemoryFs({
    "C:/videos/camera001.mp4": "video",
    "C:/videos/broll001.mp4": "video",
    "/work/existing.prproj": "<prproj>",
    ...extraFiles,
  });
  const host = new MockHost({ mediaDurations: { "C:/videos/camera001.mp4": 120, "C:/videos/broll001.mp4": 30 }, ...hostOpts });
  const config = { workspaceRoot: "/engine", saveAfterExecute: true };
  return { fs, host, config };
}

/** Relógio determinístico para testes. */
function fakeClock(start = Date.UTC(2026, 9, 7, 12, 0, 0)) {
  let t = start;
  return {
    now: () => (t += 5),
    clock: () => new Date((t += 5)),
  };
}

module.exports = { basePlan, scenario, fakeClock, EXAMPLE };
