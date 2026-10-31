import { fmt, escapeHTML as e, statusLabel } from "./format.js";
import { GearViewer } from "./viewer.js";
import { createBuilder, projectFromInput } from "./builder.js";
import { settingsFields, bindSettings, coefficientPanel } from "./settings.js";
import { setupShell } from "./shell.js";
import { createWorkbench } from "./workbench.js";
let workbench;
const toolCalls = new Map();
let toolSequence = -1;
const $ = (s) => document.querySelector(s),
  $$ = (s) => [...document.querySelectorAll(s)];
const defaults = await fetch("src/defaults.json").then((r) => r.json());
let inputs = { ...defaults },
  result = null,
  sequence = 0,
  lastId = 0,
  viewer,
  builder,
  assembly = null,
  activeStage = 0;
let project = projectFromInput(inputs);
const STORAGE = "drivelab-project-v1";
try {
  const saved = JSON.parse(localStorage.getItem(STORAGE));
  if (saved?.version === 1) project = projectFromInput(cleanInput(saved.input));
  if (saved?.version === 2) project = cleanProject(saved.project);
  activeStage =
    Number.isInteger(saved?.activeStage) &&
    saved.activeStage >= 0 &&
    saved.activeStage < project.stages.length
      ? saved.activeStage
      : 0;
  inputs = cleanInput(project.stages[activeStage].input);
} catch {
  project = projectFromInput(defaults);
  activeStage = 0;
  inputs = { ...defaults };
}
function cleanProject(data) {
  if (
    !data ||
    !Array.isArray(data.stages) ||
    !data.stages.length ||
    data.stages.length > 64 ||
    !Array.isArray(data.shafts)
  )
    throw Error("Некорректная структура редуктора");
  return {
    ...data,
    stages: data.stages.map((s) => ({ ...s, input: cleanInput(s.input) })),
  };
}
function cleanInput(data) {
  if (!data || typeof data !== "object" || Array.isArray(data))
    throw Error("Некорректные исходные данные");
  const unknown = Object.keys(data).filter(
    (key) => !(key in defaults) && key !== "gost",
  );
  if (unknown.length)
    throw Error("Неподдерживаемые параметры проекта: " + unknown.join(", "));
  const out = { ...defaults };
  for (const key of Object.keys(defaults))
    if (key in data) out[key] = data[key];
  if (data.gost && typeof data.gost === "object" && !Array.isArray(data.gost))
    out.gost = data.gost;
  return out;
}
function toast(text) {
  $("#toast").textContent = text;
  $("#toast").classList.add("visible");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => $("#toast").classList.remove("visible"), 4500);
}
function download(blob, name) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
function showError(message) {
  builder?.error(message);
  $("#errors").hidden = false;
  $("#errors").textContent = message;
  document.body.classList.remove("recalculating");
  document.body.classList.add("invalid-input");
  $("#export-word").disabled = true;
}
const worker = new Worker(new URL("./worker.js", import.meta.url));
worker.onerror = (err) => showError(`Ошибка расчётного ядра: ${err.message}`);
worker.onmessage = ({ data }) => {
  if (toolCalls.has(data.id)) {
    const call = toolCalls.get(data.id);
    toolCalls.delete(data.id);
    if (data.type === "error") call.reject(new Error(data.message));
    else call.resolve(data.result);
    return;
  }
  if (data.type === "phase") {
    $("#engine-status").textContent = data.message;
    return;
  }
  if (data.type === "ready") {
    $("#engine-status").textContent = `Python ${data.python} · готов`;
    return;
  }
  if (data.type === "error") {
    if (!data.id || data.id === lastId) showError(data.message);
    return;
  }
  if (data.id !== lastId) return;
  if (data.type === "material") {
    inputs = data.result;
    run();
    return;
  }
  assembly = data.result;
  document.body.classList.remove("recalculating");
  if (assembly.errors?.length) {
    showError(assembly.errors.join(" · "));
    return;
  }
  result = assembly.stages[activeStage].result;
  project = assembly.project;
  inputs = structuredClone(result.input);
  $("#errors").hidden = true;
  document.body.classList.remove("invalid-input");
  $("#export-word").disabled = false;
  try {
    localStorage.setItem(
      STORAGE,
      JSON.stringify({ version: 2, project, activeStage }),
    );
  } catch {
    toast("Автосохранение недоступно. Сохраните проект в JSON.");
  }
  render();
  builder.render(assembly);
  workbench?.update(result);
};
function run(type = "calculate") {
  workbench?.invalidate();
  lastId = ++sequence;
  document.body.classList.add("recalculating");
  $("#export-word").disabled = true;
  builder?.busy();
  if (type === "material")
    worker.postMessage({ id: lastId, type, input: inputs });
  else {
    project.stages[activeStage].input = structuredClone(inputs);
    worker.postMessage({
      id: lastId,
      type: "assembly",
      input: { project, activeStage },
    });
  }
}
function render() {
  const r = result,
    c = r.chosen;
  let panel = $("#coefficients");
  if (!panel) {
    panel = document.createElement("section");
    panel.id = "coefficients";
    panel.className = "page-section";
    $("#calculation").before(panel);
  }
  panel.innerHTML = coefficientPanel(r);
  $("#active-stage-label").textContent =
    `Ступень ${activeStage + 1} из ${project.stages.length}`;
  $("#project-heading").innerHTML =
    { spur: "Прямозубая", helical: "Косозубая", herringbone: "Шевронная" }[
      inputs.gearType
    ] + " передача<span>.</span>";
  $$("[data-type]").forEach((el) =>
    el.classList.toggle("selected", el.dataset.type === inputs.gearType),
  );
  $("#variant-count").textContent = r.variants.length;
  $("#metrics").innerHTML = [
    ["Межосевое расстояние", r.a, "мм", `Расчётное ${fmt(r.ac)} мм`],
    [
      "Нормальный модуль",
      c?.m,
      "мм",
      inputs.meshType === "internal"
        ? "Заданная геометрия"
        : "По таблице стандартных модулей",
    ],
    [
      "Момент на входе",
      r.T,
      "Н·м",
      `${fmt(inputs.power)} кВт · ${fmt(inputs.speed, 0)} мин⁻¹`,
    ],
    [
      "Рабочая ширина",
      r.b,
      "мм",
      inputs.gearType === "herringbone"
        ? "Суммарная ширина двух половин"
        : `ψba = ${fmt(r.psi, 4)}`,
    ],
  ]
    .map(
      ([name, value, unit, note]) =>
        `<div class="metric"><label>${e(name)}</label><strong>${fmt(value)}<span>${e(unit)}</span></strong><small>${e(note)}</small></div>`,
    )
    .join("");
  if (c) {
    $("#design-title").textContent = `${c.z1} : ${c.z2}`;
    $("#design-subtitle").textContent =
      inputs.meshType === "internal"
        ? "Внутреннее зацепление: номинальная геометрия по ГОСТ 19274–73."
        : c.m === r.recommended?.m
          ? inputs.selectionPolicy === "zubil"
            ? "Максимальный НОК среди найденных пар в допуске; прочность проверяется отдельно."
            : "Минимальная ошибка передаточного числа среди найденных пар."
          : "Выбран вручную для сравнения с рекомендацией.";
    $("#design-values").innerHTML = [
      ["Передаточное число", fmt(c.u, 6)],
      ["Отклонение", fmt(c.errorPct, 4) + " %"],
      ["Угол наклона β", fmt(c.beta) + "°"],
      ["Окружная сила Ft", fmt(c.Ft) + " Н"],
      ["Осевая сила Fa", fmt(c.Fa) + " Н"],
      ...(inputs.gearType === "herringbone"
        ? [
            [
              "Левый / правый венец",
              fmt(c.FaLeft ?? c.FaHalf) +
                " / " +
                fmt(c.FaRight ?? -c.FaHalf) +
                " Н",
            ],
          ]
        : []),
    ]
      .map(([a, b]) => `<div><dt>${e(a)}</dt><dd>${e(b)}</dd></div>`)
      .join("");
    $("#legend-z1").textContent = `z₁ = ${c.z1}`;
    $("#legend-z2").textContent = `z₂ = ${c.z2}`;
    $("#rpm-label").textContent =
      `n₁ ${fmt(inputs.speed, 0)} / n₂ ${fmt(c.n2, 2)} мин⁻¹`;
    try {
      if (!viewer) viewer = new GearViewer($("#gear-view"));
      viewer.update(r);
      $("#play-toggle").textContent = viewer.playing ? "Ⅱ" : "▶";
    } catch (error) {
      $("#gear-view").textContent =
        "WebGL недоступен. Все числовые результаты и отчёт доступны ниже.";
      console.error(error);
    }
  } else {
    $("#design-title").textContent = "Нет вариантов";
    $("#design-subtitle").textContent =
      "Измените межосевое расстояние, ширину, модуль или максимальный угол.";
    $("#design-values").innerHTML = "";
  }
  $("#profile-note").textContent =
    inputs.meshType === "internal"
      ? "Внутреннее зацепление: геометрия по ГОСТ 19274–73. Прочность и полная интерференция требуют отдельного расчёта."
      : "Расчёт по семинарам и проверка по формулам ГОСТ 21354–87.";
  $("#material-rule-note").textContent =
    inputs.materialMode === "custom"
      ? "Свойства заданы пользователем; источник указан в исходных данных."
      : "Колесо на две строки мягче шестерни по Т1.";
  $("#materials-summary").textContent =
    inputs.materialMode === "custom"
      ? `${inputs.material1} / ${inputs.material2} · свои свойства`
      : `${inputs.material1} · ${inputs.rowName1} / ${inputs.rowName2}`;
  const failed = r.checks.filter((x) => x.status === "fail").length,
    pending = r.checks.filter((x) => x.status === "pending").length,
    passed = r.checks.filter((x) => x.status === "pass").length;
  $("#check-count").textContent = `${passed}/${r.checks.length}`;
  $("#summary-status").className = "status-box " + r.status;
  $("#summary-status").textContent = failed
    ? `Не выполнено условий: ${failed}. ${pending ? `Требуют уточнения: ${pending}.` : ""}`
    : pending
      ? `Числовые проверки выполнены. Требуют уточнения: ${pending}.`
      : "Проверки для заданной модели выполнены.";
  $("#check-summary").textContent =
    `Выполнено ${passed} · не выполнено ${failed} · уточнить ${pending}`;
  $("#checks-list").innerHTML = r.checks
    .map(
      (x) =>
        `<article class="check"><span class="check-symbol ${e(x.status)}">${x.status === "pass" ? "✓" : x.status === "fail" ? "×" : "!"}</span><div><h3>${e(x.title)}</h3><p>${e(x.detail)}</p></div></article>`,
    )
    .join("");
  $("#variants-body").innerHTML =
    r.variants
      .map(
        (v) =>
          `<tr class="${v.m === c?.m ? "is-selected" : ""}" data-module="${v.m}"><td>${fmt(v.m)}</td><td>${v.z1} / ${v.z2}</td><td>${fmt(v.u, 6)}</td><td>${fmt(v.errorPct, 4)}</td><td>${fmt(v.beta)}</td><td>${fmt(v.Fa)}</td><td style="color:var(${v.contactMargin >= 1 ? "--green" : "--red"})">${fmt(v.contactMargin, 3)}</td><td><button class="pick" aria-label="Выбрать модуль ${fmt(v.m)}">${v.m === c?.m ? "Выбран" : v.m === r.recommended?.m ? "Рекомендован" : "Выбрать"}</button></td></tr>`,
      )
      .join("") ||
    '<tr><td colspan="8">Допустимые сочетания не найдены. Проверьте исходные данные.</td></tr>';
  $$("#variants-body tr[data-module]").forEach((el) =>
    el.addEventListener("click", () => {
      inputs.selectedModule = Number(el.dataset.module);
      run();
    }),
  );
  $("#size-comparison").innerHTML = (r.sizeComparison || [])
    .map(
      (v) =>
        `<button class="size-option ${v.a === r.a ? "selected" : ""}" data-aw="${v.a}"><label>aw = <b>${fmt(v.a)} мм</b></label><span>bw ${fmt(v.b)} мм · mn ${fmt(v.m)} мм</span><strong class="${v.contactMargin >= 1 ? "pass" : "fail"}">σHP / σH = ${fmt(v.contactMargin, 3)}</strong><small>${v.tablesValid ? "Т7 соответствует размерам" : "Т7 требует уточнения"} · ${v.a === r.a ? "Текущий размер" : "Применить размер ↗"}</small></button>`,
    )
    .join("");
  $$(".size-option").forEach(
    (el) =>
      (el.onclick = () => {
        inputs.aOverride = Number(el.dataset.aw);
        inputs.selectedModule = 0;
        run();
        toast("Геометрия и проверки пересчитываются.");
      }),
  );
  const rating = r.rating;
  if (rating?.available) {
    $("#strength-cards").innerHTML = [
      ["Контактная выносливость", rating.h, rating.hAllow],
      ["Изгиб шестерни", rating.fs?.[0], rating.fAllow?.[0]],
      ["Изгиб колеса", rating.fs?.[1], rating.fAllow?.[1]],
    ]
      .map(
        ([label, value, limit]) =>
          `<article class="strength-card"><label>${label}</label><strong>${fmt(value, 1)} <small>МПа</small></strong><div class="bar"><i style="width:${Math.min(100, (100 * value) / limit)}%;background:${value > limit ? "var(--red)" : "var(--green)"}"></i></div><small>Допускаемое ${fmt(limit, 1)} МПа · использование ${fmt((100 * value) / limit, 1)}%</small></article>`,
      )
      .join("");
  } else
    $("#strength-cards").innerHTML = rating?.reason
      ? `<p class="field-note">${e(rating.reason)}</p>`
      : "";
  const open = new Set(
    $$("#trace details[open]").map((x) => x.dataset.section),
  );
  const sections = Map.groupBy
    ? Map.groupBy(r.trace, (x) => x.section)
    : r.trace.reduce(
        (m, x) => (
          m.has(x.section) ? m.get(x.section).push(x) : m.set(x.section, [x]),
          m
        ),
        new Map(),
      );
  $("#trace").innerHTML = [...sections]
    .map(
      ([name, steps], i) =>
        `<details data-section="${e(name)}" ${open.has(name) || i === 0 ? "open" : ""}><summary>${e(name)} <span class="muted">${steps.length} шагов</span></summary>${steps.map((s) => `<div class="trace-step"><h3>${e(s.title)}</h3><div class="equation">${e(s.formula)}</div><div class="substitution">${e(s.substitution)}</div><div class="result">= ${fmt(s.value, 6)} ${e(s.unit)}</div><div class="source">${e(s.source)}</div></div>`).join("")}</details>`,
    )
    .join("");
}
const inputGroups = [
  [
    "Режим и исходные данные",
    [
      ["power", "Мощность P₁, кВт"],
      ["speed", "Частота n₁, мин⁻¹"],
      ["ratio", "Передаточное число u"],
      ["efficiency", "КПД η"],
      ["life", "Ресурс L, ч"],
      ["KA", "Внешняя динамика KA"],
      ["startup", "Пусковой коэффициент Kп"],
      ["peakCount", "Число пусков за ресурс (0 — неизвестно)"],
    ],
  ],
  [
    "Геометрия и выбор вариантов",
    [
      ["psiBd", "Коэффициент ширины ψbd"],
      ["aOverride", "Межосевое aw, мм (0 — подобрать)"],
      ["betaMax", "Максимальный угол β, °"],
      ["ratioTolerance", "Допуск передаточного числа, %"],
      ["modules", "Модули, мм (через пробел)", "text"],
    ],
  ],
  [
    "Табличные коэффициенты семинара",
    [
      ["KHbeta", "KHβ по Т5"],
      ["KFbeta", "KFβ по Т5"],
      ["g0", "g₀ по Т7"],
      ["fpb1", "fpb₁, мкм"],
      ["fpb2", "fpb₂, мкм"],
      ["deltaH", "δH по Т6"],
      ["deltaF", "δF по Т6"],
      ["muH", "μH, режим нагружения"],
      ["muF", "μF, режим нагружения"],
      ["SH", "Запас SH"],
      ["SF", "Запас SF"],
      ["ZVZL", "Произведение ZV ZL"],
    ],
  ],
];
function showInputs() {
  $("#input-fields").innerHTML =
    `<fieldset><legend>Материал и термообработка</legend><div class="field-grid"><label class="field">Материал шестерни<input name="material1" value="${e(inputs.material1)}" maxlength="100"></label><label class="field">Материал колеса<input name="material2" value="${e(inputs.material2)}" maxlength="100"></label><label class="field wide">Класс шестерни по Т1<select name="row1">${["У345", "У395", "У440", "У490", "У540", "У590", "У640", "У685", "У735", "У785"].map((v, i) => `<option value="${i}" ${i < 2 ? "disabled" : ""} ${inputs.row1 === i ? "selected" : ""}>${v}</option>`).join("")}</select></label></div><div class="material-preview">Шестерня: <b>${e(inputs.rowName1)}</b> · ${inputs.hb1min}–${inputs.hb1max} HB<br>Колесо: <b>${e(inputs.rowName2)}</b> · ${inputs.hb2min}–${inputs.hb2max} HB</div><p class="field-note">Класс шестерни остаётся по таблице. Колесо автоматически получает класс на две строки мягче. При смене класса проверьте достижимость свойств выбранной стали и размер заготовки.</p></fieldset>` +
    inputGroups
      .map(
        ([title, fields]) =>
          `<fieldset><legend>${e(title)}</legend><div class="field-grid">${fields.map(([key, label, type = "number"]) => `<label class="field ${type === "text" ? "wide" : ""}">${e(label)}<input name="${key}" type="${type}" ${type === "number" ? 'min="0" step="any"' : ""} required ${activeStage > 0 && ["power", "speed"].includes(key) ? "readonly" : ""} value="${e(inputs[key])}"></label>`).join("")}</div></fieldset>`,
      )
      .join("") +
    `<label class="checkbox-field"><input name="excludeEdges" type="checkbox" ${inputs.excludeEdges ? "checked" : ""}> Исключать крайние модули, когда доступно больше четырёх</label><fieldset><legend>Условия проверки по ГОСТ</legend><p class="field-note">Коэффициенты по ширине приняты по семинарской таблице Т5. Их окончательное уточнение требует расчёта валов и опор. Подтверждения сохраняются в отчёте.</p><label class="checkbox-field"><input name="faceFactorsConfirmed" type="checkbox" ${inputs.gost?.faceFactorsConfirmed ? "checked" : ""}> Коэффициенты KHβ и KFβ подтверждены для проекта</label><label class="checkbox-field"><input name="surfaceConfirmed" type="checkbox" ${inputs.gost?.surfaceConfirmed ? "checked" : ""}> Условия поверхности и смазки проверены по принятой модели</label></fieldset>`;
  const tables = document.createElement("fieldset");
  tables.innerHTML = `<legend>Выбор табличных данных</legend><label class="checkbox-field"><input name="autoTables" type="checkbox" ${inputs.autoTables ? "checked" : ""}> Автоматически выбирать δH, δF по Т6 и погрешности fpb по Т7</label><p class="field-note">Точность выбирается в настройках нагрузки. При включении введённые вручную δH, δF и fpb заменяются табличными для типа зубьев и фактических диаметров. g₀ используется в проектировочном расчёте; проверочная динамика выбирает g₀ по ГОСТ.</p>`;
  $("#input-fields").append(tables);
  const peak = document.createElement("fieldset");
  peak.innerHTML = `<legend>Максимальная нагрузка</legend><label class="field">Коэффициент Sγ<input name="peakProbabilityFactor" type="number" min="1" step="any" value="${e(inputs.gost?.peakProbabilityFactor ?? 1.75)}" required></label><label class="checkbox-field"><input name="peakProbabilityFactorConfirmed" type="checkbox" ${inputs.gost?.peakProbabilityFactorConfirmed ? "checked" : ""}> Выбор Sγ обоснован для конструкции</label><p class="field-note">1,75 — начальное проектное допущение, а не универсальное предписание для всех материалов. Обоснование по п.4.2.4 и таблицам 18–19 ГОСТ. Число повторений максимума задаётся отдельно в режиме работы.</p>`;
  $("#input-fields").append(peak);
  const settings = document.createElement("div");
  settings.innerHTML = settingsFields(inputs);
  $("#input-fields").prepend(settings);
  bindSettings($("#input-fields"));
  $("#inputs-dialog").showModal();
}
$("#open-inputs").onclick = showInputs;
$("#close-inputs").onclick = () => $("#inputs-dialog").close();
$("#inputs-form").onsubmit = (event) => {
  event.preventDefault();
  const form = new FormData(event.target);
  for (const [key, value] of form) {
    if (key in defaults)
      inputs[key] = typeof defaults[key] === "number" ? Number(value) : value;
  }
  inputs.excludeEdges = form.has("excludeEdges");
  inputs.autoTables = form.has("autoTables");
  for (const key of ["autoKA", "autoSurface", "materialConfirmed"])
    inputs[key] = form.has(key);
  inputs.gost = {
    ...inputs.gost,
    faceFactorsConfirmed: form.has("faceFactorsConfirmed"),
    surfaceConfirmed: form.has("surfaceConfirmed"),
    peakProbabilityFactor: Number(form.get("peakProbabilityFactor")),
    peakProbabilityFactorConfirmed: form.has("peakProbabilityFactorConfirmed"),
  };
  inputs.selectedModule = 0;
  if (activeStage === 0) {
    project.power = inputs.power;
    project.speed = inputs.speed;
  }
  $("#inputs-dialog").close();
  run("material");
};
$("#reset-project").onclick = () => {
  inputs = { ...defaults };
  project = projectFromInput(inputs);
  activeStage = 0;
  $("#inputs-dialog").close();
  run();
  toast("Восстановлен исходный вариант У785 / У685.");
};
$$("[data-type]").forEach(
  (el) =>
    (el.onclick = () => {
      inputs.gearType = el.dataset.type;
      inputs.selectedModule = 0;
      inputs.title =
        {
          spur: "Прямозубая передача",
          helical: "Косозубая передача",
          herringbone: "Шевронная передача",
        }[inputs.gearType] + ` · ступень ${activeStage + 1}`;
      inputs.factorsConfirmed = false;
      inputs.gost = { ...inputs.gost, faceFactorsConfirmed: false };
      run();
    }),
);
$("#save-json").onclick = () =>
  download(
    new Blob(
      [
        JSON.stringify(
          { format: "DriveLab", version: 2, engine: "0.4.0", project },
          null,
          2,
        ),
      ],
      { type: "application/json" },
    ),
    "DriveLab-project.json",
  );
