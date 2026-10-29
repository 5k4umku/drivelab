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
      mesh.rotation.z =
        (stage.angle * Math.PI) / 180 +
        (gear.side === 2 ? Math.PI - Math.PI / c.z2 : 0);
      this.rotors[gear.shaft].add(mesh);
    }
    const b = result.bounds;
    this.center = new THREE.Vector3(
      (b[0] + b[1]) / 2,
      (b[2] + b[3]) / 2,
      (b[4] + b[5]) / 2,
    );
    this.extent = Math.max(b[1] - b[0], b[3] - b[2], b[5] - b[4], 100);
    const box = new THREE.BoxGeometry(
      b[1] - b[0] + 35,
      b[3] - b[2] + 35,
      b[5] - b[4] + 20,
    );
    this.envelope = new THREE.LineSegments(
      new THREE.EdgesGeometry(box),
      new THREE.LineBasicMaterial({
        color: 0x7ba79a,
        transparent: true,
        opacity: 0.25,
      }),
    );
    box.dispose();
    this.envelope.position.copy(this.center);
    this.envelope.visible = this.showEnvelope ?? true;
    this.model.add(this.envelope);
    this.view(this.viewMode || "iso");
    this.resize();
  }
  view(mode) {
    this.viewMode = mode;
    const center = this.center || new THREE.Vector3(),
      s = this.extent || 450;
    this.controls.target.copy(center);
    const aspect =
      this.container.clientWidth / Math.max(1, this.container.clientHeight);
    const distance = (s * 1.8) / Math.min(1, aspect);
    this.camera.far = Math.max(10000, distance * 10);
    this.camera.updateProjectionMatrix();
    this.camera.position
      .copy(center)
      .add(
        mode === "front"
          ? new THREE.Vector3(0, 0, distance)
          : new THREE.Vector3(-0.7, 0.65, 1)
              .normalize()
              .multiplyScalar(distance),
      );
    this.camera.up.set(0, 1, 0);
    this.controls.update();
  }
  animate(now) {
    const dt = Math.min((now - this.last) / 1000, 0.05);
    this.last = now;
    if (this.result && this.playing && !document.hidden) {
      this.theta += (dt * this.scale * 2 * Math.PI) / 60;
      for (let i = 0; i < this.rotors.length; i++)
        this.rotors[i].rotation.z =
          this.theta * this.result.shafts[i].signedSpeed;
    }
    this.controls.update();
    if (!document.hidden) this.renderer.render(this.scene, this.camera);
    requestAnimationFrame(this.animate);
  }
}
