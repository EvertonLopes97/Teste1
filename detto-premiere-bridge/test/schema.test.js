"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { parseEditPlan, validateEditPlan } = require("../plugin/src/core/schema");
const { analyzePlan, formatPreview } = require("../plugin/src/core/analyze");
const { basePlan } = require("./helpers/fixtures");
const { MemoryFs } = require("./helpers/memoryFs");

const codes = (issues) => issues.map((i) => i.code);

test("plano de exemplo é válido", () => {
  const r = validateEditPlan(basePlan());
  assert.equal(r.valid, true, JSON.stringify(r.errors));
  assert.deepEqual(r.errors, []);
});

test.describe("JSON inválido", () => {
  test("texto que não é JSON", () => {
    const r = parseEditPlan("{ project: ");
    assert.equal(r.ok, false);
    assert.equal(r.error.code, "INVALID_JSON");
  });
  test("arquivo vazio", () => {
    const r = parseEditPlan("   ");
    assert.equal(r.ok, false);
    assert.equal(r.error.code, "EMPTY_PLAN");
  });
  test("aceita BOM do Windows", () => {
    const r = parseEditPlan("\uFEFF" + JSON.stringify(basePlan()));
    assert.equal(r.ok, true);
  });
  test("raiz não-objeto", () => {
    const r = validateEditPlan([1, 2]);
    assert.equal(r.valid, false);
    assert.deepEqual(codes(r.errors), ["INVALID_ROOT"]);
  });
  test("campos obrigatórios ausentes e tipos errados", () => {
    const plan = basePlan();
    delete plan.project;
    plan.sequence.fps = "30";
    plan.media = "nope";
    plan.cuts[0].start = -1;
    const r = validateEditPlan(plan);
    assert.equal(r.valid, false);
    assert.ok(codes(r.errors).includes("MISSING_PROJECT"));
    assert.ok(codes(r.errors).includes("MISSING_MEDIA"));
    assert.ok(r.errors.some((e) => e.path === "$.sequence.fps" && e.code === "INVALID_FIELD"));
    assert.ok(r.errors.some((e) => e.path === "$.cuts[0].start"));
  });
  test("chave desconhecida gera aviso, não erro", () => {
    const plan = basePlan();
    plan.foo = 1;
    const r = validateEditPlan(plan);
    assert.equal(r.valid, true);
    assert.ok(codes(r.warnings).includes("UNKNOWN_KEY"));
  });
});

test.describe("FPS incompatível", () => {
  test("project.fps diferente de sequence.fps é erro", () => {
    const plan = basePlan();
    plan.sequence.fps = 25;
    const r = validateEditPlan(plan);
    assert.equal(r.valid, false);
    assert.ok(codes(r.errors).includes("FPS_MISMATCH"));
  });
  test("29.97 e 29.97002997 são equivalentes", () => {
    const plan = basePlan();
    plan.project.fps = 29.97;
    plan.sequence.fps = 30000 / 1001;
    plan.cuts = [];
    const r = validateEditPlan(plan);
    assert.ok(!codes(r.errors).includes("FPS_MISMATCH"));
  });
  test("fps fora do padrão gera aviso", () => {
    const plan = basePlan();
    plan.project.fps = 33;
    plan.sequence.fps = 33;
    const r = validateEditPlan(plan);
    assert.ok(codes(r.warnings).includes("UNUSUAL_FPS"));
  });
  test("tempos fora da grade de frames geram aviso", () => {
    const plan = basePlan();
    plan.cuts[0].end = 4.321;
    const r = validateEditPlan(plan);
    assert.equal(r.valid, true);
    assert.ok(codes(r.warnings).includes("NOT_FRAME_ALIGNED"));
  });
});

test.describe("clip fora do intervalo", () => {
  test("end maior que a duração declarada da mídia", () => {
    const plan = basePlan();
    plan.cuts[0].end = 121;
    const r = validateEditPlan(plan);
    assert.ok(codes(r.errors).includes("CUT_OUT_OF_RANGE"));
  });
  test("end <= start", () => {
    const plan = basePlan();
    plan.cuts[0].start = 5;
    plan.cuts[0].end = 5;
    const r = validateEditPlan(plan);
    assert.ok(codes(r.errors).includes("INVALID_CUT_RANGE"));
  });
  test("timeline negativa", () => {
    const plan = basePlan();
    plan.cuts[0].timeline = -2;
    const r = validateEditPlan(plan);
    assert.ok(r.errors.some((e) => e.path === "$.cuts[0].timeline"));
  });
  test("cortes sobrepostos na mesma track geram aviso", () => {
    const plan = basePlan();
    plan.cuts[1].timeline = 2;
    const r = validateEditPlan(plan);
    assert.ok(codes(r.warnings).includes("CUT_OVERLAP"));
  });
});

test.describe("mídia / referências", () => {
  test("corte referencia mídia inexistente no plano", () => {
    const plan = basePlan();
    plan.cuts[0].source = "camera_999";
    const r = validateEditPlan(plan);
    assert.ok(codes(r.errors).includes("UNKNOWN_MEDIA_REFERENCE"));
  });
  test("track desconhecida", () => {
    const plan = basePlan();
    plan.cuts[0].track = "V9";
    const r = validateEditPlan(plan);
    assert.ok(codes(r.errors).includes("UNKNOWN_TRACK"));
  });
  test("track por nome de função é aceita", () => {
    const plan = basePlan();
    plan.cuts[0].track = "vfx references";
    plan.cuts[0].audioTrack = 3;
    assert.equal(validateEditPlan(plan).valid, true);
  });
});

test.describe("arquivo duplicado", () => {
  test("id de mídia duplicado é erro", () => {
    const plan = basePlan();
    plan.media.push({ id: "camera_001", path: "C:/videos/other.mp4" });
    const r = validateEditPlan(plan);
    assert.ok(codes(r.errors).includes("DUPLICATE_MEDIA_ID"));
  });
  test("mesmo arquivo com ids diferentes gera aviso (importado uma vez)", () => {
    const plan = basePlan();
    plan.media.push({ id: "camera_copy", path: "c:\\VIDEOS\\camera001.mp4" });
    const r = validateEditPlan(plan);
    assert.equal(r.valid, true);
    assert.ok(codes(r.warnings).includes("DUPLICATE_MEDIA_PATH"));
  });
  test("corte idêntico repetido gera aviso", () => {
    const plan = basePlan();
    plan.cuts.push({ ...plan.cuts[0] });
    const r = validateEditPlan(plan);
    assert.ok(codes(r.warnings).includes("DUPLICATE_CUT"));
  });
  test("marker duplicado gera aviso", () => {
    const plan = basePlan();
    plan.markers.push({ ...plan.markers[0] });
    assert.ok(codes(validateEditPlan(plan).warnings).includes("DUPLICATE_MARKER"));
  });
});

test("preview conta itens e detecta mídia ausente", async () => {
  const fs = new MemoryFs({ "C:/videos/camera001.mp4": "x" });
  const preview = await analyzePlan(basePlan(), fs);
  assert.deepEqual(preview.counts, { cuts: 3, markers: 1, graphics: 1, vfx: 1, effects: 1, assets: 2 });
  assert.deepEqual(preview.missingMedia, ["broll_001"]);
  assert.equal(preview.canExecute, true);
  assert.equal(preview.timelineTimecode, "00:00:14:12");
  const text = formatPreview(preview);
  assert.match(text, /Cortes: 3/);
  assert.match(text, /Assets: 2/);
  assert.match(text, /Mídias ausentes: broll_001/);
});
