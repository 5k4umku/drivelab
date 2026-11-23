import {
  installSceneEffects,
  prepareSceneEffects,
  moveCamera,
} from "./scene-effects.js";
import * as THREE from "three";
import { OrbitControls } from "../vendor/three/OrbitControls.js";

/** Rendering only: all engineering dimensions and speeds come from Python.
 * Involute flanks sampled in transverse section; root transitions are radial.
 * The display has zero backlash and no claim of manufacturing-ready geometry.
 */
function profile(c, i) {
  const z = c["z" + i],
    rp = c["d" + i] / 2,
    rb = c["db" + i] / 2,
    ra = c["da" + i] / 2,
    rf = c["df" + i] / 2;
  const alpha = (c.alphaT * Math.PI) / 180,
    invPitch = Math.tan(alpha) - alpha;
  const points = [],
    pitch = (2 * Math.PI) / z,
    half = (Math.PI / 2 + 2 * (c["x" + i] || 0) * Math.tan(Math.PI / 9)) / z;
  const inv = (r) => {
    const a = Math.acos(Math.min(1, rb / r));
    return Math.tan(a) - a;
  };
  const angle = (r) => half + invPitch - inv(r);
  const pt = (r, a) =>
    points.push(new THREE.Vector2(r * Math.cos(a), r * Math.sin(a)));
  const start = Math.max(rf, rb);
  for (let tooth = 0; tooth < z; tooth++) {
    const center = tooth * pitch;
    pt(rf, center - angle(start));
    for (let j = 0; j <= 7; j++) {
      const r = start + ((ra - start) * j) / 7;
      pt(r, center - angle(r));
    }
    for (let j = 1; j <= 3; j++)
      pt(ra, center - angle(ra) + (2 * angle(ra) * j) / 3);
    for (let j = 6; j >= 0; j--) {
      const r = start + ((ra - start) * j) / 7;
      pt(r, center + angle(r));
    }
    pt(rf, center + angle(start));
    for (let j = 1; j <= 3; j++)
      pt(rf, center + angle(start) + ((pitch - 2 * angle(start)) * j) / 3);
  }
  return { points, rp };
}
export function gearGeometry(c, i, width, type, hand = 1) {
  if (c.meshType === "internal" && i === 2)
    return ringGeometry(c, width, type, hand);
  const { points, rp } = profile(c, i),
    count = points.length,
    segments = type === "spur" ? 1 : 20;
  const positions = [],
    indices = [],
    twist =
      (Math.tan((c.beta * Math.PI) / 180) / rp) * (i === 1 ? 1 : -1) * hand;
  for (let layer = 0; layer <= segments; layer++) {
    const depth = width * (layer / segments - 0.5);
    const a = (type === "herringbone" ? Math.abs(depth) : depth) * twist;
    for (const pt of points)
      positions.push(
        pt.x * Math.cos(a) - pt.y * Math.sin(a),
        pt.x * Math.sin(a) + pt.y * Math.cos(a),
        depth,
      );
  }
  for (let layer = 0; layer < segments; layer++)
    for (let j = 0; j < count; j++) {
      const a = layer * count + j,
        b = layer * count + ((j + 1) % count),
        c2 = a + count,
        d = b + count;
      indices.push(a, b, d, a, d, c2);
    }
  const faces = THREE.ShapeUtils.triangulateShape(points, []);
  for (const [a, b, c2] of faces) {
    indices.push(c2, b, a);
    indices.push(
      a + segments * count,
      b + segments * count,
      c2 + segments * count,
    );
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geo.setIndex(indices);
  geo.computeVertexNormals();
  return geo;
}

/** Inward involute teeth. The bore is a real hole, not a translucent disc.
 * Root transitions are schematic; manufacturing interference is not checked. */
function ringGeometry(c, width, type, hand) {
  const rb = c.db2 / 2,
    ra = c.da2 / 2,
    rf = c.df2 / 2,
    rp = c.d2 / 2;
  const alpha = (c.alphaT * Math.PI) / 180,
    invPitch = Math.tan(alpha) - alpha;
  const pitch = (2 * Math.PI) / c.z2,
    half = Math.PI / (2 * c.z2),
    inner = [];
  const angle = (r) => {
    const a = Math.acos(rb / r);
    return half - invPitch + Math.tan(a) - a;
  };
  const point = (r, a) =>
    inner.push(new THREE.Vector2(r * Math.cos(a), r * Math.sin(a)));
  for (let tooth = 0; tooth < c.z2; tooth++) {
    const center = tooth * pitch;
    for (let j = 0; j <= 7; j++) {
      const r = rf + ((ra - rf) * j) / 7;
      point(r, center - angle(r));
    }
    for (let j = 1; j <= 3; j++)
      point(ra, center - angle(ra) + (2 * angle(ra) * j) / 3);
    for (let j = 1; j <= 7; j++) {
      const r = ra + ((rf - ra) * j) / 7;
      point(r, center + angle(r));
    }
    for (let j = 1; j < 4; j++)
      point(rf, center + angle(rf) + ((pitch - 2 * angle(rf)) * j) / 4);
  }
  inner.reverse();
  const outer = Array.from(
    { length: 128 },
    (_, j) =>
      new THREE.Vector2(
        (c.outerDiameter / 2) * Math.cos((j * 2 * Math.PI) / 128),
        (c.outerDiameter / 2) * Math.sin((j * 2 * Math.PI) / 128),
      ),
  );
  const points = [...outer, ...inner],
    count = points.length,
    segments = type === "spur" ? 1 : 20;
  const positions = [],
    indices = [],
    twist = (Math.tan((c.beta * Math.PI) / 180) / rp) * hand;
  for (let layer = 0; layer <= segments; layer++) {
    const depth = width * (layer / segments - 0.5),
      a = (type === "herringbone" ? Math.abs(depth) : depth) * twist;
    for (const p of points)
      positions.push(
        p.x * Math.cos(a) - p.y * Math.sin(a),
        p.x * Math.sin(a) + p.y * Math.cos(a),
        depth,
      );
  }
  for (const [start, length] of [
    [0, outer.length],
    [outer.length, inner.length],
  ])
    for (let layer = 0; layer < segments; layer++)
      for (let j = 0; j < length; j++) {
        const a = layer * count + start + j,
          b = layer * count + start + ((j + 1) % length);
        indices.push(a, b, b + count, a, b + count, a + count);
      }
  for (const [a, b, d] of THREE.ShapeUtils.triangulateShape(outer, [inner])) {
    indices.push(
      d,
      b,
      a,
      a + segments * count,
      b + segments * count,
      d + segments * count,
    );
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geo.setIndex(indices);
  geo.computeVertexNormals();
  return geo;
}
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
      const gear = new THREE.Mesh(
        gearGeometry(
          c,
          i,
          result.b,
          result.input.gearType,
          result.assemblyContext?.hand === "left" ? -1 : 1,
        ),
        material,
      );
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
      ]) {
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
    this.phase = Math.PI - Math.PI / c.z2;
    this.pinionPhase = c.meshType === "internal" ? Math.PI : 0;
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
