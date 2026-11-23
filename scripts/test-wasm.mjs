import { createRequire } from "node:module";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import assert from "node:assert/strict";
const root = resolve(import.meta.dirname, "..");
const require = createRequire(import.meta.url);
const { loadPyodide } = require("../vendor/pyodide/pyodide.js");
const py = await loadPyodide({
  indexURL: resolve(root, "vendor/pyodide") + "/",
});
const files = JSON.parse(await readFile(resolve(root, "src/python-files.json"), "utf8"));
for (const name of files)
  py.FS.writeFile(
    "/home/pyodide/" + name,
    await readFile(resolve(root, "src", name), "utf8"),
  );
py.runPython(
  "from engine import calculate_json\nfrom assembly import assembly_json\nfrom automation import tools_json",
);
for (const name of [
  "helical-seminar",
  "spur",
  "herringbone",
  "automatic-coefficients",
]) {
  const input = JSON.parse(
    await readFile(resolve(root, "examples", name + ".json"), "utf8"),
  ).input;
  const expected = JSON.parse(
    await readFile(resolve(root, "examples", name + ".result.json"), "utf8"),
  );
  py.globals.set("payload", JSON.stringify(input));
  const actual = JSON.parse(py.runPython("calculate_json(payload)"));
  for (const key of ["m", "z1", "z2", "beta", "Fa", "Ft"])
    assert.ok(
      Math.abs(actual.chosen[key] - expected.chosen[key]) < 1e-8,
      `${name}: ${key}`,
    );
  assert.ok(
    Math.abs(actual.rating.h - expected.rating.h) < 1e-8,
    `${name}: stress`,
  );
  for (const key of ["muH", "muF", "YA", "KA", "YR", "ZR"])
    assert.equal(actual.input[key], expected.input[key], key);
  assert.deepEqual(actual.rating.faceAuto, expected.rating.faceAuto);
  console.log(name + ": native CPython / WebAssembly parity passed");
}
for (const [action, args, check] of [
  [
    "zubil",
    { low: 80, high: 90, ratio: 3, tolerance: 3 },
    (r) => assert.deepEqual([r.best.z1, r.best.z2, r.best.lcm], [23, 67, 1541]),
  ],
  [
    "fit",
    { diameter: 40, hole_grade: 7, shaft_grade: 6 },
    (r) => assert.equal(r.gapMax, 0.041),
  ],
]) {
  py.globals.set("payload", JSON.stringify({ action, args }));
  check(JSON.parse(py.runPython("tools_json(payload)")));
}
py.runPython("from assembly import from_single");
const assisted = JSON.parse(
  py.runPython(
    "tools_json(__import__('json').dumps(dict(action='search',project=from_single(),index=0)))",
  ),
);
assert.equal(assisted.count, 24);
assert.ok(assisted.accepted > 0);
console.log("Zubil, IT и автоподбор: WebAssembly проверен.");
const reducer = JSON.parse(
  await readFile(resolve(root, "examples/reducer-three-stage.json"), "utf8"),
);
const reference = JSON.parse(
  await readFile(
    resolve(root, "examples/reducer-three-stage.result.json"),
    "utf8",
  ),
);
py.globals.set("payload", JSON.stringify({ project: reducer.project }));
const assembly = JSON.parse(py.runPython("assembly_json(payload)"));
assert.equal(assembly.errors.length, 0);
for (const key of ["totalRatio", "outputPower", "outputSpeed", "outputTorque"])
  assert.ok(Math.abs(assembly[key] - reference[key]) < 1e-8, key);
for (let i = 0; i < assembly.shafts.length; i++)
  for (const key of ["radial", "axial"])
    assert.ok(
      Math.abs(assembly.shafts[i].A[key] - reference.shafts[i].A[key]) < 1e-8,
      `Вал ${i + 1}: ${key}`,
    );
console.log(
  "Редуктор: кинематика и реакции опор CPython / WebAssembly совпадают.",
);

