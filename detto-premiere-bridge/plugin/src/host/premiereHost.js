// @ts-check
"use strict";

/**
 * Adaptador Premiere Pro (UXP) — implementa `HostAdapter` (ver core/types.js)
 * usando somente a API oficial `require("premierepro")`.
 *
 * Toda edição passa por `project.lockedAccess` + `project.executeTransaction`,
 * então cada operação entra no histórico de Undo do Premiere.
 * Recursos ausentes na versão instalada geram `ApiNotAvailableError`, que o
 * executor converte em `{status: "fallback"}` sem derrubar o job.
 */

const { ApiNotAvailableError, BridgeError } = require("../core/errors");
const paths = require("../core/paths");

/** @returns {any} */
function loadPpro() {
  return require("premierepro");
}

class PremiereHost {
  /**
   * @param {{ppro?: any, uxp?: any, os?: any}} [deps] injeção para testes
   */
  constructor(deps = {}) {
    this._deps = deps;
    /** @type {any} */
    this._ppro = deps.ppro || null;
  }

  /** @returns {any} */
  get ppro() {
    if (!this._ppro) this._ppro = loadPpro();
    return this._ppro;
  }

  get platform() {
    try {
      const os = this._deps.os || require("os");
      return String(os.platform());
    } catch (_) {
      return "";
    }
  }

  // ------------------------------------------------------------ ambiente

  async getEnvironment() {
    let uxp = this._deps.uxp;
    try {
      uxp = uxp || require("uxp");
    } catch (_) {
      uxp = null;
    }
    let connected = false;
    let premiereVersion = "";
    try {
      const ppro = this.ppro;
      connected = !!(ppro && ppro.Project);
      if (ppro.Application && ppro.Application.version) premiereVersion = String(await ppro.Application.version);
    } catch (_) {
      connected = false;
    }
    const host = uxp && uxp.host;
    if (!premiereVersion && host) premiereVersion = String(host.version || "");
    if (host && host.buildNumber) premiereVersion += ` (build ${host.buildNumber})`;
    return {
      connected,
      hostName: (host && host.name) || "Premiere Pro",
      premiereVersion,
      uxpVersion: (uxp && uxp.versions && uxp.versions.uxp) || "",
      pluginVersion: (uxp && uxp.versions && uxp.versions.plugin) || "",
      platform: this.platform,
    };
  }

  // ------------------------------------------------------------ projeto

  /** @returns {Promise<any|null>} */
  async _project() {
    try {
      const p = await this.ppro.Project.getActiveProject();
      return p || null;
    } catch (_) {
      return null;
    }
  }

  /** @returns {Promise<any>} */
  async _requireProject() {
    const p = await this._project();
    if (!p) throw new BridgeError("PROJECT_NOT_FOUND", "Nenhum projeto ativo no Premiere.");
    return p;
  }

  /** @param {any} p */
  _info(p) {
    return { name: String(p.name || ""), path: String(p.path || "") };
  }

  async getActiveProject() {
    const p = await this._project();
    return p ? this._info(p) : null;
  }

  /** @param {string} path */
  async openProject(path) {
    const p = await this.ppro.Project.open(this._native(path));
    if (!p) throw new BridgeError("PROJECT_OPEN_FAILED", `Não foi possível abrir ${path}`);
    return this._info(p);
  }

  /** @param {string} path */
  async createProject(path) {
    const p = await this.ppro.Project.createProject(this._native(path));
    if (!p) throw new BridgeError("PROJECT_CREATE_FAILED", `Não foi possível criar ${path}`);
    return this._info(p);
  }

  async saveProject() {
    const p = await this._requireProject();
    const ok = await p.save();
    if (ok === false) throw new BridgeError("SAVE_FAILED", "Premiere recusou salvar o projeto.");
  }

  /**
   * Executa ações dentro de uma transação (entra no Undo do Premiere).
   * @param {any} project
   * @param {string} label
   * @param {() => any[]} buildActions
   */
  _transact(project, label, buildActions) {
    let ok = false;
    /** @type {any} */
    let error = null;
    project.lockedAccess(() => {
      try {
        ok = project.executeTransaction((/** @type {any} */ compound) => {
          for (const action of buildActions()) compound.addAction(action);
        }, `DETTO: ${label}`);
      } catch (e) {
        error = e;
      }
    });
    if (error) throw error;
    if (ok === false) throw new BridgeError("TRANSACTION_FAILED", `Premiere rejeitou a operação: ${label}`);
  }

