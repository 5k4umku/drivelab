import { fmt, escapeHTML as e } from "./format.js";
import { AssemblyViewer } from "./assembly-viewer.js";

const kinds = {
  spur: "Прямозубая",
  helical: "Косозубая",
  herringbone: "Шевронная",
};
const layouts = {
  centered: "Венцы между опорами",
  offset: "Между опорами со смещением",
  "overhung-left": "Венцы левее обеих опор",
  "overhung-right": "Венцы правее обеих опор",
  manual: "Координаты опор вручную",
};
export const shaftDefault = (layout = "centered") => ({
  layout,
  clearance: 35,
  span: 80,
  zA: -50,
  zB: 50,
  diameter: 20,
  locating: "A",
  bearing: "ball",
});
export function projectFromInput(input) {
  return {
    name: "Мой редуктор",
    power: input.power,
    speed: input.speed,
    ratioTolerance: 1,
    stages: [
      { input: structuredClone(input), angle: 0, axial: 0, hand: "right" },
    ],
    shafts: [shaftDefault("overhung-right"), shaftDefault("overhung-left")],
  };
}
export function newStage(defaults) {
  const input = {
    ...structuredClone(defaults),
    ratio: 3,
    modules: "1 1.25 1.5 2 2.5 3 4 5 6 8 10",
    aOverride: 0,
    selectedModule: 0,
    factorsConfirmed: false,
    faceMode: "seminar",
    loadRegime: "II",
    loadDirection: "oneway",
    autoKA: true,
  };
  return { input, angle: 0, axial: null, hand: "right" };
}
const options = (values, selected) =>
  Object.entries(values)
    .map(
      ([v, label]) =>
        `<option value="${e(v)}" ${String(selected) === v ? "selected" : ""}>${e(label)}</option>`,
    )
    .join("");
const field = (label, key, value, extra = "") =>
  `<label class="builder-field">${e(label)}<input data-key="${e(key)}" value="${value === null ? "" : e(value)}" ${extra}></label>`;
const select = (label, key, value, choices) =>
  `<label class="builder-field">${e(label)}<select data-key="${e(key)}">${options(choices, value)}</select></label>`;

