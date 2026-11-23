import * as THREE from "three";
import { fmt } from "./format.js";

let sceneId = 0;
const forceColors = [0xf0f2f5, 0x72dce8, 0xc5b7fa];
const forceLegend = "X — белый, Y — бирюзовый, Z — лиловый";

// Эффекты меняют только представление. Силы и скорости приходят из Python.
export function installSceneEffects(viewer) {
  const panel = document.createElement("div");
  const id = `scene-${++sceneId}`;
  panel.className = "scene-tools";
  panel.innerHTML = `
    <style>
      .scene-tools .scene-controls-row,
      .scene-tools :is(.scene-views, .scene-options) {
        display: flex; flex-wrap: wrap; align-items: center; gap: 6px; min-width: 0;
      }
      .scene-tools :is(.scene-controls-row, .scene-readout, .scene-help) { flex-basis: 100%; }
      .scene-tools .scene-readout { display: grid; gap: 4px; line-height: 1.45; }
      .scene-tools .scene-mode-note { margin: 0; }
      .scene-tools .scene-context { grid-row: 1; font-size: 12px; font-weight: 600; }
      .scene-tools .scene-controls-row button {
        flex: 0 1 auto; min-height: 44px; min-width: 44px; border-radius: 5px;
      }
      .scene-tools .scene-controls-row button[aria-pressed="true"] {
        background: var(--accent); border-color: var(--accent); color: #09212b;
      }
      .scene-tools .scene-controls-row input[type="range"] { accent-color: var(--accent); }
    </style>
    <div class="scene-controls-row">
      <div class="scene-views" role="group" aria-label="Ракурс модели">
        <button type="button" data-effect="iso" aria-pressed="true" title="Общий вид (I)">Общий вид</button>
        <button type="button" data-effect="front" aria-pressed="false" title="Вид с торца (F)">С торца</button>
        <button type="button" data-effect="contact" aria-pressed="false" title="Крупный план зацепления (C)">Зацепление</button>
      </div>
      <button type="button" data-effect="reset" title="Собрать модель и вернуть исходный ракурс (Home)">Исходный вид</button>
    </div>
    <div class="scene-controls-row">
      <label for="${id}-explode">Разнесение <output for="${id}-explode">0 %</output>
        <input id="${id}-explode" type="range" min="0" max="100" step="1" value="0"
          aria-label="Разнести сборку" aria-valuetext="0 %, рабочее зацепление">
      </label>
      <div class="scene-options" role="group" aria-label="Слои и движение модели">
        <button type="button" data-effect="grid" aria-pressed="true" title="Сетка (G)">Сетка</button>
        <button type="button" data-effect="forces" aria-pressed="false">Силы</button>
        <button type="button" data-effect="section" aria-pressed="false">Разрез</button>
        <button type="button" data-effect="orbit" aria-pressed="false">Облёт</button>
      </div>
    </div>
    <div class="scene-readout">
      <span class="scene-mode-note" role="status">Рабочее зацепление</span>
      <span class="scene-grid-note"></span>
      <span class="scene-context"></span>
      <span class="scene-profile-note" hidden>Эвольвенты соседних зубьев кольца сходятся до диаметра впадин df₂. Для построения перехода до df₂ нужен профиль долбяка.</span>
      <span class="scene-force-note" hidden></span>
    </div>
    <details class="scene-help"><summary>Управление и геометрия модели</summary>
      <p>Эвольвентные боковые поверхности показаны по расчётным диаметрам. Переход к впадине и кожух условные. Боковой зазор, форма от инструмента и возможность интерференции требуют данных изготовления.</p>
      <p>В парном виде зелёная окружность — делительная d, синяя — основная db. При смещении оранжевым показана отличающаяся начальная окружность dw.</p>
      <p id="${id}-help">Мышь: перетащите модель для поворота, колесо меняет масштаб.
        Касание: один палец — поворот, два — масштаб и сдвиг.
        Клавиатура на модели: стрелки — сдвиг, Shift + стрелки — поворот, +/− — масштаб,
        I — общий вид, F — с торца, C — зацепление, G — сетка, Home — исходный вид.</p>
    </details>`;
  viewer.container.after(panel);
  viewer.effectsPanel = panel;
  viewer.explosion = 0;
  viewer.explosionTarget = 0;
  viewer.renderer.localClippingEnabled = true;
  viewer.forceGroup = new THREE.Group();
  viewer.scene.add(viewer.forceGroup);
  viewer.forceGroup.visible = false;
  const canvas = viewer.renderer.domElement;
  canvas.tabIndex = 0;
  canvas.setAttribute("role", "group");
  canvas.setAttribute("aria-label", "Интерактивная модель передачи");
  canvas.setAttribute("aria-describedby", `${id}-help`);
  canvas.addEventListener("focus", () => {
    canvas.style.outline = "3px solid var(--focus, #187b60)";
    canvas.style.outlineOffset = "-3px";
  });
  canvas.addEventListener("blur", () => { canvas.style.outline = ""; });
  viewer.pauseMotion = () => {
    viewer.playing = false;
    viewer.controls.autoRotate = false;
    viewer.cameraTransition = null;
    sync();
  };
  function setExplosion(value) {
    viewer.explosionTarget = Math.max(0, Math.min(1, value));
    viewer.explosion = viewer.explosionTarget;
    panel.querySelector("input").value = Math.round(viewer.explosionTarget * 100);
    viewer.tickEffects(0);
    sync();
  }
  panel.querySelector("input").oninput = (ev) => {
    viewer.pauseMotion();
    setExplosion(Number(ev.target.value) / 100);
    if (viewer.explosion && viewer.viewMode === "contact") {
      viewer.view("iso", true);
    } else if (!ev.isTrusted) {
      // A preset can set the native range without a subsequent change event.
      viewer.view(viewer.viewMode || "iso", true);
    }
  };
  panel.querySelector("input").onchange = () => viewer.view(viewer.viewMode || "iso", true);
  let gridStep;
  const gridNote = panel.querySelector(".scene-grid-note");
  viewer.setGridStep = (step) => {
    gridStep = step;
    gridNote.textContent = `Сетка XY · ${fmt(step)} мм`;
  };
  function sync() {
    const percent = Math.round(viewer.explosionTarget * 100);
    panel.querySelector("output").textContent = `${percent} %`;
    panel.querySelector("input").setAttribute("aria-valuetext",
      percent ? `${percent} %, разнесённый вид без физического контакта` : "0 %, рабочее зацепление");
    panel.querySelector(".scene-mode-note").textContent = viewer.explosionTarget
      ? `Разнесённый вид ${percent} % · без физического контакта${viewer.forcesOn ? " · силы скрыты" : ""}`
      : viewer.sectionOn
        ? "Визуальный разрез · расчёт без изменений"
        : "Рабочее зацепление";
    for (const [action, on] of [["forces", viewer.forcesOn], ["section", viewer.sectionOn], ["orbit", viewer.controls.autoRotate]])
      panel.querySelector(`[data-effect="${action}"]`).setAttribute("aria-pressed", String(!!on));
    panel.querySelector(".scene-force-note").hidden = !viewer.forcesOn;
    panel.querySelector('[data-effect="grid"]').setAttribute("aria-pressed", String(viewer.grid.visible));
    gridNote.hidden = !viewer.grid.visible || gridStep === undefined;
  }
  viewer.syncSceneTools = sync;
  viewer.updateSceneContext = (contact) => {
    const r = viewer.result;
    if (!r?.stages) return;
    const detail = contact ?? viewer.contactDetail();
    const context = panel.querySelector(".scene-context");
    const button = panel.querySelector('[data-effect="contact"]');
    button.disabled = !detail;
    button.textContent = detail ? `Зацепление · ступень ${detail.number}` : "Зацепление";
    if (contact) {
      const { pair, number } = contact;
      const c = pair.chosen;
      const mesh = c.meshType === "internal" ? "внутреннее" : "внешнее";
      context.textContent = `Ступень ${number} · ${mesh} зацепление · z₁/z₂ = ${c.z1}/${c.z2} · aw = ${fmt(c.a)} мм · b = ${fmt(pair.b)} мм`;
    } else {
      context.textContent = `${r.stages.length} ступ. · ${r.shafts.length} вал. · nвых = ${fmt(r.outputSpeed, 2)} мин⁻¹`;
    }
    for (const arrow of viewer.forceGroup.children)
      arrow.visible = !contact || arrow.userData.stageNumber === contact.number;
    const forceNote = panel.querySelector(".scene-force-note");
    const source = contact ? `Силы на шестерне ступени ${contact.number}` : "Силы на шестернях";
    forceNote.textContent = `${source}. ${forceLegend}. Общий масштаб сборки, максимум компоненты ${fmt(viewer.forceScale)} Н.`;
  };
  function action(name) {
    const orbitWasOn = viewer.controls.autoRotate;
    viewer.pauseMotion();
    if (name === "forces") viewer.forcesOn = !viewer.forcesOn;
    if (name === "grid") viewer.grid.visible = !viewer.grid.visible;
    if (name === "section") {
      viewer.sectionOn = !viewer.sectionOn;
      applySection(viewer);
    }
    if (name === "orbit") viewer.controls.autoRotate = !orbitWasOn && !viewer.motionQuery.matches;
    if (name === "reset") {
      setExplosion(0);
      viewer.sectionOn = false;
      viewer.forcesOn = false;
      viewer.grid.visible = true;
      applySection(viewer);
      viewer.view("iso");
    }
    if (["front", "iso", "contact"].includes(name)) {
      if (name === "contact") setExplosion(0);
      viewer.view(name);
    }
    sync();
  }
  panel.querySelectorAll("[data-effect]").forEach(
    (button) =>
      (button.onclick = () => {
        action(button.dataset.effect);
      }),
  );
  viewer.controls.autoRotateSpeed = 0.6;
  viewer.controls.addEventListener("start", viewer.pauseMotion);
  viewer.controls.listenToKeyEvents(canvas);
  canvas.addEventListener("keydown", (event) => {
    const key = event.key.toLowerCase(),
      named = { home: "reset", f: "front", i: "iso", c: "contact", g: "grid" }[key]
        ?? { KeyF: "front", KeyI: "iso", KeyC: "contact", KeyG: "grid" }[event.code];
    if (event.altKey || ((event.metaKey || event.ctrlKey) && !key.startsWith("arrow"))) return;
    if (!named && !key.startsWith("arrow") && !["+", "=", "-", "−"].includes(key)) return;
    viewer.pauseMotion();
    if (named) action(named);
    else if (["+", "=", "-", "−"].includes(key)) {
      const offset = viewer.camera.position.clone().sub(viewer.controls.target),
        distance = THREE.MathUtils.clamp(offset.length() * (["+", "="].includes(key) ? .85 : 1 / .85), viewer.controls.minDistance, viewer.controls.maxDistance);
      viewer.camera.position.copy(viewer.controls.target).add(offset.setLength(distance));
      viewer.controls.update();
    }
    event.preventDefault();
  }, true);
  viewer.motionQuery = matchMedia("(prefers-reduced-motion: reduce)");
  const respectMotion = () => {
    viewer.reducedMotion = viewer.motionQuery.matches;
    viewer.controls.enableDamping = !viewer.motionQuery.matches;
    panel.querySelector('[data-effect="orbit"]').disabled = viewer.motionQuery.matches;
    if (viewer.motionQuery.matches) {
      if (viewer.cameraTransition) {
        viewer.camera.position.copy(viewer.cameraTransition.to);
        viewer.controls.target.copy(viewer.cameraTransition.targetTo);
      }
      viewer.pauseMotion();
    }
  };
  viewer.motionQuery.addEventListener("change", respectMotion);
  respectMotion();
  viewer.visibilityObserver = new IntersectionObserver((entries) => {
    viewer.inViewport = entries[0].isIntersecting;
    viewer.last = performance.now();
  });
  document.addEventListener("visibilitychange", () => {
    viewer.last = performance.now();
  });
  viewer.visibilityObserver.observe(viewer.container);
  viewer.inViewport = true;
  viewer.tickEffects = (dt) => {
    const reduce = viewer.motionQuery.matches;
    // Also observe the current value: media emulation and suspended tabs can
    // update matches before delivering the change event.
    if (reduce !== viewer.reducedMotion) respectMotion();
    viewer.explosion = THREE.MathUtils.lerp(
      viewer.explosion,
      viewer.explosionTarget,
      reduce ? 1 : 1 - Math.exp(-dt * 6),
    );
    viewer.model.traverse((object) => {
      if (object.userData.restPosition)
        object.position
          .copy(object.userData.restPosition)
          .addScaledVector(object.userData.explodeDirection, viewer.explosion);
    });
    viewer.forceGroup.visible = !!viewer.forcesOn && viewer.explosion < 0.01;
    if (viewer.cameraTransition) {
      const t = viewer.cameraTransition;
      t.elapsed += dt;
      const progress = reduce ? 1 : Math.min(1, t.elapsed / 0.75),
        ease = progress * progress * (3 - 2 * progress);
      viewer.camera.position.lerpVectors(t.from, t.to, ease);
      viewer.controls.target.lerpVectors(t.targetFrom, t.targetTo, ease);
      if (progress === 1) viewer.cameraTransition = null;
    }
  };
}

