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
  "defaults.json",
  "seminar_tables.json",
])
  py.FS.writeFile(
    "/home/pyodide/" + name,
    await readFile(resolve(root, "src", name), "utf8"),
  );
py.runPython("from engine import calculate_json");
for (const name of ["helical-seminar", "spur", "herringbone"]) {
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
  console.log(name + ": native CPython / WebAssembly parity passed");
}
