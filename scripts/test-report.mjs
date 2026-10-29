import { readFile } from "node:fs/promises";
import vm from "node:vm";
import assert from "node:assert/strict";
import { makeReport, makeAssemblyReport } from "../src/report.js";

// Та же версия библиотеки, что используется при выгрузке в браузере.
const D = vm.runInNewContext(
  await readFile(new URL("../vendor/docx-9.6.1.js", import.meta.url), "utf8") + ";docx",
  { TextEncoder, TextDecoder, setTimeout, clearTimeout, setImmediate, Buffer, Uint8Array, ArrayBuffer },
);
for (const [name, make] of [
  ["helical-seminar", makeReport],
  ["reducer-three-stage", makeAssemblyReport],
]) {
  const result = JSON.parse(await readFile(new URL(`../examples/${name}.result.json`, import.meta.url), "utf8"));
  const archive = await D.Packer.toBuffer(make(result, D));
  assert.ok(archive.length > 10000, `${name}: пустой отчёт`);
  assert.equal(archive.subarray(0, 2).toString(), "PK", `${name}: отсутствует ZIP-контейнер DOCX`);
  console.log(`${name}: DOCX сформирован (${archive.length} байт)`);
}
