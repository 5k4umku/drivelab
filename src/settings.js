import { escapeHTML as e, fmt } from "./format.js";
const input = (p, key, label, extra = "") =>
  `<label class="field">${label}<input name="${key}" type="number" min="0" step="any" value="${e(p[key])}" ${extra}></label>`;
const select = (p, key, label, values) =>
  `<label class="field">${label}<select name="${key}">${Object.entries(values)
    .map(
      ([v, text]) =>
        `<option value="${v}" ${String(p[key]) === v ? "selected" : ""}>${text}</option>`,
    )
    .join("")}</select></label>`;
const tick = (p, key, label) =>
  `<label class="checkbox-field"><input type="checkbox" name="${key}" ${p[key] ? "checked" : ""}>${label}</label>`;
const uneven = {
  0: "Равномерный",
  1: "Малая неравномерность",
  2: "Средняя неравномерность",
  3: "Значительная неравномерность",
};
export const regimes = {
  manual: "Вручную: μH и μF",
  0: "0 · постоянный момент",
  I: "I · тяжёлый",
  II: "II · средний равновероятный",
  III: "III · средний нормальный",
  IV: "IV · лёгкий",
  V: "V · особо лёгкий",
};
const materialRows = [
  ["У345", 174, 217, 460, 345, 10],
  ["У395", 187, 229, 480, 360, 11],
  ["У440", 197, 235, 500, 380, 12],
  ["У490", 212, 248, 530, 400, 14],
  ["У540", 223, 262, 550, 420, 16],
  ["У590", 235, 277, 580, 450, 18],
  ["У640", 248, 293, 610, 470, 21],
  ["У685", 262, 311, 640, 500, 24],
  ["У735", 277, 321, 670, 520, 26],
  ["У785", 293, 331, 690, 550, 29],
];
export function settingsFields(p) {
  return `<fieldset><legend>Нагрузка и автоматический выбор</legend><div class="field-grid">${select(p, "loadRegime", "Режим нагружения", regimes)}${select(p, "loadDirection", "Направление нагрузки", { manual: "YA вручную", oneway: "Нереверсивная", reversing: "Реверсивная · симметричный цикл" })}${input(p, "YA", "YA при ручном выборе", 'max="1"')}${select(p, "accuracy", "Степень точности по Т7", { 6: "6", 7: "7", 8: "8", 9: "9" })}</div><p class="field-note">Для симметричного реверса моменты и число циклов на обеих сторонах зуба равны. Ресурс L задаётся для каждой стороны; YA=0,65 для У. Для неравного реверса нужен отдельный расчёт сторон по табл.13 ГОСТ.</p>${tick(p, "autoKA", "Выбирать KA по таблице 21 ГОСТ")}<div class="field-grid">${select(p, "driverClass", "Режим двигателя", uneven)}${select(p, "machineClass", "Режим рабочей машины", uneven)}</div><p class="field-note">KA и типовой спектр 0–V описывают разные свойства нагрузки. Таблица KA применяется вне резонанса; ячейки «и выше» задают нижнюю границу.</p>${select(p, "rootFinish", "Обработка переходной поверхности", {cut: "Нарезание / шлифование · Rz ≤ 40 мкм", polished: "Полирование · улучшенная сталь"})}${tick(p, "autoSurface", "Выбрать YR по обработке корня и ZR по требованиям Т4")}</fieldset>
 <fieldset><legend>Распределение нагрузки по ширине</legend>${select(p, "faceMode", "Как определять KHβ и KFβ", { manual: "Ввести вручную", seminar: "Т5 семинара · по расположению опор", formula: "Формулы ГОСТ · по полному перекосу" })}<p class="field-note">Т5 автоматически определяет симметрию и консоль, учитывает тип опор и интерполирует соседние строки ψbd. Прочерки и выход за диапазон не экстраполируются. Формула ГОСТ требует полного отклонения контактных линий: деформации плюс погрешности изготовления.</p><div class="field-grid">${input(p, "faceDeviation", "Полное fkβ⁰, мкм")}${input(p, "faceHV", "HV менее твёрдого колеса")}${select(p, "torqueSide", "Торец концентрации нагрузки", { input: "Со стороны подвода момента", opposite: "Противоположный" })}</div><p class="field-note">Формула KHβ⁰: прямые и косые зубья, b/d₁≤1,3. HB и HV — разные шкалы: автоматической подмены нет.</p></fieldset>
 <fieldset><legend>Свойства материала</legend>${select(p, "materialMode", "Источник характеристик", { table: "Т1 семинара · колесо на две строки мягче", custom: "Мои характеристики" })}<p class="field-note">Марки сталей задаются выше независимо. Таблица задаёт класс свойств, а не гарантирует его достижимость для любой стали и заготовки. Проверочный профиль ГОСТ сейчас рассчитан на улучшенную сталь У / У.</p><div class="field-grid">${[1, 2].map((i) => `<div class="wide"><b>${i === 1 ? "Шестерня" : "Колесо"}</b></div>${input(p, "hb" + i + "min", "HB минимум")}${input(p, "hb" + i + "max", "HB максимум")}${input(p, "sigmaH" + i, "σHlim, МПа")}${input(p, "sigmaF" + i, "σFlim, МПа")}${input(p, "NHG" + i, "NHG, млн циклов")}${input(p, "yield" + i, "Предел текучести, МПа")}`).join("")}</div><label class="field">Источник характеристик<input name="materialSource" value="${e(p.materialSource)}" maxlength="1000"></label>${tick(p, "materialConfirmed", "Свойства и технология получения подтверждены")}<details><summary>Открыть таблицу Т1 · улучшенная сталь</summary><div class="table-wrap"><table><thead><tr><th>Класс</th><th>HB</th><th>σHlim</th><th>σFlim</th><th>NHG, млн</th></tr></thead><tbody>${materialRows.map(([n, lo, hi, h, f, nh]) => `<tr><td>${n}</td><td>${lo}–${hi}</td><td>${h}</td><td>${f}</td><td>${nh}</td></tr>`).join("")}</tbody></table></div></details></fieldset>`;
}
export function bindSettings(root) {
  root.addEventListener("change", (event) => {
    if (
      ![
        "faceFactorsConfirmed",
        "surfaceConfirmed",
        "peakProbabilityFactorConfirmed",
      ].includes(event.target.name)
    ) {
      for (const key of ["faceFactorsConfirmed", "surfaceConfirmed"]) {
        const el = root.querySelector(`[name="${key}"]`);
        if (el) el.checked = false;
      }
    }
  });
  const lock = () => {
    const value = (k) => root.querySelector(`[name="${k}"]`)?.value;
    const checked = (k) => root.querySelector(`[name="${k}"]`)?.checked;
    const set = (keys, readonly) =>
      keys.forEach((k) => {
        const el = root.querySelector(`[name="${k}"]`);
        if (el) {
          el.readOnly = readonly;
          el.classList.toggle("automatic-field", readonly);
        }
      });
    set(["muH", "muF"], value("loadRegime") !== "manual");
    set(["YA"], value("loadDirection") !== "manual");
    set(["KA"], checked("autoKA"));
    set(["KHbeta", "KFbeta"], value("faceMode") !== "manual");
    set(
      [1, 2].flatMap((i) => [
        "hb" + i + "min",
        "hb" + i + "max",
        "sigmaH" + i,
        "sigmaF" + i,
        "NHG" + i,
        "yield" + i,
      ]),
      value("materialMode") === "table",
    );
  };
  root
    .querySelectorAll('select,input[type="checkbox"]')
    .forEach((el) => el.addEventListener("change", lock));
  lock();
}
export function coefficientPanel(r) {
  const rows = (r.trace || []).filter(
    (s) =>
      s.section.startsWith("0.") ||
      /^(ZE|ZH|Zε|KHv|KFv|KHα|KFα|KHβ|KFβ|KH|KF|g0|Yβ|Yε|ZN\d|YN\d|YFS\d|Yδ\d|YX\d|ZX\d|ZV|KHbeta|KFbeta|KHw)/.test(
        s.title,
      ),
  );
  return `<div class="section-heading"><div><div class="eyebrow">ПРОИСХОЖДЕНИЕ КОЭФФИЦИЕНТОВ</div><h2>Из таблицы — в расчёт</h2><p class="section-note">${rows.length} вычислений и выборов для ступени. Раскройте строку, чтобы проверить формулу и источник.</p></div></div><div class="coefficient-grid">${rows.map((s) => `<details class="coefficient-item"><summary><span>${e(s.title)}</span><b>${fmt(s.value, 4)}</b></summary><p class="equation">${e(s.formula)}</p><p>${e(s.substitution)}</p><small>${e(s.source)}</small></details>`).join("")}</div>`;
}
