import {
  installSceneEffects,
  prepareSceneEffects,
  moveCamera,
} from "./scene-effects.js";
import * as THREE from "three";
import { OrbitControls } from "../vendor/three/OrbitControls.js";

import { gearMesh, meshPhase } from "./gear-geometry.js";
export { gearGeometry } from "./gear-geometry.js";

export const sceneAccent = 0x6ce2f5;

function studioEnvironment(renderer) {
  const surface = document.createElement("canvas");
  surface.width = 256;
  surface.height = 128;
  const ctx = surface.getContext("2d");
  ctx.fillStyle = "#303134";
  ctx.fillRect(0, 0, surface.width, surface.height);
  for (const [x, y, width, height, color] of [
    [14, 30, 68, 34, "#f6f5f3"],
    [122, 18, 36, 48, "#c6c7ca"],
    [174, 64, 64, 18, "#e4e5e5"],
  ]) {
    ctx.fillStyle = color;
    ctx.fillRect(x, y, width, height);
  }
  const texture = new THREE.CanvasTexture(surface);
  texture.mapping = THREE.EquirectangularReflectionMapping;
  texture.colorSpace = THREE.SRGBColorSpace;
  const generator = new THREE.PMREMGenerator(renderer);
  const environment = generator.fromEquirectangular(texture);
  generator.dispose();
  texture.dispose();
  return environment;
}

export function steelMaterial(color = 0xb6b8bb) {
  return new THREE.MeshStandardMaterial({ color, metalness: 0.72, roughness: 0.34 });
}

