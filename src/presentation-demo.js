import { mountReportReader } from "./presentation-report.js";
const stylesheet = new URL("./presentation-demo.css", import.meta.url);

const demos = {
  project: {
    title: "Проект привода",
    actions: [
      ["Ступени", "Собрать многоступенчатый редуктор"],
      ["Двигатель", "Выбрать АИР90L4 или ввести свои данные"],
      ["Валы и опоры", "Проверить реакции и эпюры изгиба"],
    ],
    output: "<p class='feature-demo-chain'>Двигатель → Входной вал → Ступени → Выходной вал</p>",
  },
  geometry: {
    title: "Геометрия и компоновка",
    actions: [
      ["2D-схема", "Переместить венцы и опоры · выгрузить SVG"],
      ["Зацепление", "Прямые, косые, шевронные зубья · внутренняя пара"],
      ["Объёмная модель", "Осмотреть зацепление, силы и разрез"],
    ],
    output: "<p>Положение деталей на 2D-схеме задаёт их положение в 3D.</p>",
  },
  selection: {
    title: "Подбор и точность",
    actions: [
      ["Варианты", "Сравнить размеры, ширину и запас"],
      ["Зубья · Zubil", "Сравнить пары по НОК и отклонению u"],
      ["Точность и допуски", "Степени 6–9 · IT5–IT12 · чувствительность к моменту"],
    ],
    output: "<p>Рабочий момент меняется. Анализ показывает, как меняется запас прочности.</p>",
  },
  verification: {
    title: "Проверка передачи",
    actions: [
      ["Нагрузка", "Задать циклограмму и обратный ход"],
      ["ГОСТ 21354–87", "Проверить контакт, изгиб и пиковую нагрузку"],
      ["Ход расчёта", "Раскрыть формулы, подстановки и источники"],
    ],
    output: "<p>Пример приложения 11. Контакт 764,411 МПа при допускаемом 957,657 МПа. Часть условий требует уточнения.</p>",
  },
  report: {
    title: "Результат и документы",
    actions: [
      ["Проект JSON", "Сохранить настройки и открыть их снова"],
      ["Выгрузка Word", "Сформировать отчёт по результату"],
    ],
    output: `
      <div class="feature-demo-paper">
        <p>Приложение 11 · пример отчёта</p>
        <p><strong>σH = ZE ZH Zε √[Ft KH (u + 1) / (bw d₁ u)]</strong></p>
        <table><thead><tr><th scope="col">Проверка</th><th scope="col">Расчёт, МПа</th><th scope="col">Допуск, МПа</th></tr></thead>
        <tbody><tr><th scope="row">Контакт</th><td>764,411</td><td>957,657</td></tr></tbody></table>
      </div>`,
  },
};

function loadStyles() {
  if (document.querySelector('link[data-feature-demo-style]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = stylesheet.href;
  link.dataset.featureDemoStyle = "";
  document.head.append(link);
}

export function mountFeatureTour(root) {
  const tour = root.querySelector("[data-feature-tour]");
  const screen = tour?.querySelector("[data-feature-screen]");
  if (!screen) return () => {};
  loadStyles();

  const steps = [...tour.querySelectorAll("[data-feature-step]")]
    .filter(step => Object.hasOwn(demos, step.dataset.featureStep));
  const selectors = [...tour.querySelectorAll("[data-feature-select]")];

  const pointer = tour.querySelector("[data-feature-pointer]");
  const pointerHome = document.createComment("feature-pointer");
  if (pointer) {
    pointer.before(pointerHome);
    pointer.setAttribute("aria-hidden", "true");
    pointer.style.pointerEvents = "none";
    screen.append(pointer);
  }

  const panel = document.createElement("div");
  panel.className = "feature-demo-panel";
  screen.prepend(panel);
  const motion = matchMedia("(prefers-reduced-motion: reduce)");
  const events = new AbortController();
  const options = { signal: events.signal };
  const report = mountReportReader(tour, options);
  let activeKey, scrollKey, focusedRow;
  let autoOpened = false;
  let timers = [];
  let frame = 0;

  function clearSequence() {
    timers.forEach(clearTimeout);
    timers = [];
  }

  function positionPointer() {
    if (!pointer || !focusedRow) return;
    const rect = focusedRow.getBoundingClientRect();
    const base = screen.getBoundingClientRect();
    pointer.style.left = Math.min(base.width - 24, rect.right - base.left - 18) + "px";
    pointer.style.top = rect.top - base.top + Math.min(18, rect.height / 2) + "px";
  }

  function show(key, replay = false) {
    if (!Object.hasOwn(demos, key) || (key === activeKey && !replay)) return;
    clearSequence();
    activeKey = key;
    const { title, actions, output } = demos[key];
    panel.innerHTML = `<h3>${title}</h3><ul>${actions.map(([label, value]) =>
      `<li><strong>${label}</strong><span>${value}</span></li>`).join("")}</ul>
      <div class="feature-demo-output">${output}</div>`;
    tour.dataset.featureActive = key;
    for (const button of selectors) {
      button.setAttribute("aria-pressed", String(button.dataset.featureSelect === key));
    }
    const rows = [...panel.querySelectorAll("li"), panel.querySelector(".feature-demo-output")];
    const highlight = (row) => {
      focusedRow?.classList.remove("feature-demo-current");
      focusedRow = row;
      row.classList.add("feature-demo-current");
      if (key === "report" && row === rows[1]) row.classList.add("feature-demo-export-press");
      positionPointer();
    };
    if (pointer) pointer.hidden = motion.matches;
    function openReport() {
      if (key !== "report" || autoOpened || document.hidden) return;
      autoOpened = true;
      report.open();
    }
    if (motion.matches || document.hidden) {
      highlight(rows.at(-1));
      openReport();
    } else {
      highlight(rows[0]);
      timers = rows.slice(1).map((row, index) =>
        setTimeout(() => {
          highlight(row);
          if (row === rows.at(-1)) openReport();
        }, (index + 1) * 520));
    }
  }

  function updateFromViewport() {
    frame = 0;
    const marker = innerHeight * .55;
    const visible = steps.map(step => ({step, box: step.getBoundingClientRect()}))
      .filter(({box}) => box.bottom > 0 && box.top < innerHeight);
    const current = visible.reduce((best, item) => {
      const distance = ({box}) => Math.max(box.top - marker, marker - box.bottom, 0);
      return !best || distance(item) < distance(best) ? item : best;
    }, null)?.step.dataset.featureStep;
    if (current && current !== scrollKey) show(current, true);
    scrollKey = current;
    positionPointer();
  }
  function queueViewportUpdate() {
    if (!frame) frame = requestAnimationFrame(updateFromViewport);
  }

  addEventListener("scroll", queueViewportUpdate, { ...options, passive: true });
  addEventListener("resize", queueViewportUpdate, options);
  motion.addEventListener("change", () => show(activeKey, true), options);
  document.addEventListener("visibilitychange", () => show(activeKey, true), options);
  for (const button of selectors) {
    button.addEventListener("click", () => show(button.dataset.featureSelect, true), options);
  }
  show(steps[0]?.dataset.featureStep || "project");
  queueViewportUpdate();
  return () => {
    events.abort();
    report.cleanup();
    clearSequence();
    cancelAnimationFrame(frame);
    panel.remove();
    delete tour.dataset.featureActive;
    for (const button of selectors) button.removeAttribute("aria-pressed");
    if (pointer) {
      pointerHome.replaceWith(pointer);
      pointer.hidden = true;
    }
  };
}

