/* CPython runs in a dedicated worker; no numeric engineering implementation here. */
self.postMessage({ type: "phase", message: "Загрузка CPython / WASM…" });
importScripts("../vendor/pyodide/pyodide.js");
const ready = (async () => {
  const runtime = await loadPyodide({
    indexURL: new URL("../vendor/pyodide/", self.location).href,
  });
  self.postMessage({ type: "phase", message: "Загрузка расчётной модели…" });
  for (const name of [
    "engine.py",
    "selection.py", "automation.py", "tolerances.py",
    "defaults.json",
    "rating.py",
    "coefficients.py",
    "motor.py",
    "internal.py",
    "motors.json",
    "seminar_tables.json",
    "assembly.py",
  ]) {
    const response = await fetch(new URL(name, self.location));
    if (!response.ok) throw Error(`Не удалось загрузить ${name}`);
    runtime.FS.writeFile("/home/pyodide/" + name, await response.text());
  }
  await runtime.runPythonAsync(
    "from engine import calculate_json, material_pair, MATERIALS\nfrom assembly import assembly_json\nfrom automation import tools_json\nimport json",
  );
  self.postMessage({ type: "phase", message: "Расчёт исходного варианта…" });
  self.postMessage({
    type: "ready",
    python: runtime.runPython("import sys; sys.version.split()[0]"),
  });
  return runtime;
})();
async function handle(data) {
  try {
    const py = await ready;
    py.globals.set("payload", JSON.stringify(data.input));
    const output = await py.runPythonAsync(
      data.type === "tools" ? "tools_json(payload)" : data.type === "material"
        ? "json.dumps(material_pair(json.loads(payload)), ensure_ascii=False)"
        : data.type === "assembly"
          ? "assembly_json(payload)"
          : "calculate_json(payload)",
    );
    self.postMessage({
      id: data.id,
      type: data.type,
      result: JSON.parse(output),
    });
  } catch (error) {
    self.postMessage({ id: data.id, type: "error", message: String(error) });
  }
}
let queue = Promise.resolve();
self.onmessage = ({ data }) => {
  queue = queue.then(() => handle(data));
};
ready.catch((error) =>
  self.postMessage({ type: "error", message: String(error) }),
);