export class GearViewer {
  get playing() {
    return this._playing;
  }
  set playing(value) {
    this._playing = !!value;
    // Keep the existing playback control truthful after a direct scene gesture.
    const button = this.container?.closest(".viewer-card")?.querySelector(".playback .play");
    if (button) {
      button.textContent = this._playing ? "Ⅱ" : "▶";
      button.setAttribute("aria-label", this._playing ? "Приостановить вращение" : "Включить вращение");
    }
    this.container?.dispatchEvent(new CustomEvent("scene-playback-change", {
      bubbles: true,
      detail: { playing: this._playing },
    }));
  }
  constructor(container) {
    this.container = container;
    this.playing = !matchMedia("(prefers-reduced-motion: reduce)").matches;
    this.scale = 0.012;
    this.theta = 0;
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(34, 1, 0.1, 10000);
    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      powerPreference: "high-performance",
    });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.setClearColor(0x0c1727);
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.scene.environment = studioEnvironment(this.renderer).texture;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.replaceChildren(this.renderer.domElement);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.075;
    this.controls.enablePan = true;
    this.scene.add(new THREE.HemisphereLight(0xf4fbff, 0x546d91, 1.4));
    for (const [x, y, z, power, color] of [
      [-250, 350, 400, 2.8, 0xf5fbff],
      [350, -120, -300, 2.25, 0x8fc9ff],
    ]) {
      const l = new THREE.DirectionalLight(color, power);
      l.position.set(x, y, z);
      this.scene.add(l);
    }
    this.model = new THREE.Group();
    this.scene.add(this.model);
    this.grid = new THREE.GridHelper(20, 20, 0x648db2, 0x426285);
    this.grid.rotation.x = Math.PI / 2;
    this.grid.material.transparent = true;
    this.grid.material.opacity = 0.44;
    this.grid.material.depthWrite = false;
    this.grid.material.toneMapped = false;
    this.scene.add(this.grid);
    this.lines = new THREE.Group();
    this.model.add(this.lines);
    this.lines.visible = false;
    installSceneEffects(this);
    this.observer = new ResizeObserver(() => this.resize());
    this.observer.observe(container);
    this.last = performance.now();
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }
  resize() {
    const w = this.container.clientWidth,
      h = this.container.clientHeight;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    if (
      this.result &&
      (!this.visibleWidth || Math.abs(w - this.visibleWidth) > 40)
    )
      this.view(this.viewMode || "iso", true);
    this.visibleWidth = w;
  }
  update(result) {
    const c = result.chosen;
    if (!c) return;
    this.result = result;
    this.theta = 0;
    for (const child of [...this.model.children])
      if (child !== this.lines) {
        this.model.remove(child);
        child.traverse((o) => {
          if (o.isInstancedMesh) o.dispose();
          o.geometry?.dispose();
          o.material?.dispose();
        });
      }
    for (const child of [...this.lines.children]) {
      this.lines.remove(child);
      child.geometry?.dispose();
      child.material?.dispose();
    }
    // Center the actual addendum envelope, including unequal profile shifts.
    const r1 = c.da1 / 2,
      r2 = (c.outerDiameter || c.da2) / 2,
      left = Math.min(-c.a / 2 - r1, c.a / 2 - r2),
      right = Math.max(-c.a / 2 + r1, c.a / 2 + r2),
      offset = (left + right) / 2;
    this.gears = [];
    for (const i of [1, 2]) {
      const group = new THREE.Group();
      group.position.x = (i === 1 ? -c.a / 2 : c.a / 2) - offset;
      this.model.add(group);
      this.gears.push(group);
      const material = steelMaterial(i === 1 ? 0xcbd0d3 : 0xaeb1b6);
      const gear = gearMesh(c, i, result.b, result.input.gearType,
        result.assemblyContext?.hand === "left" ? -1 : 1, material);
      gear.userData.explodeDirection = new THREE.Vector3(
        0,
        0,
        (i === 1 ? -1 : 1) * result.b * 2,
      );
      group.add(gear);
      // shaft symbols have illustrative diameter, separately identified in caption.
      const shaft = new THREE.Mesh(
        new THREE.CylinderGeometry(
          c["df" + i] * 0.13,
          c["df" + i] * 0.13,
          result.b * 1.9,
          40,
        ),
        steelMaterial(0x82858a),
      );
      shaft.rotation.x = Math.PI / 2;
      if (!(c.meshType === "internal" && i === 2)) group.add(shaft);
      else {
        shaft.geometry.dispose();
        shaft.material.dispose();
      }
      const mark = new THREE.Mesh(
        new THREE.BoxGeometry(c["d" + i] * 0.25, c.m * 0.7, 0.8),
        new THREE.MeshBasicMaterial({ color: i === 1 ? sceneAccent : 0xe4e5e7, toneMapped: false }),
      );
      mark.position.set(c["d" + i] * 0.23, 0, result.b / 2 + 0.7);
      if (c.meshType === "internal" && i === 2) {
        mark.geometry.dispose();
        mark.geometry = new THREE.BoxGeometry(
          (c.outerDiameter - c.df2) * 0.25,
          c.m * 0.7,
          0.8,
        );
        mark.position.x = (c.outerDiameter + c.df2) / 4;
      }
      group.add(mark);
      for (const [key, color] of [
        ["d", 0x91e5be],
        ["db", 0x597e91],
        ["dw", 0xffaa65],
      ]) {
        if (key === "dw" && Math.abs((c[key + i] ?? c["d" + i]) - c["d" + i]) < 1e-8) continue;
        const pts = Array.from(
          { length: 181 },
          (_, j) =>
            new THREE.Vector3(
              group.position.x +
                (c[key + i] / 2) * Math.cos((j * 2 * Math.PI) / 180),
              (c[key + i] / 2) * Math.sin((j * 2 * Math.PI) / 180),
              result.b / 2 + 1.5,
            ),
        );
        this.lines.add(
          new THREE.Line(
            new THREE.BufferGeometry().setFromPoints(pts),
            new THREE.LineBasicMaterial({
              color,
              transparent: true,
              opacity: 0.65,
            }),
          ),
        );
      }
    }
    this.phase = meshPhase(c, 2);
    this.pinionPhase = meshPhase(c, 1);
    this.gears[0].rotation.z = this.pinionPhase;
    this.gears[1].rotation.z = this.phase;
    // Include the axial shaft symbols: a wide pair must also fit in iso view.
    this.extent = Math.max(right - left, 2 * r1, 2 * r2, result.b * 1.9);
    prepareSceneEffects(this);
    this.view(this.viewMode || "iso", true);
    this.resize();
  }
  contactDetail() {
    const pair = this.result;
    const c = pair?.chosen;
    if (!c) return null;
    const sign = c.meshType === "internal" ? -1 : 1;
    return {
      pair,
      position: new THREE.Vector3(this.gears[0].position.x + sign * (c.dw1 ?? c.d1) / 2, 0, 0),
    };
  }

  view(mode, preserveMotion = false) {
    if (!preserveMotion) this.pauseMotion?.();
    const contact = mode === "contact" ? this.contactDetail() : null;
    if (mode === "contact" && !contact) mode = "iso";
    this.viewMode = mode;
    this.updateSceneContext?.(contact);
    this.effectsPanel?.querySelectorAll('[data-effect="front"], [data-effect="iso"], [data-effect="contact"]').forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.effect === mode));
    });
    this.container?.closest?.(".viewer-card")?.querySelectorAll('.viewer-top [id$="-front"], .viewer-top [id$="-iso"]').forEach((button) => {
      const active = button.id.endsWith(`-${mode}`);
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    const box = new THREE.Box3().setFromObject(this.model),
      center = box.isEmpty() ? new THREE.Vector3() : box.getCenter(new THREE.Vector3()),
      size = box.getSize(new THREE.Vector3());
    let s = Math.max(size.x, size.y, size.z, this.extent || 450);
    if (contact) {
      const { pair, position } = contact;
      const c = pair.chosen;
      center.copy(position);
      s = Math.max(pair.b * 1.4, c.m * 12);
    }
    if (this.grid) {
      const targetStep = s / 14;
      const decade = 10 ** Math.floor(Math.log10(targetStep));
      const step = ([1, 2, 5, 10].find((factor) => factor * decade >= targetStep) ?? 10) * decade;
      this.grid.scale.setScalar(step);
      this.grid.position.set(
        Math.round(center.x / step) * step,
        Math.round(center.y / step) * step,
        contact ? center.z - s * 0.65 : box.isEmpty() ? -s : box.min.z - step,
      );
      this.setGridStep?.(step);
    }
    const aspect =
      this.container.clientWidth / Math.max(1, this.container.clientHeight) ||
      1;
    const direction = (mode === "front"
      ? new THREE.Vector3(0, 0, 1)
      : new THREE.Vector3(-0.6, 0.65, 1.25)).normalize();
    if (mode === "contact" || box.isEmpty())
      box.setFromCenterAndSize(center, new THREE.Vector3(s, s, s));
    const right = new THREE.Vector3().crossVectors(new THREE.Vector3(0, 1, 0), direction).normalize(),
      up = new THREE.Vector3().crossVectors(direction, right),
      tangent = Math.tan(THREE.MathUtils.degToRad(this.camera.fov / 2));
    let distance = 0;
    // Fit every corner in camera coordinates, including depth. A scalar
    // multiplier of the largest world-axis span clips diagonal/wide assemblies.
    for (const x of [box.min.x, box.max.x])
      for (const y of [box.min.y, box.max.y])
        for (const z of [box.min.z, box.max.z]) {
          const delta = new THREE.Vector3(x, y, z).sub(center),
            depth = delta.dot(direction);
          distance = Math.max(distance,
            depth + Math.abs(delta.dot(right)) / (tangent * aspect),
            depth + Math.abs(delta.dot(up)) / tangent);
        }
    distance = Math.max(distance * 1.12, 1);
    this.controls.minDistance = Math.max(.1, s * .02);
    this.controls.maxDistance = distance * 20;
    this.camera.far = Math.max(10000, distance * 10);
    this.camera.updateProjectionMatrix();
    moveCamera(
      this,
      center,
      direction.multiplyScalar(distance).add(center),
    );
    this.camera.up.set(0, 1, 0);
    this.controls.update();
  }
  animate(now) {
    const dt = Math.max(0, (now - this.last) / 1000);
    this.last = now;
    if (this.result && this.playing && !document.hidden && this.inViewport) {
      this.theta =
        (this.theta +
          (dt * this.scale * this.result.input.speed * 2 * Math.PI) / 60) %
        (2 * Math.PI * this.result.chosen.z2);
      this.gears[0].rotation.z = this.pinionPhase + this.theta;
      this.gears[1].rotation.z =
        this.phase +
        ((this.result.chosen.meshType === "internal" ? 1 : -1) * this.theta) /
          this.result.chosen.u;
    }
    this.tickEffects(dt);
    this.controls.update(dt);
    if (!document.hidden && this.inViewport)
      this.renderer.render(this.scene, this.camera);
    requestAnimationFrame(this.animate);
  }
}