  // ------------------------------------------------------------ mídia / bins

  /**
   * Percorre o projeto recursivamente e devolve todos os clips com caminho de mídia.
   */
  async listMediaItems() {
    const project = await this._requireProject();
    const root = await project.getRootItem();
    /** @type {Array<{path: string, item: any}>} */
    const out = [];
    await this._walk(root, out);
    return out;
  }

  /**
   * @param {any} folder
   * @param {Array<{path: string, item: any}>} out
   */
  async _walk(folder, out) {
    const ppro = this.ppro;
    const items = (await folder.getItems()) || [];
    for (const item of items) {
      if (item.type === ppro.ProjectItem.TYPE_BIN) {
        const sub = ppro.FolderItem.cast(item);
        if (sub) await this._walk(sub, out);
        continue;
      }
      if (item.type !== ppro.ProjectItem.TYPE_CLIP && item.type !== ppro.ProjectItem.TYPE_FILE) continue;
      try {
        const clip = ppro.ClipProjectItem.cast(item);
        if (!clip) continue;
        if (await clip.isSequence()) continue;
        const mediaPath = await clip.getMediaFilePath();
        if (mediaPath) out.push({ path: mediaPath, item });
      } catch (_) {
        /* itens sem mídia (cores, títulos) são ignorados */
      }
    }
  }

  /** @param {string} name */
  async ensureBin(name) {
    const ppro = this.ppro;
    const project = await this._requireProject();
    const root = await project.getRootItem();
    const find = async () => {
      const items = (await root.getItems()) || [];
      const bin = items.find((/** @type {any} */ i) => i.type === ppro.ProjectItem.TYPE_BIN && i.name === name);
      return bin || null;
    };
    let bin = await find();
    if (!bin) {
      this._transact(project, `criar bin ${name}`, () => [root.createBinAction(name, false)]);
      bin = await find();
    }
    return bin;
  }

  /**
   * @param {string[]} filePaths
   * @param {any} bin ProjectItem do bin de destino (null = raiz)
   */
  async importFiles(filePaths, bin) {
    const ppro = this.ppro;
    const project = await this._requireProject();
    const native = filePaths.map((p) => this._native(p));
    const ok = await project.importFiles(native, true, bin || null, false);
    if (!ok) throw new BridgeError("IMPORT_FAILED", "Premiere não concluiu a importação.");

    const wanted = new Set(filePaths.map((p) => paths.normalizeForCompare(p)));
    /** @type {Array<{path: string, item: any}>} */
    const found = [];
    const scope = bin ? ppro.FolderItem.cast(bin) : await project.getRootItem();
    await this._walk(scope, found);
    return found.filter((f) => wanted.has(paths.normalizeForCompare(f.path)));
  }

  /** @param {any} item */
  async getMediaDuration(item) {
    const clip = this.ppro.ClipProjectItem.cast(item);
    const media = await clip.getMedia();
    if (!media) return null;
    const duration = media.duration ? await media.duration : media.getDuration();
    const seconds = duration && typeof duration.seconds === "number" ? duration.seconds : null;
    return seconds && seconds > 0 ? seconds : null;
  }

  // ------------------------------------------------------------ sequências

  /** @param {string} name */
  async findSequence(name) {
    const project = await this._requireProject();
    const seqs = (await project.getSequences()) || [];
    return seqs.find((/** @type {any} */ s) => s.name === name) || null;
  }

  /**
   * @param {string} name
   * @param {{presetPath?: string}} opts
   */
  async createSequence(name, opts) {
    const project = await this._requireProject();
    const seq = opts.presetPath
      ? await project.createSequence(name, this._native(opts.presetPath))
      : await project.createSequence(name);
    if (!seq) throw new BridgeError("SEQUENCE_CREATE_FAILED", `Não foi possível criar a sequência ${name}`);
    return seq;
  }

