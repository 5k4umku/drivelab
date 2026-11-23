import * as THREE from "three";
import { fmt } from "./format.js";

let sceneId = 0;

// Эффекты меняют только представление. Силы и скорости приходят из Python.
export function installSceneEffects(viewer) {
  const panel = document.createElement("div");
  const id = `scene-${++sceneId}`;
  panel.className = "scene-tools";
  panel.innerHTML =
    `<label for="${id}-explode">Разнесение <output for="${id}-explode">0 %</output><input id="${id}-explode" type="range" min="0" max="100" step="1" value="0" aria-label="Разнести сборку" aria-valuetext="0 %, рабочее зацепление"></label><button data-effect="forces" aria-pressed="false">Силы</button><button data-effect="section" aria-pressed="false">Разрез</button><button data-effect="orbit" aria-pressed="false">Облёт</button><button data-effect="front" title="Вид с торца (F)">С торца</button><button data-effect="iso" title="Общий объёмный вид (I)">Общий вид</button><button data-effect="contact">Зацепление</button><button data-effect="reset" title="Собрать модель и вернуть исходный ракурс (Home)">Исходный вид</button><span class="scene-mode-note" role="status">Рабочее зацепление</span><span class="scene-context"></span><span class="scene-force-note" hidden></span><span class="scene-help" id="${id}-help">Мышь: поворот левой кнопкой, масштаб колесом. Касание: один палец — поворот, два — масштаб и сдвиг. Клавиатура на модели: стрелки — сдвиг, Shift + стрелки — поворот, +/− — масштаб, F/I — ракурс, Home — исходный вид.</span>`;
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
  panel.querySelectorAll("button").forEach((button) => {
    button.style.minHeight = "44px";
    button.style.minWidth = "44px";
    button.style.flex = "0 1 auto";
  });
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
  }
  viewer.syncSceneTools = sync;
  function action(name) {
    const orbitWasOn = viewer.controls.autoRotate;
    viewer.pauseMotion();
    if (name === "forces") viewer.forcesOn = !viewer.forcesOn;
    if (name === "section") {
      viewer.sectionOn = !viewer.sectionOn;
      applySection(viewer);
    }
    if (name === "orbit") viewer.controls.autoRotate = !orbitWasOn && !viewer.motionQuery.matches;
    if (name === "reset") {
      setExplosion(0);
      viewer.sectionOn = false;
      viewer.forcesOn = false;
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
      named = { home: "reset", f: "front", i: "iso" }[key];
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
  if (r.gears) {
    loads = r.gears
      .filter((g) => g.side === 1)
      .map((g) => ({
        origin: new THREE.Vector3(g.x + g.offset[0], g.y + g.offset[1], g.z),
        force: g.force,
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
        [0xf4a85a, 0x71cbbb, 0x8fa7ff][k],
        Math.min(len * 0.3, 12),
        Math.min(len * 0.15, 6),
      );
      viewer.forceGroup.add(arrow);
    });
  if (viewer.effectsPanel) {
    const context = viewer.effectsPanel.querySelector(".scene-context"),
      forceNote = viewer.effectsPanel.querySelector(".scene-force-note");
    if (r.chosen) {
      const c = r.chosen;
      context.textContent = `m = ${fmt(c.m)} мм · z₁/z₂ = ${c.z1}/${c.z2} · aw = ${fmt(c.a)} мм · b = ${fmt(r.b)} мм`;
      forceNote.textContent = `Силы на шестерне: Ft = ${fmt(c.Ft)} Н · Fr = ${fmt(c.Fr)} Н · Fa = ${fmt(c.Fa)} Н. Оси локальные; длины стрелок нормированы.` +
        (r.input.gearType === "herringbone" ? ` Полушевроны: FaL = ${fmt(c.FaLeft ?? c.FaHalf)} Н, FaR = ${fmt(c.FaRight ?? -c.FaHalf)} Н; Fa — результирующая.` : "");
    } else {
      context.textContent = `${r.stages.length} ступ. · ${r.shafts.length} вал. · nвых = ${fmt(r.outputSpeed, 2)} мин⁻¹ · «Зацепление» — ступень 1`;
      forceNote.textContent = `Силы на шестернях: X — оранжевый, Y — зелёный, Z — синий. Максимум компоненты = ${fmt(maximum)} Н; длины стрелок нормированы.`;
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
