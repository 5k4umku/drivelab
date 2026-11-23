import { readFile } from "node:fs/promises";
import vm from "node:vm";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { fmt } from "../src/format.js";
import assert from "node:assert/strict";
import { makeReport, makeAssemblyReport } from "../src/report.js";

// Та же версия библиотеки, что используется при выгрузке в браузере.
const D = vm.runInNewContext(
  (await readFile(
    new URL("../vendor/docx-9.6.1.js", import.meta.url),
    "utf8",
  )) + ";docx",
  {
    TextEncoder,
    TextDecoder,
    setTimeout,
    clearTimeout,
    setImmediate,
    Buffer,
    Uint8Array,
    ArrayBuffer,
  },
);
for (const [name, make] of [
  ["helical-seminar", makeReport],
  ["automatic-coefficients", makeReport],
  ["reducer-three-stage", makeAssemblyReport],
  ["internal-pair", makeReport],
  ["reducer-editor", makeAssemblyReport],
]) {
  const result = JSON.parse(
    await readFile(
      new URL(`../examples/${name}.result.json`, import.meta.url),
      "utf8",
    ),
  );
  const archive = await D.Packer.toBuffer(make(result, D));
  assert.ok(archive.length > 10000, `${name}: пустой отчёт`);
  assert.equal(
    archive.subarray(0, 2).toString(),
    "PK",
    `${name}: отсутствует ZIP-контейнер DOCX`,
  );
  console.log(`${name}: DOCX сформирован (${archive.length} байт)`);
}

// Check the values inside a freshly calculated report, including the engineering status.
const root = fileURLToPath(new URL("..", import.meta.url));
const stage = JSON.parse(execFileSync("python", ["-B", "src/engine.py", "examples/gost-annex-11.json"], {
  cwd: root, encoding: "utf8",
}));
const archive = await D.Packer.toBuffer(makeReport(stage, D));
const readDocument = `
import io, json, sys, zipfile
from xml.etree import ElementTree as ET
with zipfile.ZipFile(io.BytesIO(sys.stdin.buffer.read())) as doc:
    xml = ET.fromstring(doc.read('word/document.xml'))
print(json.dumps([node.text for node in xml.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')]))
`;
const runs = JSON.parse(execFileSync("python", ["-B", "-c", readDocument], {input: archive}));
for (const stress of [stage.rating.h, ...stage.rating.fs, stage.rating.hmax, ...stage.rating.fsmax])
  assert.ok(runs.includes(fmt(stress, 3)), "В отчёте отсутствует результат " + stress);
const pending = stage.checks.find(item => item.status === "pending");
assert.ok(runs.includes(pending.detail));
console.log("Приложение 11: в DOCX сверены шесть напряжений и условие применимости.");

const rootPair = JSON.parse(execFileSync("python", ["-B", "src/engine.py", "examples/gost-root-fatigue.json"], {
  cwd: root, encoding: "utf8",
}));
const rootDoc = await D.Packer.toBuffer(makeReport(rootPair, D));
const rootRuns = JSON.parse(execFileSync("python", ["-B", "-c", readDocument], {input: rootDoc}));
for (const [i, yd] of [.938966447, .912194723].entries()) {
  assert.ok(rootRuns.includes("Yδ" + (i + 1)));
  assert.ok(rootRuns.some(line => line?.includes(fmt(yd, 6))));
  assert.ok(rootRuns.some(line => line?.includes(rootPair.input.gost.roots[i].evidence)));
}
console.log("В DOCX проверены коэффициенты Yδ и обоснования обоих венцов.");
