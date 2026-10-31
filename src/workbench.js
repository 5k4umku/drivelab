import { fmt, escapeHTML as e } from "./format.js";

export function createWorkbench({ request, getProject, getActive, apply }) {
  const root = document.querySelector("#selection");
  root.innerHTML = `<div class="page-heading"><div><div class="eyebrow">ПОИСК И ОБОСНОВАНИЕ РЕШЕНИЯ</div><h1>Подбор и точность<span>.</span></h1><p>Сначала сравните варианты, затем примените подходящий к проекту.</p></div></div>
  <div class="tool-tabs" role="group" aria-label="Инструменты подбора"><button data-tool="recommend" class="active">Помощник</button><button data-tool="teeth">Зубья · Zubil</button><button data-tool="precision">Точность и допуски</button></div>
  <div id="tool-error" role="alert" hidden class="error-banner"></div>
  <div data-tool-page="recommend"><div class="assistant-intro"><div><span class="eyebrow">ВЫБРАННАЯ СТУПЕНЬ</span><h2 id="assistant-stage">Загрузка проекта…</h2><p>Подбор учитывает опоры и последующие ступени. Материал и нагрузка остаются условиями проекта.</p></div><button class="primary" id="auto-search" disabled>Найти варианты ↗</button></div><div id="recommendations" class="recommendations"></div><div id="search-results"></div>
  <article class="tool-card"><div class="section-heading"><div><h2>Насколько решение чувствительно к нагрузке</h2><p>Три сценария при неизменной геометрии.</p></div><label class="compact-field">Рабочий момент, ± %<input id="load-range" type="number" min="0" max="50" step="1" value="10"></label></div><div id="sensitivity"></div></article></div>
  <div data-tool-page="teeth" hidden><article class="tool-card"><div class="eyebrow">АЛГОРИТМ ИЗ ВАШЕГО ZUBIL.HTML</div><h2>Числа зубьев без случайного округления</h2><p>Для каждой суммы проверяем оба соседних целых числа. В допуске выбираем максимальный НОК.</p><form id="zubil-form" class="tool-form"><label>Сумма зубьев от<input name="low" type="number" min="2" max="100000" value="280" step="any" required></label><label>до<input name="high" type="number" min="2" max="100000" value="320" step="any" required></label><label>Заданное u<input name="ratio" type="number" min="1" value="6.3" step="any" required></label><label>Допуск, %<input name="tolerance" type="number" min="0" max="100" value="1" step="any" required></label><button class="primary">Подобрать зубья</button></form><div id="zubil-results"></div><p class="field-note">Метод Павла Зарубова, независимо перенесён на Python. НОК — период повторения контакта, а не оценка прочности. <a href="https://github.com/5k4umku/drivelab/blob/main/docs/attachments-and-selection.md" target="_blank" rel="noreferrer">Разбор алгоритма ↗</a></p></article></div>
  <div data-tool-page="precision" hidden><article class="tool-card"><h2>Степень точности зубчатого венца</h2><p>Одна геометрия, разные fpb и динамическая нагрузка. Сравнение 6–9 по Т7; за границами таблицы расчёт блокируется.</p><div id="grade-results"></div></article><article class="tool-card"><h2>Квалитет линейного размера</h2><p>Отдельный расчёт IT5–IT12 по ГОСТ 25346–2013. Пример полей H/h, не назначение посадки подшипника.</p><form id="fit-form" class="tool-form"><label>Диаметр, мм<input name="diameter" type="number" min="0.01" max="500" step="any" value="40" required></label><label>Отверстие H<select name="hole_grade">${Array.from({ length: 8 }, (_, i) => `<option ${i === 2 ? "selected" : ""}>${i + 5}</option>`).join("")}</select></label><label>Вал h<select name="shaft_grade">${Array.from({ length: 8 }, (_, i) => `<option ${i === 1 ? "selected" : ""}>${i + 5}</option>`).join("")}</select></label><button class="primary">Рассчитать допуски</button></form><div id="fit-results"></div></article></div>`;
  let revision = 0,
    ready = false;
  const q = (s) => root.querySelector(s);
  const numeric = (form) =>
    Object.fromEntries([...new FormData(form)].map(([k, v]) => [k, Number(v)]));
  async function execute(action, args, render) {
    const stamp = revision,
      button = action === "search" ? q("#auto-search") : null;
    q("#tool-error").hidden = true;
    if (button) {
      button.disabled = true;
      button.textContent = "Сравниваем варианты…";
    }
    try {
      const result = await request({ action, ...args });
      if (stamp === revision) render(result);
    } catch (error) {
      if (stamp === revision) {
        q("#tool-error").hidden = false;
        q("#tool-error").textContent = error.message;
      }
    } finally {
      if (button) {
        button.disabled = !ready;
        button.textContent = "Найти варианты ↗";
      }
    }
  }
  root.querySelectorAll("[data-tool]").forEach(
    (button) =>
      (button.onclick = () => {
        root
          .querySelectorAll("[data-tool]")
          .forEach((b) => b.classList.toggle("active", b === button));
        root
          .querySelectorAll("[data-tool-page]")
          .forEach(
            (p) => (p.hidden = p.dataset.toolPage !== button.dataset.tool),
          );
      }),
  );
  function renderAnalysis(data) {
    q("#recommendations").innerHTML = data.tips
      .map(
        (t) =>
          `<article class="recommendation ${e(t.status)}"><span class="recommendation-mark">${t.status === "fail" ? "!" : t.status === "pass" ? "✓" : "↗"}</span><div><h3>${e(t.title)}</h3><p>${e(t.detail)}</p><small>${e(t.source)}</small></div></article>`,
      )
      .join("");
    q("#grade-results").innerHTML =
      `<div class="grade-grid">${data.grades.map((g) => `<div class="grade-card"><span>Степень ${g.grade}</span><strong>${fmt(g.margin, 3)}</strong><small>минимальный запас</small><p>${g.available ? `σH ${fmt(g.h, 1)} МПа` : e(g.reason)}</p><button class="outline" data-grade="${g.grade}" ${g.available ? "" : "disabled"}>Применить ${g.grade}-ю</button></div>`).join("") || '<p class="empty-state">Сравнение недоступно: выбранная ступень вне реализованной области прочности.</p>'}</div>`;
    root
      .querySelectorAll("[data-grade]")
      .forEach(
        (b) =>
          (b.onclick = () =>
            apply({ accuracy: Number(b.dataset.grade), autoTables: true })),
      );
    const max = Math.max(...data.scenarios.map((s) => s.h || 0), 1);
    q("#sensitivity").innerHTML =
      `<div class="scenario-grid">${data.scenarios.map((s) => `<div class="scenario"><span>${e(s.label)}</span><strong>${fmt(s.h, 1)} <small>МПа</small></strong><div class="scenario-track"><i style="width:${((s.h || 0) / max) * 100}%"></i></div><p>T₁ ${fmt(s.torque, 2)} Н·м<br>Запас ${fmt(s.margin, 3)}</p></div>`).join("") || '<p class="empty-state">Для анализа нужен доступный проверочный расчёт прочности.</p>'}</div><p class="field-note">${e(data.note)}</p>`;
  }
  function analyze() {
    if (ready)
      execute(
        "inspect",
        {
          project: getProject(),
          index: getActive(),
          loadPercent: Number(q("#load-range").value),
        },
        renderAnalysis,
      );
  }
  q("#load-range").onchange = analyze;
  q("#auto-search").onclick = () =>
    execute("search", { project: getProject(), index: getActive() }, (data) => {
      q("#search-results").innerHTML =
        `<article class="tool-card"><div class="eyebrow">ПРОВЕРЕНО ${data.count} КОМБИНАЦИИ</div><h2>${data.accepted ? `${data.accepted} вариантов прошли численные проверки` : "В заданной области подходящих вариантов нет"}</h2><p>${e(data.note)}</p><div class="table-wrap"><table><thead><tr><th>aw / b, мм</th><th>mn · z₁/z₂</th><th>Точность</th><th>δu, %</th><th>Мин. запас</th><th>Результат</th></tr></thead><tbody>${data.rows.map((r, i) => `<tr><td>${fmt(r.a)} / ${fmt(r.b)}</td><td>${fmt(r.m)} · ${r.z1 ?? "—"}/${r.z2 ?? "—"}</td><td>${r.patch.accuracy}</td><td>${fmt(r.errorPct, 3)}</td><td>${fmt(r.margin, 3)}</td><td>${r.eligible ? `<button class="primary" data-candidate="${i}">Применить</button><small class="pending-note">Уточнить условий: ${r.pending}</small>` : `<span class="rejection">${e(r.reason || "Запас меньше 1")}</span>`}</td></tr>`).join("")}</tbody></table></div></article>`;
      q("#search-results")
        .querySelectorAll("[data-candidate]")
        .forEach(
          (b) =>
            (b.onclick = () =>
              apply(data.rows[Number(b.dataset.candidate)].patch)),
        );
    });
  q("#zubil-form").onsubmit = (event) => {
    event.preventDefault();
    execute("zubil", { args: numeric(event.target) }, (data) => {
      const b = data.best;
      q("#zubil-results").innerHTML =
        `<div class="zubil-best ${data.withinTolerance ? "" : "outside"}"><span>${data.withinTolerance ? "Максимальный НОК в допуске" : "В допуске нет решений · ближайшая пара"}</span><strong>${b ? `${b.z1} : ${b.z2}` : "Нет пары"}</strong><p>${b ? `НОК ${b.lcm} · ${b.turns} оборотов до повторения · δu ${fmt(b.errorPct, 4)} %` : ""}</p><small>${e(data.note)}</small></div><div class="table-wrap bounded-table"><table><thead><tr><th>zΣ</th><th>z₁</th><th>z₂</th><th>НОД</th><th>НОК</th><th>uф</th><th>δu, %</th></tr></thead><tbody>${data.pairs
          .slice(0, 500)
          .map(
            (p) =>
              `<tr class="${b && p.z1 === b.z1 && p.z2 === b.z2 ? "is-selected" : ""}"><td>${p.total}</td><td>${p.z1}</td><td>${p.z2}</td><td>${p.gcd}</td><td>${p.lcm}</td><td>${fmt(p.u, 5)}</td><td>${fmt(p.errorPct, 4)}</td></tr>`,
          )
          .join(
            "",
          )}</tbody></table></div><p class="field-note">Всего ${data.count} пар; показано до 500. Для инженерного применения включите стратегию Zubil в параметрах ступени: она использует допустимую геометрию текущего проекта.</p><button id="use-zubil" class="outline">Использовать стратегию Zubil в проекте</button>`;
      q("#use-zubil").onclick = () =>
        apply({ selectionPolicy: "zubil", selectedModule: 0 });
    });
  };
  q("#fit-form").onsubmit = (event) => {
    event.preventDefault();
    execute("fit", { args: numeric(event.target) }, (data) => {
      q("#fit-results").innerHTML =
        `<div class="fit-diagram"><div><span>Отверстие H${data.holeGrade}</span><strong>${fmt(data.holeMin, 4)}…${fmt(data.holeMax, 4)} мм</strong><i class="hole-band" style="width:${(data.holeTolerance / (data.holeTolerance + data.shaftTolerance)) * 100}%"></i></div><div><span>Вал h${data.shaftGrade}</span><strong>${fmt(data.shaftMin, 4)}…${fmt(data.shaftMax, 4)} мм</strong><i class="shaft-band" style="width:${(data.shaftTolerance / (data.holeTolerance + data.shaftTolerance)) * 100}%"></i></div></div><p>Зазор: <b>0…${fmt(data.gapMax, 4)} мм</b>. Допуски: отверстие ${data.holeTolerance} мкм, вал ${data.shaftTolerance} мкм.</p><div class="it-grid">${data.rows.map((r) => `<div><span>IT${r.grade}</span><b>${r.microns} мкм</b></div>`).join("")}</div><p class="field-note">${e(data.note)} <a href="${e(data.source)}" target="_blank" rel="noreferrer">Таблица 1 ГОСТ ↗</a></p>`;
    });
  };
  return {
    invalidate() {
      revision++;
      ready = false;
      q("#auto-search").disabled = true;
      q("#grade-results").inert = true;
      q("#search-results").replaceChildren();
      root.classList.add("stale-analysis");
    },
    update(result) {
      revision++;
      ready = true;
      root.classList.remove("stale-analysis");
      q("#grade-results").inert = false;
      q("#assistant-stage").textContent =
        `Ступень ${getActive() + 1} · ${result.chosen?.z1 ?? "—"} : ${result.chosen?.z2 ?? "—"}`;
      q("#auto-search").disabled = false;
      analyze();
    },
  };
}