$("#import-json").onclick = () => $("#import-file").click();
$("#import-file").onchange = async (event) => {
  try {
    const file = event.target.files[0];
    if (!file) return;
    if (file.size > 2000000) throw Error("Файл слишком большой");
    const saved = JSON.parse(await file.text());
    if (saved.format !== "DriveLab" || ![1, 2].includes(saved.version))
      throw Error("Неподдерживаемая версия проекта");
    project =
      saved.version === 1
        ? projectFromInput(cleanInput(saved.input))
        : cleanProject(saved.project);
    activeStage = 0;
    inputs = cleanInput(project.stages[0].input);
    run();
    toast("Проект загружен.");
  } catch (err) {
    toast("Не удалось открыть JSON: " + err.message);
  }
  event.target.value = "";
};
$("#export-word").onclick = async () => {
  if (!result?.chosen) return;
  const button = $("#export-word");
  button.disabled = true;
  button.textContent = "Готовим отчёт…";
  try {
    const { makeReport } = await import("./report.js");
    const doc = makeReport(result, window.docx);
    const blob = await window.docx.Packer.toBlob(doc);
    download(blob, "DriveLab-report.docx");
    toast("Отчёт Word сохранён. Формулы доступны для редактирования.");
  } catch (error) {
    toast("Ошибка экспорта: " + error.message);
    console.error(error);
  } finally {
    button.disabled = false;
    button.textContent = "↓ Отчёт Word";
  }
};
$("#expand-all").onclick = () => {
  const expand = $$("#trace details").some((el) => !el.open);
  $$("#trace details").forEach((el) => (el.open = expand));
  $("#expand-all").textContent = expand ? "Свернуть все" : "Раскрыть все";
};
$("#play-toggle").onclick = () => {
  if (viewer) {
    viewer.playing = !viewer.playing;
    $("#play-toggle").textContent = viewer.playing ? "Ⅱ" : "▶";
    $("#play-toggle").setAttribute(
      "aria-label",
      viewer.playing ? "Приостановить вращение" : "Включить вращение",
    );
  }
};
$("#time-scale").oninput = (event) => {
  const v = Number(event.target.value) / 1000;
  if (viewer) viewer.scale = v;
  $("#time-output").textContent = fmt(v, 3) + "×";
};
for (const mode of ["front", "iso"])
  $("#view-" + mode).onclick = () => {
    viewer?.view(mode);
    $("#view-front").classList.toggle("active", mode === "front");
    $("#view-iso").classList.toggle("active", mode === "iso");
  };
