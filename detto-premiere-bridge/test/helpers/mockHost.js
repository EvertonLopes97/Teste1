"use strict";

const paths = require("../../plugin/src/core/paths");

/**
 * HostAdapter simulado: um "Premiere" em memória com projeto, bins,
 * sequências, tracks, clips e markers. Registra todas as chamadas.
 */
class MockHost {
  /**
   * @param {{
   *   connected?: boolean,
   *   project?: {name: string, path: string} | null,
   *   mediaDurations?: Record<string, number>,
   *   videoTracks?: number,
   *   audioTracks?: number,
   *   supportsRename?: boolean,
   *   supportsSettings?: boolean,
   *   supportsMarkerColor?: boolean,
   *   failImport?: string[],
   * }} [opts]
   */
  constructor(opts = {}) {
    this.connected = opts.connected !== false;
    this.project = opts.project === undefined ? { name: "existing.prproj", path: "/work/existing.prproj" } : opts.project;
    this.mediaDurations = opts.mediaDurations || {};
    this.videoTracks = opts.videoTracks ?? 5;
    this.audioTracks = opts.audioTracks ?? 4;
    this.supportsRename = opts.supportsRename !== false;
    this.supportsSettings = opts.supportsSettings !== false;
    this.supportsMarkerColor = opts.supportsMarkerColor !== false;
    this.failImport = new Set((opts.failImport || []).map(paths.normalizeForCompare));
    /** @type {Array<{path: string, item: any}>} */
    this.items = [];
    /** @type {any[]} */
    this.sequences = [];
    this.activeSequence = null;
    this.bins = new Set();
    /** @type {Array<[string, ...any[]]>} */
    this.calls = [];
    this.saved = 0;
  }

  _call(name, ...args) {
    this.calls.push([name, ...args]);
  }
  callsOf(name) {
    return this.calls.filter((c) => c[0] === name);
  }

  // --- helpers de cenário
  addProjectItem(path) {
    const item = { id: `item:${path}`, path };
    this.items.push({ path, item });
    return item;
  }
  addSequence(name, { fps = 30, width = 1920, height = 1080, clips = [] } = {}) {
    const seq = this._newSeq(name, fps, width, height);
    for (const c of clips) seq.video[c.track || 0].push({ start: c.start, end: c.end, mediaPath: c.mediaPath });
    this.sequences.push(seq);
    return seq;
  }
  _newSeq(name, fps, width, height) {
    return {
      name,
      fps,
      width,
      height,
      video: Array.from({ length: this.videoTracks }, () => []),
      audio: Array.from({ length: this.audioTracks }, () => []),
      videoNames: Array.from({ length: this.videoTracks }, (_, i) => `Video ${i + 1}`),
      audioNames: Array.from({ length: this.audioTracks }, (_, i) => `Audio ${i + 1}`),
      markers: [],
    };
  }

  // --- HostAdapter
  async getEnvironment() {
    return {
      connected: this.connected,
      hostName: "Premiere Pro",
      premiereVersion: "26.0.0",
      uxpVersion: "8.1.0",
      pluginVersion: "0.1.0",
      platform: "win32",
    };
  }
  async getActiveProject() {
    return this.project ? { ...this.project } : null;
  }
  async openProject(path) {
    this._call("openProject", path);
    this.project = { name: paths.basename(path), path };
    return { ...this.project };
  }
  async createProject(path) {
    this._call("createProject", path);
    this.project = { name: paths.basename(path), path };
    return { ...this.project };
  }
  async saveProject() {
    this._call("saveProject");
    this.saved++;
  }
  async listMediaItems() {
    return this.items.slice();
  }
  async ensureBin(name) {
    this._call("ensureBin", name);
    this.bins.add(name);
    return { bin: name };
  }
  async importFiles(filePaths, bin) {
    this._call("importFiles", filePaths, bin);
    const out = [];
    for (const p of filePaths) {
      if (this.failImport.has(paths.normalizeForCompare(p))) continue;
      out.push({ path: p, item: this.addProjectItem(p) });
    }
    return out;
  }
  async findSequence(name) {
    return this.sequences.find((s) => s.name === name) || null;
  }
  async createSequence(name, opts) {
    this._call("createSequence", name, opts);
    const seq = this._newSeq(name, 29.97, 1280, 720); // padrão "errado" para testar applySequenceSettings
    this.sequences.push(seq);
    return seq;
  }
  async getSequenceInfo(seq) {
    const clipCount = [...seq.video, ...seq.audio].reduce((n, t) => n + t.length, 0);
    return {
      name: seq.name,
      fps: seq.fps,
      width: seq.width,
      height: seq.height,
      videoTrackCount: seq.video.length,
      audioTrackCount: seq.audio.length,
      clipCount,
    };
  }
  async applySequenceSettings(seq, s) {
    this._call("applySequenceSettings", seq.name, s);
    if (!this.supportsSettings) return { applied: false, reason: "sequence_settings_not_available" };
    seq.fps = s.fps;
    seq.width = s.width;
    seq.height = s.height;
    return { applied: true };
  }
  async setActiveSequence(seq) {
    this.activeSequence = seq;
  }
  async getActiveSequence() {
    return this.activeSequence ? { name: this.activeSequence.name } : null;
  }
  async renameTrack(seq, kind, index, name) {
    if (!this.supportsRename) return false;
    (kind === "video" ? seq.videoNames : seq.audioNames)[index] = name;
    return true;
  }
  async getMediaDuration(item) {
    const d = this.mediaDurations[item.path];
    return typeof d === "number" ? d : null;
  }
  async listTrackClips(seq, kind, index) {
    return (kind === "video" ? seq.video : seq.audio)[index].slice();
  }
  async placeClip(seq, item, req) {
    this._call("placeClip", item.path, req);
    const length = req.outPoint - req.inPoint;
    seq.video[req.videoTrackIndex].push({ start: req.timelineStart, end: req.timelineStart + length, mediaPath: item.path });
    seq.audio[req.audioTrackIndex].push({ start: req.timelineStart, end: req.timelineStart + length, mediaPath: item.path });
  }
  async listMarkers(seq) {
    return seq.markers.map((m) => ({ name: m.name, start: m.start }));
  }
  async addMarker(seq, m) {
    this._call("addMarker", m);
    seq.markers.push({ ...m, colorIndex: this.supportsMarkerColor ? m.colorIndex : null });
    return { colorApplied: this.supportsMarkerColor && m.colorIndex !== null };
  }
  async applyEffect(_seq, effect) {
    this._call("applyEffect", effect);
    if (effect.name === "Gaussian Blur") return { applied: true };
    return { applied: false, reason: "effect_not_available" };
  }
}

module.exports = { MockHost };