function applySection(viewer) {
  const z = viewer.center?.z || 0;
  viewer.model.traverse((object) => {
    if (object.material) {
      object.material.clippingPlanes = viewer.sectionOn
        ? [new THREE.Plane(new THREE.Vector3(0, 0, -1), z)]
        : [];
      object.material.needsUpdate = true;
    }
  });
}

export function prepareSceneEffects(viewer) {
  viewer.model.traverse((object) => {
    if (object.userData.explodeDirection)
      object.userData.restPosition = object.position.clone();
  });
  for (const child of [...viewer.forceGroup.children]) {
    viewer.forceGroup.remove(child);
    child.traverse((o) => {
      o.geometry?.dispose();
      o.material?.dispose();
    });
  }
  const r = viewer.result;
  let loads = [];
  if (viewer.effectsPanel) {
    let limited = false;
    viewer.model.traverse(o => { if (o.geometry?.userData.limitedRingRoot) limited = true; });
    viewer.effectsPanel.querySelector(".scene-profile-note").hidden = !limited;
  }
  if (r.gears) {
    loads = r.gears
      .filter((g) => g.side === 1)
      .map((g) => ({
        origin: new THREE.Vector3(g.x + g.offset[0], g.y + g.offset[1], g.z),
        force: g.force,
        stageNumber: g.stage + 1,
      }));
  } else if (r.chosen) {
    const c = r.chosen,
      sgn = c.meshType === "internal" ? -1 : 1,
      hand = r.assemblyContext?.hand === "left" ? -1 : 1;
    loads = [
      {
        origin: new THREE.Vector3(
          viewer.gears[0].position.x + (sgn * (c.dw1 ?? c.d1)) / 2,
          0,
          0,
        ),
        force: [-sgn * c.Fr, -sgn * c.Ft, hand * c.Fa],
      },
    ];
  }
  const maximum = Math.max(1, ...loads.flatMap((l) => l.force.map(Math.abs)));
  viewer.forceScale = maximum;
  for (const load of loads)
    load.force.forEach((value, k) => {
      if (Math.abs(value) < 1e-8) return;
      const dir = new THREE.Vector3();
      dir.setComponent(k, Math.sign(value));
      const len = ((viewer.extent || 300) * 0.23 * Math.abs(value)) / maximum;
      const arrow = new THREE.ArrowHelper(
        dir,
        load.origin,
        len,
        forceColors[k],
        Math.min(len * 0.3, 12),
        Math.min(len * 0.15, 6),
      );
      // Give the stem real screen presence and keep force annotations above the mesh.
      const stemLength = len - Math.min(len * 0.3, 12);
      const stemRadius = Math.min(stemLength * 0.045, (viewer.extent || 300) * 0.003);
      const stem = new THREE.Mesh(
        new THREE.CylinderGeometry(stemRadius, stemRadius, stemLength, 8),
        new THREE.MeshBasicMaterial({ color: forceColors[k], depthTest: false, toneMapped: false }),
      );
      stem.position.y = stemLength / 2;
      stem.renderOrder = 10;
      arrow.line.visible = false;
      arrow.cone.material.depthTest = false;
      arrow.cone.material.toneMapped = false;
      arrow.cone.renderOrder = 10;
      arrow.add(stem);
      arrow.userData.stageNumber = load.stageNumber;
      viewer.forceGroup.add(arrow);
    });
  if (viewer.effectsPanel) {
    const context = viewer.effectsPanel.querySelector(".scene-context"),
      forceNote = viewer.effectsPanel.querySelector(".scene-force-note");
    if (r.chosen) {
      const c = r.chosen;
      context.textContent = `m = ${fmt(c.m)} мм · z₁/z₂ = ${c.z1}/${c.z2} · aw = ${fmt(c.a)} мм · b = ${fmt(r.b)} мм`;
      forceNote.textContent = `Ft = ${fmt(c.Ft)} Н · Fr = ${fmt(c.Fr)} Н · Fa = ${fmt(c.Fa)} Н. Локальные оси: ${forceLegend}. Длины стрелок нормированы.` +
        (r.input.gearType === "herringbone" ? ` Полушевроны: FaL = ${fmt(c.FaLeft ?? c.FaHalf)} Н, FaR = ${fmt(c.FaRight ?? -c.FaHalf)} Н; Fa — результирующая.` : "");
    }
    viewer.syncSceneTools();
  }
  viewer.explosion = viewer.explosionTarget || 0;
  viewer.model.traverse((object) => {
    if (object.userData.restPosition)
      object.position.copy(object.userData.restPosition)
        .addScaledVector(object.userData.explodeDirection, viewer.explosion);
  });
  applySection(viewer);
}

export function moveCamera(viewer, target, position) {
  if (!viewer.hasCamera || viewer.motionQuery?.matches) {
    viewer.controls.target.copy(target);
    viewer.camera.position.copy(position);
    viewer.hasCamera = true;
    viewer.cameraTransition = null;
  } else
    viewer.cameraTransition = {
      from: viewer.camera.position.clone(),
      to: position.clone(),
      targetFrom: viewer.controls.target.clone(),
      targetTo: target.clone(),
      elapsed: 0,
    };
}