export function createBuilder({
  defaults,
  getProject,
  getActive,
  onChange,
  onSelect,
  onExport,
}) {
  let viewer, latest;
  const root = document.querySelector("#constructor");
  root.innerHTML = `<div class="page-heading"><div><div class="eyebrow">СВОБОДНАЯ КОМПОНОВКА</div><h1>Конструктор редуктора<span>.</span></h1><p>Ступени, валы и опоры в одной расчётной модели.</p></div><button class="outline" id="assembly-export" disabled>↓ Отчёт по редуктору</button></div>
  <div class="builder-toolbar"><span>Начать с шаблона</span><button data-template="1">1 ступень</button><button data-template="2">2 ступени</button><button data-template="3">3 ступени</button><button data-template="seminar">Семинар №11</button></div>
  <div class="builder-global" id="builder-global"></div>
  <div id="assembly-error" class="error-banner" hidden role="alert"></div>
  <div id="assembly-metrics" class="metrics"></div>
  <div class="assembly-scene viewer-card"><div class="viewer-top"><span><i></i> КОМПОНОВКА · ПАРАЛЛЕЛЬНЫЕ ВАЛЫ</span><div><button class="viewer-button" id="assembly-front">Спереди</button><button class="viewer-button active" id="assembly-iso">3D</button><button class="viewer-button active" id="assembly-envelope" aria-pressed="true">Габариты</button></div></div><div id="assembly-view" aria-label="Трёхмерная компоновка редуктора"><div class="model-loading">Собираем редуктор…</div></div><div class="playback"><button id="assembly-play" class="play" aria-label="Приостановить редуктор">Ⅱ</button><label for="assembly-time">Масштаб времени</label><input id="assembly-time" type="range" min="0" max="100" value="12"><output id="assembly-time-value">0,012×</output></div><p class="model-footnote">Размеры венцов и положение опор связаны с расчётом. Кольца обозначают опоры; золотая опора фиксирует вал по оси. Контур показывает габариты, а не готовый корпус.</p></div>
  <div class="builder-section-title"><div><h2>Ступени</h2><p>Каждая следующая получает мощность и фактическую частоту предыдущей.</p></div><button class="primary" id="add-stage">+ Добавить ступень</button></div>
  <div id="stage-flow" aria-label="Поток мощности"></div><div id="stage-editor" class="builder-cards"></div>
  <div class="builder-section-title"><div><h2>Валы и опоры</h2><p>Ось Z идёт вдоль валов. Для каждого вала — две радиальные опоры и одна фиксирующая осевая.</p></div></div><div id="shaft-editor" class="builder-cards"></div>
  <div class="builder-section-title"><div><h2>Реакции и изгибающие моменты</h2><p>Номинальные силы зацепления. Пуск, вес деталей и внешние силы на концах валов сюда не включены.</p></div></div><div id="shaft-results"></div>
  <div class="builder-section-title"><h2>Проверки компоновки</h2></div><div id="assembly-checks" class="checks-list"></div>
  <p class="builder-scope">Последовательные внешние цилиндрические зацепления на параллельных валах без смещения профиля. Подшипники, прочность и жёсткость валов требуют отдельного расчёта. Число ступеней не привязано к семинарскому шаблону.</p>`;
  function invalidateFactors(p) {
    for (const s of p.stages) {
      s.input.factorsConfirmed = false;
      s.input.gost = { ...s.input.gost, faceFactorsConfirmed: false };
    }
  }
  const changed = (p, active = getActive(), reset = true) => {
    if (reset) invalidateFactors(p);
    onChange(p, active);
  };
  root.querySelector("#add-stage").onclick = () => {
    const p = structuredClone(getProject());
    p.stages.push(newStage(defaults));
    p.shafts.push(shaftDefault());
    changed(p, p.stages.length - 1);
  };
  root.querySelectorAll("[data-template]").forEach(
    (button) =>
      (button.onclick = () => {
        const p = projectFromInput(defaults),
          count = button.dataset.template;
        if (count !== "seminar") {
          p.name = `Редуктор · ${count} ${count === "1" ? "ступень" : "ступени"}`;
          p.stages = Array.from({ length: Number(count) }, () =>
            newStage(defaults),
          );
          p.shafts = Array.from({ length: Number(count) + 1 }, () =>
            shaftDefault(),
          );
        }
        changed(p, 0, count !== "seminar");
      }),
  );
  root.querySelector("#assembly-export").onclick = onExport;
  for (const mode of ["front", "iso"])
    root.querySelector("#assembly-" + mode).onclick = () => {
      viewer?.view(mode);
      for (const key of ["front", "iso"])
        root
          .querySelector("#assembly-" + key)
          .classList.toggle("active", mode === key);
    };
  root.querySelector("#assembly-envelope").onclick = () => {
    if (!viewer?.envelope) return;
    viewer.showEnvelope = !viewer.envelope.visible;
    viewer.envelope.visible = viewer.showEnvelope;
    root
      .querySelector("#assembly-envelope")
      .setAttribute("aria-pressed", String(viewer.showEnvelope));
    root
      .querySelector("#assembly-envelope")
      .classList.toggle("active", viewer.showEnvelope);
  };
  root.querySelector("#assembly-play").onclick = () => {
    if (!viewer) return;
    viewer.playing = !viewer.playing;
    syncPlay();
  };
  root.querySelector("#assembly-time").oninput = (event) => {
    if (viewer) viewer.scale = Number(event.target.value) / 1000;
    root.querySelector("#assembly-time-value").textContent =
      fmt(Number(event.target.value) / 1000, 3) + "×";
  };
  function syncPlay() {
    root.querySelector("#assembly-play").textContent = viewer.playing
      ? "Ⅱ"
      : "▶";
    root
      .querySelector("#assembly-play")
      .setAttribute(
        "aria-label",
        viewer.playing ? "Приостановить редуктор" : "Включить редуктор",
      );
  }
  function controls() {
    const p = getProject(),
      active = getActive();
    const openShafts = new Set(
      [...root.querySelectorAll("[data-shaft][open]")].map((el) =>
        Number(el.dataset.shaft),
      ),
    );
    root.querySelector("#builder-global").innerHTML =
      field("Название проекта", "name", p.name, 'type="text" maxlength="150"') +
      field(
        "Мощность на входе, кВт",
        "power",
        p.power,
        'type="number" min="0.001" step="any"',
      ) +
      field(
        "Частота на входе, мин⁻¹",
        "speed",
        p.speed,
        'type="number" min="0.001" step="any"',
      ) +
      field(
        "Допуск общего u, %",
        "ratioTolerance",
        p.ratioTolerance ?? 1,
        'type="number" min="0" max="100" step="any"',
      );
    root.querySelectorAll("#builder-global [data-key]").forEach(
      (el) =>
        (el.onchange = () => {
          const copy = structuredClone(getProject());
          copy[el.dataset.key] =
            el.dataset.key === "name" ? el.value : Number(el.value);
          changed(copy, active, false);
        }),
    );
    root.querySelector("#stage-editor").innerHTML = p.stages
      .map(
        (
          s,
          i,
        ) => `<details class="builder-card ${i === active ? "selected" : ""}" data-stage="${i}" ${i === active ? "open" : ""}><summary><span class="stage-number">${i + 1}</span><span>${kinds[s.input.gearType] || "Ступень"}<small>Вал ${i + 1} → вал ${i + 2} · u = ${fmt(s.input.ratio)}</small></span><span class="stage-status">${latest?.stages[i]?.result?.status === "fail" ? "Есть замечания" : "Параметры ↗"}</span></summary><div class="builder-card-body"><div class="builder-fields">
    ${select("Тип зубьев", "gearType", s.input.gearType, kinds)}${field("Передаточное число u", "ratio", s.input.ratio, 'type="number" min="1.01" max="20" step="any"')}${field("КПД ступени η", "efficiency", s.input.efficiency, 'type="number" min="0.01" max="1" step="0.001"')}${field("Направление в плоскости XY, °", "angle", s.angle, 'type="number" step="any"')}${field("Положение по Z, мм (пусто — авто)", "axial", s.axial, 'type="number" step="any" placeholder="Автоматически"')}${select("Направление зуба шестерни", "hand", s.hand, { right: "Правое", left: "Левое" })}${field("Межосевое aw, мм (0 — подбор)", "aOverride", s.input.aOverride, 'type="number" min="0" step="any"')}${field("Коэффициент ширины ψbd", "psiBd", s.input.psiBd, 'type="number" min="0.01" max="2" step="any"')}${select("Выбор коэффициентов по ширине", "faceMode", s.input.faceMode ?? "manual", { manual: "Вручную", seminar: "Автоматически по Т5", formula: "По формуле ГОСТ (настройки ступени)" })}${field("KHβ по ширине", "KHbeta", s.input.KHbeta, 'type="number" min="1" step="any"')}${field("KFβ по ширине", "KFbeta", s.input.KFbeta, 'type="number" min="1" step="any"')}
    </div><p class="field-note">Угол задаёт направление от оси шестерни к оси колеса. Автоматическое Z разводит соседние венцы с зазором 20 мм. При выборе Т5 коэффициенты пересчитываются по расположению венцов и опор. Формула ГОСТ настраивается в исходных данных ступени.</p><div class="builder-card-actions"><button class="outline" data-detail="${i}">Расчёт ступени ${i + 1} ↗</button><button class="quiet" data-up="${i}" ${i === 0 ? "disabled" : ""} aria-label="Переместить ступень ${i + 1} выше">↑</button><button class="quiet" data-down="${i}" ${i === p.stages.length - 1 ? "disabled" : ""} aria-label="Переместить ступень ${i + 1} ниже">↓</button><button class="quiet danger" data-remove="${i}" ${p.stages.length === 1 ? "disabled" : ""}>Удалить ступень ${i + 1}</button></div></div></details>`,
      )
      .join("");
    root.querySelectorAll("[data-stage] [data-key]").forEach(
      (el) =>
        (el.onchange = () => {
          const p = structuredClone(getProject()),
            i = Number(el.closest("[data-stage]").dataset.stage),
            key = el.dataset.key,
            s = p.stages[i];
          if (["angle", "axial", "hand"].includes(key))
            s[key] =
              key === "hand"
                ? el.value
                : key === "axial" && el.value.trim() === ""
                  ? null
                  : Number(el.value);
          else {
            s.input[key] = ["gearType", "faceMode"].includes(key)
              ? el.value
              : Number(el.value);
            s.input.selectedModule = 0;
          }
          changed(p, i);
        }),
    );
    root.querySelectorAll("[data-detail]").forEach(
      (el) =>
        (el.onclick = () => {
          onSelect(Number(el.dataset.detail));
          document
            .querySelector("#overview")
            .scrollIntoView({ behavior: "smooth" });
        }),
    );
    for (const action of ["remove", "up", "down"])
      root.querySelectorAll(`[data-${action}]`).forEach(
        (el) =>
          (el.onclick = () => {
            const p = structuredClone(getProject()),
              i = Number(el.dataset[action]);
            if (action === "remove") {
              p.stages.splice(i, 1);
              p.shafts.splice(i + 1, 1);
              changed(p, Math.min(i, p.stages.length - 1));
            } else {
              const j = i + (action === "up" ? -1 : 1);
              [p.stages[i], p.stages[j]] = [p.stages[j], p.stages[i]];
              changed(p, j);
            }
          }),
      );
    root.querySelector("#shaft-editor").innerHTML = p.shafts
      .map(
        (s, i) =>
          `<details class="builder-card" data-shaft="${i}" ${openShafts.has(i) ? "open" : ""}><summary><span class="shaft-number">${i + 1}</span><span>Вал ${i + 1}<small>${i === 0 ? "Входной" : i === p.shafts.length - 1 ? "Выходной" : "Промежуточный"} · ${layouts[s.layout]}</small></span><span>Опоры ↗</span></summary><div class="builder-card-body"><div class="builder-fields">${select("Расположение опор", "layout", s.layout, layouts)}${field("Диаметр вала для компоновки, мм", "diameter", s.diameter, 'type="number" min="1" step="any"')}${field("Зазор от венца до опоры, мм", "clearance", s.clearance, 'type="number" min="5" step="any"')}${field("Пролёт консольных опор / смещение, мм", "span", s.span, 'type="number" min="1" step="any"')}${field("Координата опоры A, мм", "zA", s.zA, `type="number" step="any" ${s.layout !== "manual" ? "disabled" : ""}`)}${field("Координата опоры B, мм", "zB", s.zB, `type="number" step="any" ${s.layout !== "manual" ? "disabled" : ""}`)}${select("Фиксирующая осевая опора", "locating", s.locating, { A: "Опора A", B: "Опора B" })}${select("Условное обозначение опор", "bearing", s.bearing, { ball: "Шариковые", roller: "Роликовые" })}</div><p class="field-note">Диаметр задан для проверки компоновки и не означает подтверждённую прочность. Тип опоры — обозначение, а не выбор конкретного подшипника.</p></div></details>`,
      )
      .join("");
    root.querySelectorAll("[data-shaft] [data-key]").forEach(
      (el) =>
        (el.onchange = () => {
          const p = structuredClone(getProject()),
            i = Number(el.closest("[data-shaft]").dataset.shaft),
            key = el.dataset.key;
          if (key === "layout" && el.value === "manual" && latest?.shafts[i]) {
            p.shafts[i].zA = latest.shafts[i].A.z;
            p.shafts[i].zB = latest.shafts[i].B.z;
          }
          p.shafts[i][key] = ["layout", "locating", "bearing"].includes(key)
            ? el.value
            : Number(el.value);
          changed(p);
        }),
    );
  }
  function diagram(shaft) {
    const d = shaft.diagram,
      lo = d[0].z,
      hi = d[d.length - 1].z,
      max = Math.max(1, shaft.maxBending);
    const points = d
      .map(
        (v) =>
          `${20 + (260 * (v.z - lo)) / (hi - lo || 1)},${92 - (65 * v.M) / max}`,
      )
      .join(" ");
    return `<svg class="bending-plot" viewBox="0 0 300 118" role="img" aria-label="Эпюра суммарного изгибающего момента вала ${shaft.index + 1}"><path d="M20 15 V92 H280" fill="none" stroke="#b9ccc9"/><polyline points="${points}" fill="none" stroke="#13765d" stroke-width="2.5"/><text x="20" y="112">${fmt(lo, 1)} мм</text><text x="215" y="112">${fmt(hi, 1)} мм</text><text x="24" y="15">Mmax = ${fmt(shaft.maxBending, 2)} Н·м</text></svg>`;
  }
  return {
    controls,
    busy() {
      root.classList.add("builder-busy");
      root.querySelector("#assembly-export").disabled = true;
    },
    error(message) {
      root.classList.remove("builder-busy");
      root.classList.add("builder-invalid");
      root.querySelector("#assembly-error").hidden = false;
      root.querySelector("#assembly-error").textContent = message;
      root.querySelector("#assembly-export").disabled = true;
      controls();
    },
    render(data) {
      latest = data;
      root.classList.remove("builder-busy", "builder-invalid");
      root.querySelector("#assembly-error").hidden = true;
      root.querySelector("#assembly-export").disabled = false;
      controls();
      root.querySelector("#assembly-metrics").innerHTML = [
        [
          "Ступеней / валов",
          `${data.stages.length} / ${data.shafts.length}`,
          "",
          "Связанные исходные данные",
        ],
        [
          "Общее u",
          fmt(data.totalRatio, 4),
          "",
          `Задано ${fmt(data.targetRatio, 3)} · δu ${fmt(data.ratioError, 2)} %`,
        ],
        [
          "Частота на выходе",
          fmt(data.outputSpeed, 2),
          "мин⁻¹",
          `КПД ${fmt(data.efficiency * 100, 2)} %`,
        ],
        [
          "Момент на выходе",
          fmt(data.outputTorque, 2),
          "Н·м",
          `Мощность ${fmt(data.outputPower, 3)} кВт`,
        ],
      ]
        .map(
          ([a, b, c, d]) =>
            `<div class="metric"><label>${a}</label><strong>${b}<span>${c}</span></strong><small>${d}</small></div>`,
        )
        .join("");
      root.querySelector("#stage-flow").innerHTML =
        `<span class="flow-end">Вход<br><b>${fmt(data.project.speed, 0)} мин⁻¹</b></span>` +
        data.stages
          .map(
            (s, i) =>
              `<button class="flow-stage ${i === getActive() ? "selected" : ""}" data-flow="${i}"><small>Ступень ${i + 1}</small><b>${s.result.chosen.z1} : ${s.result.chosen.z2}</b><span>${fmt(s.outputSpeed, 2)} мин⁻¹ →</span></button>`,
          )
          .join("") +
        `<span class="flow-end">Выход<br><b>${fmt(data.outputTorque, 1)} Н·м</b></span>`;
      root
        .querySelectorAll("[data-flow]")
        .forEach(
          (el) => (el.onclick = () => onSelect(Number(el.dataset.flow))),
        );
      root.querySelector("#shaft-results").innerHTML = data.shafts
        .map(
          (s) =>
            `<article class="shaft-result"><h3>Вал ${s.index + 1} <small>${fmt(s.torque, 2)} Н·м · ${fmt(s.signedSpeed, 2)} мин⁻¹</small></h3><div class="shaft-result-grid"><div class="table-wrap"><table><thead><tr><th>Опора</th><th>Z, мм</th><th>Rx, Н</th><th>Ry, Н</th><th>Rz, Н</th><th>Rrad, Н</th></tr></thead><tbody>${["A", "B"].map((k) => `<tr><td>${k}${k === s.locating ? " · фикс." : ""}</td><td>${fmt(s[k].z, 2)}</td>${s[k].vector.map((v) => `<td>${fmt(v, 2)}</td>`).join("")}<td>${fmt(s[k].radial, 2)}</td></tr>`).join("")}</tbody></table></div>${diagram(s)}</div></article>`,
        )
        .join("");
      root.querySelector("#assembly-checks").innerHTML = data.checks
        .map(
          (c) =>
            `<article class="check"><span class="check-symbol ${c.status}">${c.status === "pass" ? "✓" : c.status === "fail" ? "×" : "!"}</span><div><h3>${e(c.title)}</h3><p>${e(c.detail)}</p></div></article>`,
        )
        .join("");
      try {
        if (!viewer)
          viewer = new AssemblyViewer(root.querySelector("#assembly-view"));
        viewer.update(data);
        syncPlay();
      } catch (error) {
        root.querySelector("#assembly-view").textContent =
          "WebGL недоступен. Расчёт компоновки и отчёт остаются доступны.";
        console.error(error);
      }
    },
  };
}
