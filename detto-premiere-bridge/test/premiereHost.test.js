"use strict";

/**
 * Testa o adaptador PremiereHost contra um módulo `premierepro` falso que
 * reproduz as assinaturas oficiais (@adobe/premierepro): ações criadas por
 * create*Action só têm efeito dentro de lockedAccess + executeTransaction.
 */

const test = require("node:test");
const assert = require("node:assert/strict");
const { PremiereHost } = require("../plugin/src/host/premiereHost");

const TYPE_CLIP = 1;
const TYPE_BIN = 2;
const TYPE_FILE = 4;

function tick(seconds) {
  return { seconds, ticks: String(Math.round(seconds * 254016000000)) };
}

function fakePpro() {
  const log = [];
  let locked = false;
  const action = (label, run) => ({ label, run });

  const clip = (name, path, duration) => {
    const c = {
      name,
      type: TYPE_CLIP,
      path,
      inPoint: tick(0),
      outPoint: tick(duration),
      getMediaFilePath: async () => path,
      isSequence: async () => false,
      getInPoint: async () => c.inPoint,
      getOutPoint: async () => c.outPoint,
      getMedia: async () => ({ duration: Promise.resolve(tick(duration)) }),
      createSetInOutPointsAction: (i, o) => action(`inout ${i.seconds}-${o.seconds}`, () => { c.inPoint = i; c.outPoint = o; }),
      createClearInOutPointsAction: () => action("clear inout", () => { c.inPoint = tick(0); c.outPoint = tick(duration); }),
    };
    return c;
  };
  const bin = (name, items) => ({
    name,
    type: TYPE_BIN,
    items,
    getItems: async () => items,
    createBinAction: (n) => action(`bin ${n}`, () => items.push(bin(n, []))),
  });

  const track = (name) => {
    const t = {
      name,
      items: [],
      createSetNameAction: (n) => action(`name ${n}`, () => { t.name = n; }),
      getTrackItems: () => t.items,
    };
    return t;
  };
  const markersList = [];
  const marker = (name, start, comments) => {
    const m = {
      name, start, comments, colorIndex: 0,
      getName: () => name,
      getStart: () => tick(start),
      createSetColorByIndexAction: (i) => action(`color ${i}`, () => { m.colorIndex = i; }),
    };
    return m;
  };
  let frameRate = 25;
  const rect = { width: 1280, height: 720 };
  const settings = {
    getVideoFrameRate: () => ({ value: frameRate }),
    setVideoFrameRate: (fr) => { settings._pendingRate = fr.value; return true; },
    getVideoFrameRect: async () => ({ ...rect }),
    setVideoFrameRect: async (r) => { settings._pendingRect = r; return true; },
  };
  const seq = {
    name: "DETTO_MASTER",
    v: [track("Video 1"), track("Video 2")],
    a: [track("Audio 1")],
    getSettings: async () => settings,
    getVideoTrackCount: async () => seq.v.length,
    getAudioTrackCount: async () => seq.a.length,
    getVideoTrack: async (i) => seq.v[i],
    getAudioTrack: async (i) => seq.a[i],
    createSetSettingsAction: (s) => action("settings", () => {
      frameRate = s._pendingRate;
      Object.assign(rect, s._pendingRect);
    }),
  };

  const cam = clip("camera001.mp4", "C:\\videos\\camera001.mp4", 120);
  const nested = clip("broll.mp4", "C:\\videos\\broll.mp4", 30);
  const root = bin("root", [cam, bin("Sub", [nested]), { name: "Bars", type: TYPE_FILE, getMediaFilePath: async () => "" }]);

  const project = {
    name: "existing.prproj",
    path: "C:\\work\\existing.prproj",
    getRootItem: async () => root,
    getSequences: async () => [seq],
    getActiveSequence: async () => seq,
    importFiles: async (paths, suppress, target) => {
      log.push(["importFiles", paths, suppress, target && target.name]);
      for (const p of paths) target.items.push(clip(p.split("\\").pop(), p, 10));
      return true;
    },
    save: async () => true,
    lockedAccess: (cb) => {
      locked = true;
      try { cb(); } finally { locked = false; }
    },
    executeTransaction: (cb, label) => {
      assert.ok(locked, "executeTransaction fora de lockedAccess");
      const actions = [];
      cb({ addAction: (a) => actions.push(a) });
      log.push(["tx", label, actions.map((a) => a.label)]);
      actions.forEach((a) => a.run());
      return true;
    },
  };

  const ppro = {
    Application: { version: Promise.resolve("26.0.1") },
    Project: { getActiveProject: async () => project },
    ProjectItem: { TYPE_BIN, TYPE_CLIP, TYPE_FILE },
    FolderItem: { cast: (i) => i },
    ClipProjectItem: { cast: (i) => (i && i.type === TYPE_CLIP ? i : null) },
    TickTime: { createWithSeconds: tick, TIME_ZERO: tick(0) },
    FrameRate: { createWithValue: (value) => ({ value }) },
    Constants: { TrackItemType: { CLIP: 1 }, MediaType: { VIDEO: 2 } },
    Marker: { MARKER_TYPE_COMMENT: "Comment" },
    Markers: {
      getMarkers: async () => ({
        getMarkers: () => markersList,
        createAddMarkerAction: (name, type, start, duration, comments) =>
          action(`marker ${name}`, () => markersList.push(marker(name, start.seconds, comments))),
      }),
    },
    SequenceEditor: {
      getEditor: () => ({
        createOverwriteItemAction: (item, at, v, a) =>
          action(`overwrite ${item.name}@${at.seconds} v${v} a${a}`, () => {
            const len = item.outPoint.seconds - item.inPoint.seconds;
            const ti = {
              getStartTime: async () => at,
              getEndTime: async () => tick(at.seconds + len),
              getProjectItem: async () => item,
            };
            seq.v[v].items.push(ti);
          }),
      }),
    },
  };
  const uxp = { host: { name: "Premiere Pro", version: "26.0.1" }, versions: { uxp: "8.4.0", plugin: "0.1.0" } };
  const os = { platform: () => "win32" };
  return { ppro, uxp, os, log, project, seq, cam, root, markersList, settings };
}