  /** @param {any} seq */
  async getSequenceInfo(seq) {
    const ppro = this.ppro;
    let fps = null;
    let width = null;
    let height = null;
    try {
      const settings = await seq.getSettings();
      fps = settings.getVideoFrameRate().value;
      const rect = await settings.getVideoFrameRect();
      width = Math.round(rect.width);
      height = Math.round(rect.height);
    } catch (_) {
      try {
        const size = await seq.getFrameSize();
        width = Math.round(size.width);
        height = Math.round(size.height);
      } catch (_e) {
        /* sem informação */
      }
    }
    const videoTrackCount = await seq.getVideoTrackCount();
    const audioTrackCount = await seq.getAudioTrackCount();
    let clipCount = 0;
    const CLIP = ppro.Constants.TrackItemType.CLIP;
    for (let i = 0; i < videoTrackCount; i++) clipCount += ((await seq.getVideoTrack(i)).getTrackItems(CLIP, false) || []).length;
    for (let i = 0; i < audioTrackCount; i++) clipCount += ((await seq.getAudioTrack(i)).getTrackItems(CLIP, false) || []).length;
    return { name: String(seq.name), fps, width, height, videoTrackCount, audioTrackCount, clipCount };
  }

  /**
   * @param {any} seq
   * @param {{fps: number, width: number, height: number}} s
   */
  async applySequenceSettings(seq, s) {
    const ppro = this.ppro;
    try {
      const project = await this._requireProject();
      const settings = await seq.getSettings();
      const rateOk = settings.setVideoFrameRate(ppro.FrameRate.createWithValue(s.fps));
      const rect = settings.getVideoFrameRect ? await settings.getVideoFrameRect() : null;
      let rectOk = false;
      if (rect) {
        rect.width = s.width;
        rect.height = s.height;
        rectOk = await settings.setVideoFrameRect(rect);
      }
      this._transact(project, "configurar sequência", () => [seq.createSetSettingsAction(settings)]);
      return rateOk && rectOk ? { applied: true } : { applied: false, reason: "sequence_settings_partial" };
    } catch (e) {
      return { applied: false, reason: "sequence_settings_not_available" };
    }
  }

  /** @param {any} seq */
  async setActiveSequence(seq) {
    const project = await this._requireProject();
    await project.setActiveSequence(seq);
  }

  async getActiveSequence() {
    const project = await this._project();
    if (!project) return null;
    try {
      const seq = await project.getActiveSequence();
      return seq ? { name: String(seq.name) } : null;
    } catch (_) {
      return null;
    }
  }

  // ------------------------------------------------------------ tracks / clips

  /**
   * @param {any} seq
   * @param {"video"|"audio"} kind
   * @param {number} index
   */
  async _track(seq, kind, index) {
    return kind === "video" ? seq.getVideoTrack(index) : seq.getAudioTrack(index);
  }

  /**
   * @param {any} seq
   * @param {"video"|"audio"} kind
   * @param {number} index
   * @param {string} name
   */
  async renameTrack(seq, kind, index, name) {
    const track = await this._track(seq, kind, index);
    if (!track) return false;
    if (track.name === name) return true;
    if (typeof track.createSetNameAction !== "function") return false;
    const project = await this._requireProject();
    this._transact(project, `nomear ${kind} ${index + 1}`, () => [track.createSetNameAction(name)]);
    return true;
  }

  /**
   * @param {any} seq
   * @param {"video"|"audio"} kind
   * @param {number} index
   */
  async listTrackClips(seq, kind, index) {
    const ppro = this.ppro;
    const track = await this._track(seq, kind, index);
    const items = track.getTrackItems(ppro.Constants.TrackItemType.CLIP, false) || [];
    /** @type {import("../core/types").TimelineClip[]} */
    const out = [];
    for (const ti of items) {
      try {
        const start = (await ti.getStartTime()).seconds;
        const end = (await ti.getEndTime()).seconds;
        const pi = await ti.getProjectItem();
        const clip = ppro.ClipProjectItem.cast(pi);
        const mediaPath = clip ? await clip.getMediaFilePath() : "";
        out.push({ start, end, mediaPath });
      } catch (_) {
        /* ignora itens sem mídia */
      }
    }
    return out;
  }

