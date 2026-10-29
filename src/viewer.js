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
    half = Math.PI / (2 * z);
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
function gearGeometry(c, i, width, type) {
  const { points, rp } = profile(c, i),
    count = points.length,
    segments = type === "spur" ? 1 : 20;
  const positions = [],
    indices = [],
    twist = (Math.tan((c.beta * Math.PI) / 180) / rp) * (i === 1 ? 1 : -1);
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
export class GearViewer {
  constructor(container) {
    this.container = container;
    this.playing = !matchMedia("(prefers-reduced-motion: reduce)").matches;
    this.scale = 0.012;
    this.theta = 0;
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(34, 1, 0.1, 10000);
    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: "high-performance",
    });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.setClearColor(0, 0);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.replaceChildren(this.renderer.domElement);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.075;
    this.controls.enablePan = true;
    this.scene.add(new THREE.HemisphereLight(0xe8faff, 0x425663, 3));
    for (const [x, y, z, power] of [
      [-250, 350, 400, 4],
      [350, -120, -300, 3],
    ]) {
      const l = new THREE.DirectionalLight(0xffffff, power);
      l.position.set(x, y, z);
      this.scene.add(l);
    }
    this.model = new THREE.Group();
    this.scene.add(this.model);
    this.lines = new THREE.Group();
    this.model.add(this.lines);
    this.lines.visible = false;
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
    const offset = (c.d2 / 2 - c.d1 / 2) / 2; // camera centered on overall envelope, not the pitch point
    this.gears = [];
    for (const i of [1, 2]) {
      const group = new THREE.Group();
      group.position.x = (i === 1 ? -c.a / 2 : c.a / 2) - offset;
      this.model.add(group);
      this.gears.push(group);
      const material = new THREE.MeshStandardMaterial({
        color: i === 1 ? 0x75c9ab : 0xa7bdca,
        metalness: 0.45,
        roughness: 0.38,
      });
      const gear = new THREE.Mesh(
        gearGeometry(c, i, result.b, result.input.gearType),
        material,
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
        new THREE.MeshStandardMaterial({
          color: 0x506878,
          metalness: 0.5,
          roughness: 0.4,
        }),
      );
      shaft.rotation.x = Math.PI / 2;
      group.add(shaft);
      const mark = new THREE.Mesh(
        new THREE.BoxGeometry(c["d" + i] * 0.25, c.m * 0.7, 0.8),
        new THREE.MeshBasicMaterial({ color: i === 1 ? 0xd8ffed : 0xe4f0f7 }),
      );
      mark.position.set(c["d" + i] * 0.23, 0, result.b / 2 + 0.7);
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
    this.gears[1].rotation.z = this.phase;
    this.extent = c.da1 / 2 + c.a + c.da2 / 2;
    this.view("iso");
    this.resize();
  }
  view(mode) {
    const s = this.extent || 450;
    this.controls.target.set(0, 0, 0);
    this.camera.position.set(
      mode === "front" ? 0 : -s * 0.6,
      mode === "front" ? 0 : s * 0.65,
      mode === "front" ? s * 1.7 : s * 1.25,
    );
    this.camera.up.set(0, 1, 0);
    this.controls.update();
  }
  animate(now) {
    const dt = Math.min((now - this.last) / 1000, 0.05);
    this.last = now;
    if (this.result && this.playing && !document.hidden) {
      this.theta =
        (this.theta +
          (dt * this.scale * this.result.input.speed * 2 * Math.PI) / 60) %
        (2 * Math.PI * this.result.chosen.z2);
      this.gears[0].rotation.z = this.theta;
      this.gears[1].rotation.z = this.phase - this.theta / this.result.chosen.u;
    }
    this.controls.update();
    if (!document.hidden) this.renderer.render(this.scene, this.camera);
    requestAnimationFrame(this.animate);
  }
}