test("getEnvironment detecta versões do Premiere e do UXP", async () => {
  const f = fakePpro();
  const env = await new PremiereHost(f).getEnvironment();
  assert.deepEqual(env, {
    connected: true,
    hostName: "Premiere Pro",
    premiereVersion: "26.0.1",
    uxpVersion: "8.4.0",
    pluginVersion: "0.1.0",
    platform: "win32",
  });
});

test("listMediaItems percorre bins recursivamente e ignora itens sem mídia", async () => {
  const f = fakePpro();
  const items = await new PremiereHost(f).listMediaItems();
  assert.deepEqual(items.map((i) => i.path), ["C:\\videos\\camera001.mp4", "C:\\videos\\broll.mp4"]);
});

test("ensureBin cria via transação e importFiles usa caminhos nativos", async () => {
  const f = fakePpro();
  const host = new PremiereHost(f);
  const bin = await host.ensureBin("DETTO_MEDIA");
  assert.equal(bin.name, "DETTO_MEDIA");
  assert.deepEqual(f.log[0], ["tx", "DETTO: criar bin DETTO_MEDIA", ["bin DETTO_MEDIA"]]);
  assert.equal(await host.ensureBin("DETTO_MEDIA"), bin, "reutiliza bin existente");
  const imported = await host.importFiles(["C:/new/a.mp4"], bin);
  assert.deepEqual(f.log.at(-1), ["importFiles", ["C:\\new\\a.mp4"], true, "DETTO_MEDIA"]);
  assert.equal(imported.length, 1);
});

test("placeClip: in/out → overwrite → restaura in/out, tudo em transações", async () => {
  const f = fakePpro();
  const host = new PremiereHost(f);
  await host.placeClip(f.seq, f.cam, { inPoint: 10, outPoint: 18.5, timelineStart: 4.3, videoTrackIndex: 1, audioTrackIndex: 0 });
  const txs = f.log.filter((l) => l[0] === "tx").map((l) => l[2][0]);
  assert.deepEqual(txs, ["inout 10-18.5", "overwrite camera001.mp4@4.3 v1 a0", "inout 0-120"]);
  assert.equal(f.cam.inPoint.seconds, 0, "clip de origem restaurado");
  const clips = await host.listTrackClips(f.seq, "video", 1);
  assert.deepEqual(clips, [{ start: 4.3, end: 12.8, mediaPath: "C:\\videos\\camera001.mp4" }]);
});

test("addMarker cria marker de comentário e aplica cor", async () => {
  const f = fakePpro();
  const host = new PremiereHost(f);
  const r = await host.addMarker(f.seq, { name: "PLAYER_MENTION", start: 12.4, duration: 0, comment: "c", colorIndex: 1 });
  assert.deepEqual(r, { colorApplied: true });
  assert.equal(f.markersList[0].colorIndex, 1);
  assert.deepEqual(await host.listMarkers(f.seq), [{ name: "PLAYER_MENTION", start: 12.4 }]);
});

test("sequência: info, settings e nome de tracks", async () => {
  const f = fakePpro();
  const host = new PremiereHost(f);
  assert.deepEqual(await host.getSequenceInfo(f.seq), {
    name: "DETTO_MASTER", fps: 25, width: 1280, height: 720, videoTrackCount: 2, audioTrackCount: 1, clipCount: 0,
  });
  assert.deepEqual(await host.applySequenceSettings(f.seq, { fps: 30, width: 1920, height: 1080 }), { applied: true });
  const info = await host.getSequenceInfo(f.seq);
  assert.deepEqual([info.fps, info.width, info.height], [30, 1920, 1080]);
  assert.equal(await host.renameTrack(f.seq, "video", 0, "PRESENTER"), true);
  assert.equal(f.seq.v[0].name, "PRESENTER");
});

test("getMediaDuration lê Media.duration", async () => {
  const f = fakePpro();
  assert.equal(await new PremiereHost(f).getMediaDuration(f.cam), 120);
});

test("efeitos ainda não suportados retornam fallback", async () => {
  const r = await new PremiereHost(fakePpro()).applyEffect(null, { name: "Lumetri Color" });
  assert.equal(r.applied, false);
  assert.equal(r.reason, "effect_not_available");
});

test("sem projeto ativo → PROJECT_NOT_FOUND", async () => {
  const f = fakePpro();
  f.ppro.Project.getActiveProject = async () => null;
  const host = new PremiereHost(f);
  assert.equal(await host.getActiveProject(), null);
  await assert.rejects(host.listMediaItems(), { code: "PROJECT_NOT_FOUND" });
});