for (const name of ["internal-pair", "reducer-editor"]) {
  const input = JSON.parse(
    await readFile(resolve(root, "examples", name + ".json"), "utf8"),
  );
  const expected = JSON.parse(
    await readFile(resolve(root, "examples", name + ".result.json"), "utf8"),
  );
  py.globals.set(
    "payload",
    JSON.stringify(input.project ? { project: input.project } : input.input),
  );
  const actual = JSON.parse(
    py.runPython(
      input.project ? "assembly_json(payload)" : "calculate_json(payload)",
    ),
  );
  assert.deepEqual(actual.errors, []);
  if (input.project) {
    for (const key of ["outputSpeed", "outputTorque", "totalRatio"])
      assert.ok(Math.abs(actual[key] - expected[key]) < 1e-8, key);
    assert.deepEqual(actual.motor, expected.motor);
    for (let i = 0; i < actual.shafts.length; i++) {
      assert.equal(
        actual.shafts[i].signedSpeed,
        expected.shafts[i].signedSpeed,
      );
      for (let k = 0; k < 3; k++)
        assert.ok(
          Math.abs(
            actual.shafts[i].A.vector[k] - expected.shafts[i].A.vector[k],
          ) < 1e-8,
        );
    }
  } else {
    for (const key of ["a", "da2", "df2", "epsilonAlpha", "Fa"])
      assert.ok(
        Math.abs(actual.chosen[key] - expected.chosen[key]) < 1e-8,
        key,
      );
    assert.equal(actual.rating.available, false);
  }
  console.log(name + ": CPython / WebAssembly совпадают.");
}

const annex = JSON.parse(await readFile(resolve(root, "examples/gost-annex-11.json"), "utf8"));
function calculateStage(input) {
  py.globals.set("payload", JSON.stringify(input));
  const assembly = JSON.parse(py.runPython(
    "assembly_json(json.dumps({'project': from_single(json.loads(payload))}))",
  ));
  assert.deepEqual(assembly.errors, []);
  return assembly.stages[0].result;
}
py.runPython("import json");
const stage = calculateStage(annex.input);
assert.equal(stage.rating.mandatoryPending, true);
assert.ok(Math.abs(stage.rating.h - 764.41) < 0.02);
for (const [i, expected] of [227.85, 217.01].entries())
  assert.ok(Math.abs(stage.rating.fs[i] - expected) < 0.02);
const spectrum = [{ torqueRatio: 1, timeFraction: 1 }];
for (const method of ["cycles", "stresses"]) {
  const r = calculateStage({ gost: { spectrum, spectrumMethod: method } }).rating;
  assert.equal(r.available, true);
  assert.equal(r.method, "gost-spectrum-" + method);
  assert.ok(Number.isFinite(r.hmax));
  if (method === "stresses") {
    assert.equal(r.h, null);
    assert.equal(r.mandatoryPending, true);
  }
}
const withCriteria = calculateStage({ gost: { criteria: { lifeLimitHours: 100000 } } });
assert.ok(withCriteria.rating.criteria.life.hours > 0);
console.log("Приложение 11, циклограммы и критерий ресурса проверены в сборке редуктора WASM.");

for (const loads of [[2], [1, -2], [1, 2]]) {
  const spectrum = loads.map(torqueRatio => ({torqueRatio, timeFraction: 1 / loads.length}));
  const stage = calculateStage({startup: 1, KA: 1, life: 20000, autoTables: false,
    gost: {spectrum, spectrumMethod: "cycles", design: {}}});
  assert.equal(stage.rating.available, true);
  if (loads[1] === 2) {
    assert.equal(stage.design.available, false);
    assert.match(stage.design.reason, /нагрузка по истории/);
    continue;
  }
  assert.equal(stage.design.cases.length, loads.length);
  for (const [i, item] of stage.design.cases.entries()) {
    assert.ok(Math.abs(item.T2H - stage.T * stage.chosen.u * Math.abs(loads[i])) < 1e-8);
    assert.equal(item.T2F, item.T2H);
    if (i === 1) assert.equal(item.side, "обратный ход");
  }
}
console.log("Раздел 5: фактические моменты, реверс и ограничение переменной нагрузки проверены.");

const rootExample = JSON.parse(await readFile(resolve(root, "examples/gost-root-fatigue.json"), "utf8")).input;
const rootsStage = calculateStage(rootExample);
assert.equal(rootsStage.rating.available, true, rootsStage.rating.reason);
for (const [i, value] of [.938966447, .912194723].entries()) {
  assert.ok(Math.abs(rootsStage.rating.roots[i].Ydelta - value) < 1e-8);
  assert.ok(rootsStage.trace.some(s => s.title === "Yδ" + (i+1) && Math.abs(s.value - value) < 1e-8));
}
for (const radius of [7, 7.0001]) {
  const measured = {radiusMm: radius, uncertaintyMm: 0, section: "Нормальное сечение", evidence: "Контроль"};
  const result = calculateStage({...rootExample, gost: {...rootExample.gost, roots: [measured, measured]}});
  const expected = radius === 7 ? [.874891363, .874891363] : [.942374152, .926780523];
  expected.forEach((value,i) => assert.ok(Math.abs(result.rating.roots[i].Ydelta - value) < 1e-8));
}
console.log("Yδ обоих венцов и порог 7 мм проверены в WASM.");
