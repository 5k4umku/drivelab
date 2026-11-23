// Навигация и оформление не меняют инженерные данные проекта.
export function setupShell() {
  const labels = {
    constructor: "Модель",
    overview: "Ступень",
    selection: "Подбор",
    variants: "Варианты",
    checks: "Проверки",
    coefficients: "Коэффициенты",
    calculation: "Ход расчёта",
    method: "Методика",
  };
  const select = document.querySelector("#theme-select");
  function theme(value) {
    document.documentElement.dataset.theme =
      value === "system"
        ? matchMedia("(prefers-color-scheme: dark)").matches
          ? "dark"
          : "light"
        : value;
    try {
      localStorage.setItem("drivelab-theme", value);
    } catch {}
    document.querySelector('meta[name="theme-color"]').content =
      document.documentElement.dataset.theme === "dark" ? "#0d141e" : "#f1f4f8";
    document.dispatchEvent(new CustomEvent("drivelab-theme"));
  }
  let preference = "system";
  try {
    preference = localStorage.getItem("drivelab-theme") || "system";
  } catch {}
  if (!["system", "light", "dark"].includes(preference)) preference = "system";
  select.value = preference;
  theme(preference);
  select.onchange = () => theme(select.value);
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (select.value === "system") theme("system");
  });
  const menus = [...document.querySelectorAll(".instrument-header details")];
  function closeMenus() {
    menus.forEach((menu) => { menu.open = false; });
  }
  document.addEventListener("click", (event) => {
    menus.forEach((menu) => { if (!menu.contains(event.target)) menu.open = false; });
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      const open = menus.find((menu) => menu.open);
      open?.querySelector("summary").focus();
      closeMenus();
    }
  });
  function route() {
    const assemblyChecks = location.hash === "#assembly-checks";
    const id = assemblyChecks ? "constructor" : Object.hasOwn(labels, location.hash.slice(1))
      ? location.hash.slice(1)
      : "constructor";
    for (const page of document.querySelectorAll(".page-section"))
      page.hidden = page.id !== id;
    for (const link of document.querySelectorAll(
      "#project-nav a",
    )) {
      link.classList.toggle("active", link.hash === "#" + id);
      if (link.hash === "#" + id) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    }
    document.querySelector("#route-title").textContent = labels[id];
    closeMenus();
    document.querySelector(".analysis-menu").classList.toggle("current", !!document.querySelector(".analysis-menu a.active"));
    document.body.dataset.page = id;
    window.scrollTo({ top: 0, behavior: "instant" });
    if (assemblyChecks) {
      const checks = document.querySelector("#assembly-checks");
      checks.tabIndex = -1;
      checks.scrollIntoView({ block: "start" });
      checks.focus({ preventScroll: true });
    }
    requestAnimationFrame(() => window.dispatchEvent(new Event("resize")));
  }
  addEventListener("hashchange", route);
  route();
  new MutationObserver(() => {
    const id = document.body.dataset.page;
    document
      .querySelectorAll(".page-section")
      .forEach((p) => (p.hidden = p.id !== id));
  }).observe(document.querySelector("main"), { childList: true });
  // Обе сцены используют одни данные. На небольшом экране выбираем нужный вид.
  const root = document.querySelector("#constructor"),
    scene = root.querySelector(".assembly-scene"),
    scheme = root.querySelector(".schematic-editor");
  const studio = document.createElement("div");
  studio.className = "studio";
  scene.before(studio);
  studio.innerHTML =
    '<div class="studio-heading"><div><span class="live-dot"></span> Модель редуктора</div><div class="tool-tabs"><button data-scene="3d" class="active">Объёмная модель</button><button data-scene="2d">Схема 2D</button></div></div>';
  studio.append(scene, scheme);
  scheme.hidden = true;
  studio.querySelectorAll("[data-scene]").forEach(
    (b) =>
      (b.onclick = () => {
        scene.hidden = b.dataset.scene !== "3d";
        scheme.hidden = b.dataset.scene !== "2d";
        studio
          .querySelectorAll("[data-scene]")
          .forEach((x) => x.classList.toggle("active", x === b));
      }),
  );
  // Модель первой: исходные поля остаются доступными, но не заслоняют результат.
  root.querySelector(".builder-toolbar").after(studio);
  const setup = document.createElement("details");
  setup.className = "project-setup";
  setup.open = false;
  setup.innerHTML =
    "<summary><span>01</span><b>Исходные данные и двигатель</b><small>Мощность, частота, корпус</small></summary>";
  studio.after(setup);
  const global = root.querySelector("#builder-global"),
    motor = root.querySelector(".motor-card");
  setup.append(global);
  if (motor) setup.append(motor.parentElement);
  // Подробный расчёт — отдельный экран, а не скрытый якорь компоновки.
  root.addEventListener("click", (event) => {
    if (event.target.closest("[data-detail]"))
      queueMicrotask(() => {
        location.hash = "overview";
      });
  });
  const projectNotice = document.createElement("section");
  projectNotice.className = "review-notice";
  projectNotice.setAttribute("aria-label", "Итог проверок компоновки");
  projectNotice.setAttribute("aria-live", "polite");
  const desk = document.createElement("div");
  desk.className = "assembly-desk";
  root.querySelector(".page-heading").after(desk);
  const inspector = document.createElement("aside");
  inspector.className = "assembly-inspector";
  inspector.setAttribute("aria-label", "Данные ступени и редуктора");
  inspector.innerHTML = '<h2>Выбранная ступень</h2><div id="inspector-pair"></div><a href="#overview">Открыть расчёт ступени →</a><h2>Выход редуктора</h2>';
  desk.append(studio, inspector);
  inspector.append(root.querySelector("#assembly-metrics"), projectNotice);
  const presets = document.createElement("details");
  presets.className = "project-setup presets";
  presets.innerHTML = "<summary><b>Начать с шаблона</b></summary>";
  desk.after(presets);
  presets.append(root.querySelector(".builder-toolbar"));
  const stagePicker = document.querySelector("#project-stage");
  stagePicker.onchange = () => root.querySelector(`[data-flow="${Number(stagePicker.value)}"]`)?.click();

  // Размеры и нагрузки остаются узлами результата расчёта, рядом со сценой.
  const gearView = document.querySelector("#gear-view");
  gearView.after(document.querySelector("#metrics"));
  document.querySelector("#metrics").setAttribute("aria-label", "Геометрия и нагрузка выбранной ступени");

  const checksNotice = document.createElement("section");
  checksNotice.className = "review-notice";
  checksNotice.setAttribute("aria-label", "Область проверки выбранной ступени");
  const checksPage = document.querySelector("#checks");
  checksPage.querySelector(".section-heading").after(checksNotice);
  const write = (node, text) => {
    if (node.textContent !== text) node.textContent = text;
  };
  const make = (tag, text) => {
    const node = document.createElement(tag);
    node.textContent = text;
    return node;
  };
  const cards = (selector) => [...document.querySelectorAll(selector)].map((card) => ({
    title: card.querySelector("h3")?.textContent || "",
    detail: card.querySelector("p")?.textContent || "",
    failed: !!card.querySelector(".check-symbol.fail"),
    pending: !!card.querySelector(".check-symbol.pending"),
  }));
  let noticeStamp = "";
  function review() {
    document.querySelectorAll(".segmented [data-type]").forEach((button) =>
      button.setAttribute("aria-pressed", String(button.classList.contains("selected"))),
    );
    const stage = document.querySelector("#active-stage-label")?.textContent ||
      document.querySelector(".variant-label strong")?.textContent || "Ступень ещё не рассчитана";

    const assembly = cards("#assembly-checks .check"),
      selected = cards("#checks-list .check"),
      busy = root.classList.contains("builder-busy") || root.classList.contains("builder-invalid"),
      stageStatus = document.querySelector("#summary-status")?.textContent || "";
    const stamp = JSON.stringify([stage, assembly, selected, busy, stageStatus]);
    if (stamp === noticeStamp) return;
    noticeStamp = stamp;
    const failures = assembly.filter((c) => c.failed),
      pending = assembly.filter((c) => c.pending),
      ratio = assembly.find((c) => c.title === "Общее передаточное число");
    projectNotice.dataset.status = busy || !assembly.length ? "pending" : failures.length ? "fail" : "pending";
    const outcome = document.querySelector("#project-outcome");
    write(outcome, busy || !assembly.length ? "Ожидаем расчёт" : failures.length ? `Компоновка · отказов: ${failures.length}` : `Компоновка · уточнить: ${pending.length}`);
    outcome.dataset.status = !busy && failures.length ? "fail" : "pending";
    const title = make("h2", busy ? "Компоновка: результат обновляется или недоступен" : !assembly.length ?
      "Компоновка: ожидаем расчёт" : failures.length ? `Компоновка: не выполнено проверок — ${failures.length}` :
      "Компоновка: числовые проверки выполнены");
    const link = make("a", "Все проверки компоновки →");
    link.href = "#assembly-checks";
    link.onclick = () => { if (location.hash === link.hash) route(); };
    const nodes = [title];
    if (!busy && ratio) nodes.push(make("p", `${ratio.failed ? "Не выполнено" : "Выполнено"}: ${ratio.title}. ${ratio.detail}`));
    if (!busy && failures.some((c) => c !== ratio)) nodes.push(make("p", `Требуют исправления: ${failures.filter((c) => c !== ratio).map((c) => c.title).join("; ")}.`));
    const scope = document.createElement("details");
    scope.append(make("summary", `Область расчёта${!busy && assembly.length ? ` · уточнить условий: ${pending.length}` : ""}`),
      make("p", "Прочность ступеней проверяется отдельно. Статика и габариты не подтверждают прочность валов и ресурс подшипников."));
    nodes.push(scope, link);
    projectNotice.replaceChildren(...nodes);
    const unresolved = selected.filter((c) => c.failed || c.pending);
    checksNotice.dataset.status = selected.some((c) => c.failed) ? "fail" : "pending";
    const checksNodes = [make("h3", stage), make("p", busy ? "Результат обновляется или недоступен. Предыдущие числа не подтверждают текущие исходные данные." : stageStatus || "Ожидаем проверку ступени."),
      make("p", "Это проверки выбранной ступени. Выполнение числовых условий не подтверждает исходные технологические данные и все случаи ГОСТ.")];
    if (!busy && ratio?.failed) checksNodes.push(make("p", `В компоновке не выполнено общее передаточное число. ${ratio.detail}`));
    if (!busy && unresolved.length) {
      const details = document.createElement("details");
      details.append(make("summary", `Отказы и неподтверждённые условия: ${unresolved.length}`));
      const list = document.createElement("ul");
      unresolved.forEach((c) => list.append(make("li", `${c.title}: ${c.detail}`)));
      details.append(list);
      checksNodes.push(details);
    }
    const back = make("a", "Проверки всего редуктора →");
    back.href = "#assembly-checks";
    checksNodes.push(back);
    checksNotice.replaceChildren(...checksNodes);
  }
  const reviewObserver = new MutationObserver((records) => {
    if (records.some((record) => ![projectNotice, checksNotice].some((node) => node === record.target || node.contains(record.target)))) review();
  });
  reviewObserver.observe(document.querySelector("main"), { childList: true, subtree: true });
  reviewObserver.observe(root, { attributes: true, attributeFilter: ["class"] });
  review();
}
