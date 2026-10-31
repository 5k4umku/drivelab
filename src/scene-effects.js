import * as THREE from "three";

// Эффекты меняют только представление. Силы и скорости приходят из Python.
export function installSceneEffects(viewer) {
  const panel = document.createElement("div");
  panel.className = "scene-tools";
  panel.innerHTML =
    '<label>Разнести сборку<input type="range" min="0" max="100" value="0" aria-label="Разнести сборку"></label><button data-effect="forces" aria-pressed="false">Силы</button><button data-effect="section" aria-pressed="false">Разрез</button><button data-effect="orbit" aria-pressed="false">Облёт</button><button data-effect="reset">Собрать</button><span class="scene-mode-note">Рабочее зацепление</span>';
  viewer.container.after(panel);
  viewer.effectsPanel = panel;
  viewer.explosion = 0;
  viewer.explosionTarget = 0;
  viewer.renderer.localClippingEnabled = true;
  viewer.forceGroup = new THREE.Group();
  viewer.scene.add(viewer.forceGroup);
  viewer.forceGroup.visible = false;
  panel.querySelector("input").oninput = (ev) => {
    viewer.explosionTarget = Number(ev.target.value) / 100;
    note();
  };
  function note() {
    panel.querySelector(".scene-mode-note").textContent = viewer.explosionTarget
      ? "Разнесённый вид · без физического контакта"
      : viewer.sectionOn
        ? "Визуальный разрез · расчёт без изменений"
        : "Рабочее зацепление";
  }
  panel.querySelectorAll("[data-effect]").forEach(
    (button) =>
      (button.onclick = () => {
        const action = button.dataset.effect;
        if (action === "forces") viewer.forcesOn = !viewer.forcesOn;
        if (action === "section") {
          viewer.sectionOn = !viewer.sectionOn;
          applySection(viewer);
        }
        if (action === "orbit")
          viewer.controls.autoRotate = !viewer.controls.autoRotate;
        if (action === "reset") {
          viewer.explosionTarget = 0;
          panel.querySelector("input").value = 0;
          viewer.sectionOn = false;
          viewer.forcesOn = false;
          viewer.controls.autoRotate = false;
          applySection(viewer);
        }
        panel
          .querySelector('[data-effect="forces"]')
          .setAttribute("aria-pressed", String(!!viewer.forcesOn));
        panel
          .querySelector('[data-effect="section"]')
          .setAttribute("aria-pressed", String(!!viewer.sectionOn));
        panel
          .querySelector('[data-effect="orbit"]')
          .setAttribute("aria-pressed", String(viewer.controls.autoRotate));
        note();
      }),
  );
  viewer.controls.autoRotateSpeed = 0.6;
  viewer.controls.addEventListener("start", () => {
    viewer.cameraTransition = null;
  });
  viewer.visibilityObserver = new IntersectionObserver((entries) => {
    viewer.inViewport = entries[0].isIntersecting;
  });
  viewer.visibilityObserver.observe(viewer.container);
  viewer.inViewport = true;
  viewer.tickEffects = (dt) => {
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
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
          viewer.gears[0].position.x + (sgn * c.d1) / 2,
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
  applySection(viewer);
}

export function moveCamera(viewer, target, position) {
  if (!viewer.hasCamera) {
    viewer.controls.target.copy(target);
    viewer.camera.position.copy(position);
    viewer.hasCamera = true;
  } else
    viewer.cameraTransition = {
      from: viewer.camera.position.clone(),
      to: position.clone(),
      targetFrom: viewer.controls.target.clone(),
      targetTo: target.clone(),
      elapsed: 0,
    };
}