$("#toggle-lines").onclick = () => {
  if (viewer) {
    viewer.lines.visible = !viewer.lines.visible;
    $("#toggle-lines").setAttribute(
      "aria-pressed",
      String(viewer.lines.visible),
    );
    $("#toggle-lines").classList.toggle("active", viewer.lines.visible);
  }
};
builder = createBuilder({
  defaults,
  getProject: () => project,
  getActive: () => activeStage,
  onChange: (next, index) => {
    project = next;
    activeStage = index;
    inputs = cleanInput(project.stages[index].input);
    run();
  },
  onSelect: (index) => {
    activeStage = index;
    inputs = cleanInput(project.stages[index].input);
    run();
  },
  onExport: async () => {
    if (!assembly || assembly.errors?.length) return;
    const button = $("#assembly-export");
    button.disabled = true;
    button.textContent = "Готовим отчёт…";
    try {
      const { makeAssemblyReport } = await import("./report.js");
      const blob = await window.docx.Packer.toBlob(
        makeAssemblyReport(assembly, window.docx),
      );
      download(blob, "DriveLab-reducer.docx");
      toast("Отчёт по редуктору сохранён.");
    } catch (error) {
      toast("Ошибка экспорта: " + error.message);
    } finally {
      button.disabled = false;
      button.textContent = "↓ Отчёт по редуктору";
    }
  },
});
builder.controls();
workbench = createWorkbench({
  request: (input) =>
    new Promise((resolve, reject) => {
      const id = toolSequence--;
      toolCalls.set(id, { resolve, reject });
      worker.postMessage({ id, type: "tools", input });
    }),
  getProject: () => structuredClone(project),
  getActive: () => activeStage,
  apply: (patch) => {
    inputs = {
      ...inputs,
      ...patch,
      gost: {
        ...inputs.gost,
        faceFactorsConfirmed: false,
        surfaceConfirmed: false,
      },
    };
    run();
    toast("Параметры применены. Пересчитываем редуктор и опоры.");
  },
});
setupShell();
run();