  /**
   * Overwrite de um trecho da mídia na timeline.
   * Usa in/out do clip de origem (padrão do Premiere) e restaura os valores anteriores.
   *
   * @param {any} seq
   * @param {any} item
   * @param {import("../core/types").PlaceClipRequest} req
   */
  async placeClip(seq, item, req) {
    const ppro = this.ppro;
    const project = await this._requireProject();
    const clip = ppro.ClipProjectItem.cast(item);
    if (!clip) throw new BridgeError("NOT_A_CLIP", "Item do projeto não é um clip de mídia.");
    const editor = ppro.SequenceEditor.getEditor(seq);
    if (!editor || typeof editor.createOverwriteItemAction !== "function") {
      throw new ApiNotAvailableError("overwrite_item", "overwrite_not_available");
    }

    /** @type {any} */
    let prevIn = null;
    /** @type {any} */
    let prevOut = null;
    try {
      prevIn = await clip.getInPoint(ppro.Constants.MediaType.VIDEO);
      prevOut = await clip.getOutPoint(ppro.Constants.MediaType.VIDEO);
    } catch (_) {
      /* mídia só de áudio etc. */
    }

    const tIn = ppro.TickTime.createWithSeconds(req.inPoint);
    const tOut = ppro.TickTime.createWithSeconds(req.outPoint);
    const tAt = ppro.TickTime.createWithSeconds(req.timelineStart);

    this._transact(project, "definir in/out", () => [clip.createSetInOutPointsAction(tIn, tOut)]);
    try {
      this._transact(project, "inserir clip", () => [
        editor.createOverwriteItemAction(item, tAt, req.videoTrackIndex, req.audioTrackIndex),
      ]);
    } finally {
      // devolve o clip de origem ao estado anterior (não destrutivo)
      try {
        this._transact(project, "restaurar in/out", () => [
          prevIn && prevOut ? clip.createSetInOutPointsAction(prevIn, prevOut) : clip.createClearInOutPointsAction(),
        ]);
      } catch (_) {
        /* não crítico */
      }
    }
  }

  // ------------------------------------------------------------ markers

  /** @param {any} seq */
  async _markers(seq) {
    const ppro = this.ppro;
    if (!ppro.Markers || typeof ppro.Markers.getMarkers !== "function") {
      throw new ApiNotAvailableError("markers", "markers_not_available");
    }
    return ppro.Markers.getMarkers(seq);
  }

  /** @param {any} seq */
  async listMarkers(seq) {
    const markers = await this._markers(seq);
    return (markers.getMarkers() || []).map((/** @type {any} */ m) => ({ name: m.getName(), start: m.getStart().seconds }));
  }

  /**
   * @param {any} seq
   * @param {import("../core/types").MarkerRequest} m
   */
  async addMarker(seq, m) {
    const ppro = this.ppro;
    const project = await this._requireProject();
    const markers = await this._markers(seq);
    const start = ppro.TickTime.createWithSeconds(m.start);
    const duration = m.duration > 0 ? ppro.TickTime.createWithSeconds(m.duration) : ppro.TickTime.TIME_ZERO;
    const type = (ppro.Marker && ppro.Marker.MARKER_TYPE_COMMENT) || "Comment";
    this._transact(project, `marker ${m.name}`, () => [markers.createAddMarkerAction(m.name, type, start, duration, m.comment)]);

    if (m.colorIndex === null || m.colorIndex === undefined) return { colorApplied: false };
    try {
      const fresh = await this._markers(seq);
      const created = (fresh.getMarkers() || []).find(
        (/** @type {any} */ x) => x.getName() === m.name && Math.abs(x.getStart().seconds - m.start) < 0.001
      );
      if (!created || typeof created.createSetColorByIndexAction !== "function") return { colorApplied: false };
      this._transact(project, `cor do marker ${m.name}`, () => [created.createSetColorByIndexAction(m.colorIndex)]);
      return { colorApplied: true };
    } catch (_) {
      return { colorApplied: false };
    }
  }

  // ------------------------------------------------------------ fase 2

  /**
   * Efeitos ficam para a fase 2 (VideoFilterFactory/ComponentChain ainda em evolução).
   * @param {any} _seq @param {any} effect
   */
  async applyEffect(_seq, effect) {
    return { applied: false, reason: "effect_not_available", effect: effect && effect.name };
  }

  // ------------------------------------------------------------ util

  /** @param {string} p */
  _native(p) {
    return paths.toNative(p, this.platform);
  }
}

module.exports = { PremiereHost };
