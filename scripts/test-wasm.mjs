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
for (const name of [
  "engine.py",
  "rating.py",
  "coefficients.py",
  "motor.py",
  "internal.py",
  "motors.json",
  "defaults.json",
  "seminar_tables.json",
  "assembly.py",
])
  py.FS.writeFile(
    "/home/pyodide/" + name,
    await readFile(resolve(root, "src", name), "utf8"),
  );
py.runPython(
  "from engine import calculate_json\nfrom assembly import assembly_json",
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
