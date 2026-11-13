// @ts-check
"use strict";

/**
 * Contratos (JSDoc) entre o núcleo do Bridge e os adaptadores de plataforma.
 * O núcleo (`src/core`) não importa nada de UXP/Premiere: tudo passa por estas
 * interfaces, o que permite testar o executor em Node com mocks.
 *
 * @typedef {Object} EnvironmentInfo
 * @property {boolean} connected
 * @property {string}  hostName
 * @property {string}  premiereVersion
 * @property {string}  uxpVersion
 * @property {string}  pluginVersion
 * @property {string}  platform          "win32" | "darwin" | ...
 *
 * @typedef {Object} ProjectInfo
 * @property {string} name
 * @property {string} path               caminho do .prproj ("" se nunca salvo)
 *
 * @typedef {Object} SequenceInfo
 * @property {string} name
 * @property {number|null} fps
 * @property {number|null} width
 * @property {number|null} height
 * @property {number} videoTrackCount
 * @property {number} audioTrackCount
 * @property {number} clipCount
 *
 * @typedef {Object} TimelineClip
 * @property {number} start              segundos na timeline
 * @property {number} end
 * @property {string} mediaPath
 *
 * @typedef {Object} PlaceClipRequest
 * @property {number} inPoint            segundos na mídia
 * @property {number} outPoint
 * @property {number} timelineStart      segundos na sequência
 * @property {number} videoTrackIndex    zero-based
 * @property {number} audioTrackIndex    zero-based
 *
 * @typedef {Object} MarkerRequest
 * @property {string} name
 * @property {number} start
 * @property {number} duration
 * @property {string} comment
 * @property {number|null} colorIndex
 *
 * @typedef {Object} HostAdapter
 * @property {() => Promise<EnvironmentInfo>} getEnvironment
 * @property {() => Promise<ProjectInfo|null>} getActiveProject
 * @property {(path: string) => Promise<ProjectInfo>} openProject
 * @property {(path: string) => Promise<ProjectInfo>} createProject
 * @property {() => Promise<void>} saveProject
 * @property {() => Promise<Array<{path: string, item: any}>>} listMediaItems
 * @property {(name: string) => Promise<any>} ensureBin
 * @property {(paths: string[], bin: any) => Promise<Array<{path: string, item: any}>>} importFiles
 * @property {(name: string) => Promise<any|null>} findSequence
 * @property {(name: string, opts: {presetPath?: string}) => Promise<any>} createSequence
 * @property {(seq: any) => Promise<SequenceInfo>} getSequenceInfo
 * @property {(seq: any, s: {fps: number, width: number, height: number}) => Promise<{applied: boolean, reason?: string}>} applySequenceSettings
 * @property {(seq: any) => Promise<void>} setActiveSequence
 * @property {() => Promise<{name: string}|null>} getActiveSequence
 * @property {(seq: any, kind: "video"|"audio", index: number, name: string) => Promise<boolean>} renameTrack
 * @property {(item: any) => Promise<number|null>} getMediaDuration
 * @property {(seq: any, kind: "video"|"audio", index: number) => Promise<TimelineClip[]>} listTrackClips
 * @property {(seq: any, item: any, req: PlaceClipRequest) => Promise<void>} placeClip
 * @property {(seq: any) => Promise<Array<{name: string, start: number}>>} listMarkers
 * @property {(seq: any, m: MarkerRequest) => Promise<{colorApplied: boolean}>} addMarker
 * @property {(seq: any, effect: any) => Promise<{applied: boolean, reason?: string}>} applyEffect
 *
 * @typedef {Object} FileSystemAdapter
 * @property {(path: string) => Promise<boolean>} exists
 * @property {(path: string) => Promise<string>} readText
 * @property {(path: string, text: string) => Promise<void>} writeText
 * @property {(path: string) => Promise<string[]>} readdir   nomes de arquivos (não caminhos)
 * @property {(path: string) => Promise<void>} mkdirp
 * @property {(from: string, to: string) => Promise<void>} move
 * @property {(from: string, to: string) => Promise<void>} copyFile
 */

module.exports = {};
