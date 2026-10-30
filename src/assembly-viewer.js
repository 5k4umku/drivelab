import { prepareSceneEffects, moveCamera } from "./scene-effects.js";
import * as THREE from "three";
import { GearViewer, gearGeometry } from "./viewer.js";

const colors = [0x75c9ab, 0x98b8ce, 0xd6b383, 0xac9ece, 0x88bfc4, 0xcda3a3];
export class AssemblyViewer extends GearViewer {
  update(result) {
    this.result = result;
    this.theta = 0;
    for (const child of [...this.model.children]) {
      this.model.remove(child);
      child.traverse((o) => {
        o.geometry?.dispose();
        o.material?.dispose();
      });
    }
    this.rotors = [];
    const material = (color) =>
      new THREE.MeshStandardMaterial({
        color,
        metalness: 0.35,
        roughness: 0.4,
      });
    for (const shaft of result.shafts) {
      const rotor = new THREE.Group();
      rotor.position.set(shaft.x, shaft.y, 0);
      this.model.add(rotor);
      this.rotors.push(rotor);
      const body = new THREE.Mesh(
        new THREE.CylinderGeometry(
          shaft.diameter / 2,
          shaft.diameter / 2,
          shaft.zMax - shaft.zMin,
          24,
        ),
        material(0x566e7d),
      );
      body.rotation.x = Math.PI / 2;
      body.position.z = (shaft.zMax + shaft.zMin) / 2;
      rotor.add(body);
      for (const name of ["A", "B"]) {
        const support = new THREE.Mesh(
          new THREE.TorusGeometry(
            shaft.diameter * 0.78,
            shaft.diameter * 0.23,
            8,
            28,
          ),
          material(name === shaft.locating ? 0xc99850 : 0x566477),
        );
        support.position.set(shaft.x, shaft.y, shaft[name].z);
        this.model.add(support);
        if (shaft.bearing === "roller") {
          const collar = new THREE.Mesh(
            new THREE.TorusGeometry(
              shaft.diameter * 0.8,
              shaft.diameter * 0.1,
              4,
              28,
            ),
            material(0xaac1cf),
          );
          collar.position.set(
            shaft.x,
            shaft.y,
            shaft[name].z + shaft.diameter * 0.22,
          );
          this.model.add(collar);
        }
      }
    }
    for (const gear of result.gears) {
      const stage = result.stages[gear.stage];
      const c = stage.result.chosen;
      const mesh = new THREE.Mesh(
        gearGeometry(
          c,
          gear.side,
          gear.width,
          stage.result.input.gearType,
          stage.hand === "left" ? -1 : 1,
        ),
        material(colors[gear.stage % colors.length]),
      );
      mesh.position.z = gear.z;
      mesh.userData.explodeDirection = new THREE.Vector3(
        0,
        0,
        (gear.side === 1 ? -1 : 1) * (gear.stage + 1) * gear.width * 2,
      );
      mesh.rotation.z =
        (stage.angle * Math.PI) / 180 +
        (gear.side === 2
          ? Math.PI - Math.PI / c.z2
          : c.meshType === "internal"
            ? Math.PI
            : 0);
      this.rotors[gear.shaft].add(mesh);
    }
    if (result.motor) {
      const s = result.shafts[0],
        m = result.motor,
        r = m.frame * 0.78,
        length = m.frame * 2.4,
        z = s.zMin - length / 2 - 25;
      const body = new THREE.Mesh(
        new THREE.CylinderGeometry(r, r, length, 32),
        material(0x527082),
      );
      body.rotation.x = Math.PI / 2;
      body.position.set(s.x, s.y, z);
      this.model.add(body);
      for (let i = 0; i < 10; i++) {
        const rib = new THREE.Mesh(
          new THREE.TorusGeometry(r + 2, 2, 4, 32),
          material(0x668597),
        );
        rib.position.set(s.x, s.y, z - length * 0.4 + (length * 0.8 * i) / 9);
        this.model.add(rib);
      }
      const feet = new THREE.Mesh(
        new THREE.BoxGeometry(r * 2.1, 10, length * 0.7),
        material(0x3c596c),
      );
      feet.position.set(s.x, s.y - r, z);
      this.model.add(feet);
      const coupling = new THREE.Mesh(
        new THREE.CylinderGeometry(s.diameter * 0.8, s.diameter * 0.8, 35, 20),
        material(0xb4a176),
      );
      coupling.rotation.x = Math.PI / 2;
      coupling.position.z = s.zMin - 12;
      this.rotors[0].add(coupling);
    }
    const b = result.bounds;
    const cameraBounds = [...b];
    if (result.motor) {
      const s = result.shafts[0],
        m = result.motor;
      cameraBounds[4] = Math.min(b[4], s.zMin - m.frame * 2.4 - 25);
      cameraBounds[0] = Math.min(b[0], s.x - m.frame);
      cameraBounds[1] = Math.max(b[1], s.x + m.frame);
      cameraBounds[2] = Math.min(b[2], s.y - m.frame);
      cameraBounds[3] = Math.max(b[3], s.y + m.frame);
    }
    this.center = new THREE.Vector3(
      (cameraBounds[0] + cameraBounds[1]) / 2,
      (cameraBounds[2] + cameraBounds[3]) / 2,
      (cameraBounds[4] + cameraBounds[5]) / 2,
    );
    this.extent = Math.max(
      cameraBounds[1] - cameraBounds[0],
      cameraBounds[3] - cameraBounds[2],
      cameraBounds[5] - cameraBounds[4],
      100,
    );
    const clearance = result.project.housing?.clearance ?? 20,
      mode = result.project.housing?.mode ?? "contour";
    const box = new THREE.BoxGeometry(
      b[1] - b[0] + 2 * clearance,
      b[3] - b[2] + 2 * clearance,
      b[5] - b[4] + 2 * clearance,
    );
    const housingCenter = new THREE.Vector3(
      (b[0] + b[1]) / 2,
      (b[2] + b[3]) / 2,
      (b[4] + b[5]) / 2,
    );
    if (mode === "transparent") {
      const shell = new THREE.Mesh(
        box.clone(),
        new THREE.MeshStandardMaterial({
          color: 0x8ca99f,
          transparent: true,
          opacity: 0.1,
          depthWrite: false,
          side: THREE.DoubleSide,
        }),
      );
      shell.position.copy(housingCenter);
      this.model.add(shell);
    }
    this.envelope = new THREE.LineSegments(
      new THREE.EdgesGeometry(box),
      new THREE.LineBasicMaterial({
        color: 0x7ba79a,
        transparent: true,
        opacity: 0.25,
      }),
    );
    box.dispose();
    this.envelope.position.copy(housingCenter);
    this.envelope.visible = mode !== "hidden" && (this.showEnvelope ?? true);
    this.model.add(this.envelope);
    this.view(this.viewMode || "iso");
    prepareSceneEffects(this);
    this.resize();
  }
  view(mode) {
    this.viewMode = mode;
    const center = this.center || new THREE.Vector3(),
      s = this.extent || 450;

    const aspect =
      this.container.clientWidth / Math.max(1, this.container.clientHeight) ||
      1;
    const distance = (s * 1.8) / Math.min(1, Math.max(0.35, aspect));
    this.camera.far = Math.max(10000, distance * 10);
    this.camera.updateProjectionMatrix();
    const targetPosition = center
      .clone()
      .add(
        mode === "front"
          ? new THREE.Vector3(0, 0, distance)
          : new THREE.Vector3(-0.7, 0.65, 1)
              .normalize()
              .multiplyScalar(distance),
      );
    moveCamera(this, center, targetPosition);
    this.camera.up.set(0, 1, 0);
    this.controls.update();
  }
  animate(now) {
    const dt = Math.min((now - this.last) / 1000, 0.05);
    this.last = now;
    if (this.result && this.playing && !document.hidden && this.inViewport) {
      this.theta += (dt * this.scale * 2 * Math.PI) / 60;
      for (let i = 0; i < this.rotors.length; i++)
        this.rotors[i].rotation.z =
          this.theta * this.result.shafts[i].signedSpeed;
    }
    this.tickEffects(dt);
    this.controls.update();
    if (!document.hidden && this.inViewport)
      this.renderer.render(this.scene, this.camera);
    requestAnimationFrame(this.animate);
  }
}
