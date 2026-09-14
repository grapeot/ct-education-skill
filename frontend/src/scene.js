import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { sliceCorners } from "./mapping.js";
import { firstUnclippedHit } from "./picking.js";
import { FALLBACK_LAYER_COLORS } from "./state.js";
import { isCssHexColor } from "./validate.js";

export function detectWebGL() {
  try {
    const probe = document.createElement("canvas");
    return Boolean(probe.getContext("webgl2") || probe.getContext("webgl"));
  } catch {
    return false;
  }
}

function layerColor(layer, order) {
  if (isCssHexColor(layer.color)) return layer.color;
  return FALLBACK_LAYER_COLORS[order % FALLBACK_LAYER_COLORS.length];
}

function makeTextSprite(text, color) {
  const canvas = document.createElement("canvas");
  canvas.width = 128;
  canvas.height = 64;
  const context = canvas.getContext("2d");
  context.fillStyle = color;
  context.font = "600 28px ui-sans-serif, system-ui, sans-serif";
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.fillText(text, 64, 32);
  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthTest: false,
  });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(16, 8, 1);
  sprite.renderOrder = 4;
  return sprite;
}

function easeInOut(t) {
  return t < 0.5 ? 2 * t * t : 1 - (2 * t - 2) ** 2 / 2;
}

export class ObservatoryScene {
  constructor(canvas, { bounds, affineRas, shape }) {
    this.canvas = canvas;
    this.bounds = bounds;
    this.affineRas = affineRas;
    this.shape = shape;
    this.scripted = false;
    this.layerMeshes = new Map();
    this.annotationGroup = new THREE.Group();
    this.pickables = [];
    this.clipPlane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
    this.tourAnim = null;

    const renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: false,
      preserveDrawingBuffer: true,
      powerPreference: "high-performance",
    });
    if (!renderer.getContext()) {
      renderer.dispose();
      throw new Error("webgl");
    }
    renderer.setClearColor(0x0c1018, 1);
    renderer.localClippingEnabled = false;
    renderer.shadowMap.enabled = false;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.NoToneMapping;
    this.renderer = renderer;

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0c1018);

    this.camera = new THREE.PerspectiveCamera(42, 1, 1, 20000);
    this.camera.up.set(0, 0, 1);

    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.rotateSpeed = 0.68;
    this.controls.zoomSpeed = 0.9;
    this.controls.panSpeed = 0.6;
    this.controls.screenSpacePanning = true;
    if (THREE.TOUCH) {
      this.controls.touches.ONE = THREE.TOUCH.ROTATE;
      this.controls.touches.TWO = THREE.TOUCH.DOLLY_PAN;
    }

    this.scene.add(new THREE.HemisphereLight(0xf3ead8, 0x12161c, 0.42));
    this.scene.add(new THREE.AmbientLight(0xf3ead8, 0.16));
    const key = new THREE.DirectionalLight(0xfff6e8, 0.96);
    key.position.set(180, -220, 360);
    this.scene.add(key);
    const fill = new THREE.DirectionalLight(0x9bb7c9, 0.32);
    fill.position.set(-240, 160, 70);
    this.scene.add(fill);
    const rim = new THREE.DirectionalLight(0x7eb8b4, 0.14);
    rim.position.set(30, 260, -90);
    this.scene.add(rim);

    this._addBounds();
    this._addRasLabels();

    this.sliceGeometry = new THREE.BufferGeometry();
    this.sliceGeometry.setAttribute(
      "position",
      new THREE.BufferAttribute(new Float32Array(12), 3),
    );
    this.sliceGeometry.setAttribute(
      "uv",
      new THREE.BufferAttribute(new Float32Array([0, 0, 1, 0, 1, 1, 0, 1]), 2),
    );
    this.sliceGeometry.setIndex([0, 1, 2, 0, 2, 3]);
    this.sliceTexture = null;
    this.sliceMaterial = new THREE.MeshBasicMaterial({
      map: null,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.58,
      depthWrite: false,
      toneMapped: false,
    });
    this.sliceMesh = new THREE.Mesh(this.sliceGeometry, this.sliceMaterial);
    this.sliceMesh.userData = { type: "slice" };
    this.sliceMesh.renderOrder = 1;
    this.sliceMesh.visible = false;
    this.scene.add(this.sliceMesh);

    this.edgeGeom = new THREE.BufferGeometry();
    this.edgeGeom.setAttribute("position", new THREE.BufferAttribute(new Float32Array(12), 3));
    this.edgeGeom.setIndex([0, 1, 1, 2, 2, 3, 3, 0]);
    this.edgeLines = new THREE.LineSegments(
      this.edgeGeom,
      new THREE.LineBasicMaterial({ color: 0xf3ead8, transparent: true, opacity: 0.55 }),
    );
    this.edgeLines.visible = false;
    this.scene.add(this.edgeLines);

    this.selectionMarker = new THREE.Group();
    const mark = new THREE.Mesh(
      new THREE.SphereGeometry(1.4, 16, 12),
      new THREE.MeshBasicMaterial({ color: 0xf3ead8 }),
    );
    this.selectionMarker.add(mark);
    const axes = [
      [new THREE.Vector3(-8, 0, 0), new THREE.Vector3(8, 0, 0), 0xc4b5fd],
      [new THREE.Vector3(0, -8, 0), new THREE.Vector3(0, 8, 0), 0x2ec9c0],
      [new THREE.Vector3(0, 0, -8), new THREE.Vector3(0, 0, 8), 0xe8b86d],
    ];
    for (const [from, to, color] of axes) {
      const geom = new THREE.BufferGeometry().setFromPoints([from, to]);
      this.selectionMarker.add(new THREE.Line(geom, new THREE.LineBasicMaterial({ color })));
    }
    this.selectionMarker.visible = false;
    this.scene.add(this.selectionMarker);

    this.clipHelper = new THREE.PlaneHelper(this.clipPlane, 40, 0x2ec9c0);
    this.clipHelper.visible = false;
    this.scene.add(this.clipHelper);

    this.scene.add(this.annotationGroup);

    this.orbit = { target: [0, 0, 0], radius: 200, height: 40 };
    this.fitBounds();
    this.raycaster = new THREE.Raycaster();
    this.raycaster.params.Line = { threshold: 2.5 };
    this.pointer = new THREE.Vector2();
    this._loop = this._loop.bind(this);
    this.resize();
    this._raf = requestAnimationFrame(this._loop);
  }

  _addBounds() {
    const min = new THREE.Vector3(...this.bounds.min);
    const max = new THREE.Vector3(...this.bounds.max);
    const box = new THREE.Box3(min, max);
    const helper = new THREE.Box3Helper(box, 0x3a3f46);
    this.scene.add(helper);
    const size = max.clone().sub(min);
    const gridSize = Math.max(size.x, size.y, 1);
    const grid = new THREE.GridHelper(gridSize, 18, 0x2a3036, 0x161a1e);
    grid.rotation.x = Math.PI / 2;
    grid.position.set((min.x + max.x) / 2, (min.y + max.y) / 2, min.z);
    this.scene.add(grid);
  }

  _addRasLabels() {
    const [min, max] = [this.bounds.min, this.bounds.max];
    const cx = (min[0] + max[0]) / 2;
    const cy = (min[1] + max[1]) / 2;
    const cz = (min[2] + max[2]) / 2;
    const placements = [
      ["R", [max[0], cy, cz], "#f3ead8"],
      ["L", [min[0], cy, cz], "#f3ead8"],
      ["A", [cx, max[1], cz], "#f3ead8"],
      ["P", [cx, min[1], cz], "#f3ead8"],
      ["S", [cx, cy, max[2]], "#f3ead8"],
      ["I", [cx, cy, min[2]], "#f3ead8"],
    ];
    for (const [text, position, color] of placements) {
      const sprite = makeTextSprite(text, color);
      sprite.position.set(position[0], position[1], position[2]);
      this.scene.add(sprite);
    }
  }

  fitBounds() {
    const min = new THREE.Vector3(...this.bounds.min);
    const max = new THREE.Vector3(...this.bounds.max);
    const center = min.clone().add(max).multiplyScalar(0.5);
    const radius = max.clone().sub(min).length() * 0.5;
    const dist = Math.max(radius / Math.sin(THREE.MathUtils.degToRad(this.camera.fov) / 2) * 0.78, 40);
    const dir = new THREE.Vector3(0.62, -0.9, 0.42).normalize();
    this.camera.up.set(0, 0, 1);
    this.camera.position.copy(center).add(dir.multiplyScalar(dist));
    this.camera.near = Math.max(0.2, dist / 250);
    this.camera.far = dist * 24;
    this.camera.updateProjectionMatrix();
    this.controls.target.copy(center);
    this.controls.update();
    this.orbit = {
      target: [center.x, center.y, center.z],
      radius: dist * 0.72,
      height: Math.max(sizeZ(this.bounds) * 0.22, 12),
    };
    const span = Math.max(max.x - min.x, max.y - min.y, max.z - min.z);
    this.clipHelper.scale.setScalar(span);
  }

  unionLayerBounds(ids) {
    let box = null;
    for (const id of ids || []) {
      const mesh = this.layerMeshes.get(id);
      if (!mesh || !mesh.visible) continue;
      mesh.geometry.computeBoundingBox();
      const next = mesh.geometry.boundingBox;
      if (!next) continue;
      box = box ? box.union(next.clone()) : next.clone();
    }
    return box;
  }

  fitBox(box, pad = 1.22) {
    if (!box) {
      this.fitBounds();
      return;
    }
    const min = box.min;
    const max = box.max;
    const center = min.clone().add(max).multiplyScalar(0.5);
    const radius = Math.max(max.clone().sub(min).length() * 0.5, 8);
    const dist = Math.max(
      (radius / Math.sin(THREE.MathUtils.degToRad(this.camera.fov) / 2)) * pad,
      40,
    );
    const dir = new THREE.Vector3(0.62, -0.9, 0.42).normalize();
    this.flyTo([center.x, center.y, center.z], dist);
    this.orbit.height = Math.max((max.z - min.z) * 0.2, 10);
    this.camera.near = Math.max(0.2, dist / 250);
    this.camera.far = dist * 24;
    this.camera.updateProjectionMatrix();
  }

  resize() {
    const width = Math.max(1, this.canvas.clientWidth);
    const height = Math.max(1, this.canvas.clientHeight);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
  }

  _loop() {
    this._raf = requestAnimationFrame(this._loop);
    if (this.scripted) return;
    if (this.tourAnim) this._stepTour();
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }

  _stepTour() {
    const anim = this.tourAnim;
    const t = easeInOut(Math.min(1, (performance.now() - anim.start) / anim.duration));
    this.camera.position.lerpVectors(anim.fromPos, anim.toPos, t);
    this.controls.target.lerpVectors(anim.fromTarget, anim.toTarget, t);
    this.camera.up.set(0, 0, 1);
    this.camera.lookAt(this.controls.target);
    if (t >= 1) {
      this.orbit.target = [this.controls.target.x, this.controls.target.y, this.controls.target.z];
      this.tourAnim = null;
      if (anim.done) anim.done();
    }
  }

  jumpTo(target, distance) {
    const toTarget = new THREE.Vector3(...target);
    const currentDir = this.camera.position.clone().sub(this.controls.target);
    if (currentDir.lengthSq() < 1e-6) currentDir.set(0.62, -0.9, 0.42);
    currentDir.normalize();
    this.tourAnim = null;
    this.controls.target.copy(toTarget);
    this.camera.up.set(0, 0, 1);
    this.camera.position.copy(toTarget).add(currentDir.multiplyScalar(distance));
    this.orbit.target = [target[0], target[1], target[2]];
    this.orbit.radius = distance;
    this.controls.update();
  }

  flyTo(target, distance) {
    const toTarget = new THREE.Vector3(...target);
    const currentDir = this.camera.position.clone().sub(this.controls.target);
    if (currentDir.lengthSq() < 1e-6) currentDir.set(0.62, -0.9, 0.42);
    currentDir.normalize();
    const toPos = toTarget.clone().add(currentDir.multiplyScalar(distance));
    this.tourAnim = {
      start: performance.now(),
      duration: 1100,
      fromPos: this.camera.position.clone(),
      toPos,
      fromTarget: this.controls.target.clone(),
      toTarget,
    };
    this.orbit.target = [target[0], target[1], target[2]];
    this.orbit.radius = distance;
  }

  renderFrame(t) {
    this.scripted = true;
    this.controls.enabled = false;
    const [tx, ty, tz] = this.orbit.target;
    const azimuth = t * 0.35;
    this.camera.up.set(0, 0, 1);
    this.camera.position.set(
      tx + this.orbit.radius * Math.cos(azimuth),
      ty + this.orbit.radius * Math.sin(azimuth),
      tz + this.orbit.height,
    );
    this.camera.lookAt(tx, ty, tz);
    this.renderer.render(this.scene, this.camera);
  }

  setScripted(value) {
    this.scripted = Boolean(value);
    this.controls.enabled = !this.scripted;
  }

  setOrbit({ target, radius, height }) {
    if (target) this.orbit.target = target.slice();
    if (Number.isFinite(radius)) this.orbit.radius = radius;
    if (Number.isFinite(height)) this.orbit.height = height;
  }

  capturePng() {
    return this.renderer.domElement.toDataURL("image/png");
  }

  setSlicePlane(axis, index, canvas) {
    const corners = sliceCorners(axis, index, this.shape, this.affineRas);
    const positions = this.sliceGeometry.getAttribute("position");
    for (let i = 0; i < 4; i += 1) {
      positions.setXYZ(i, corners[i][0], corners[i][1], corners[i][2]);
    }
    positions.needsUpdate = true;
    this.sliceGeometry.computeVertexNormals();
    this.sliceGeometry.computeBoundingSphere();
    const edge = this.edgeGeom.getAttribute("position");
    for (let i = 0; i < 4; i += 1) {
      edge.setXYZ(i, corners[i][0], corners[i][1], corners[i][2]);
    }
    edge.needsUpdate = true;
    if (canvas) {
      if (this.sliceTexture) this.sliceTexture.dispose();
      const texture = new THREE.CanvasTexture(canvas);
      texture.flipY = false;
      texture.colorSpace = THREE.NoColorSpace;
      texture.minFilter = THREE.NearestFilter;
      texture.magFilter = THREE.NearestFilter;
      texture.generateMipmaps = false;
      texture.needsUpdate = true;
      this.sliceTexture = texture;
      this.sliceMaterial.map = texture;
      this.sliceMaterial.needsUpdate = true;
    }
  }

  setSlice3dVisible(visible) {
    const on = Boolean(visible);
    this.sliceMesh.visible = on;
    this.edgeLines.visible = on;
    this._rebuildPickables();
  }

  setSelectionMarker(ras) {
    if (!ras) {
      this.selectionMarker.visible = false;
      return;
    }
    this.selectionMarker.visible = true;
    this.selectionMarker.position.set(ras[0], ras[1], ras[2]);
  }

  setClip({ enabled, axis, value }) {
    this.renderer.localClippingEnabled = Boolean(enabled);
    this.clipHelper.visible = Boolean(enabled);
    const normal =
      axis === "x"
        ? new THREE.Vector3(1, 0, 0)
        : axis === "y"
          ? new THREE.Vector3(0, 1, 0)
          : new THREE.Vector3(0, 0, 1);
    const point =
      axis === "x"
        ? new THREE.Vector3(value, 0, 0)
        : axis === "y"
          ? new THREE.Vector3(0, value, 0)
          : new THREE.Vector3(0, 0, value);
    this.clipPlane.setFromNormalAndCoplanarPoint(normal, point);
    const planes = enabled ? [this.clipPlane] : [];
    for (const mesh of this.layerMeshes.values()) {
      mesh.material.clippingPlanes = planes;
      mesh.material.needsUpdate = true;
    }
  }

  upsertLayer(layer, meshData, order) {
    this.removeLayer(layer.id);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(meshData.positions, 3),
    );
    geometry.setIndex(meshData.indices);
    geometry.computeVertexNormals();
    geometry.computeBoundingBox();
    const color = layerColor(layer, order);
    const kind = String(layer.id || "").toLowerCase();
    const airway = kind.includes("airway");
    const lung = kind.includes("lung");
    const material = new THREE.MeshStandardMaterial({
      color: new THREE.Color(color),
      roughness: airway ? 0.32 : lung ? 0.8 : 0.52,
      metalness: airway ? 0.14 : 0.04,
      transparent: true,
      opacity: layer.opacity,
      side: THREE.DoubleSide,
      depthWrite: layer.opacity > 0.92,
      clippingPlanes: this.renderer.localClippingEnabled ? [this.clipPlane] : [],
      clipShadows: false,
      emissive: new THREE.Color(color),
      emissiveIntensity: airway ? 0.2 : lung ? 0.025 : 0.05,
      polygonOffset: true,
      polygonOffsetFactor: 1,
      polygonOffsetUnits: 1,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.userData = { type: "layer", id: layer.id };
    mesh.visible = layer.visible;
    this.layerMeshes.set(layer.id, mesh);
    this.scene.add(mesh);
    this._rebuildPickables();
  }

  setLayerAppearance(id, { visible, opacity }) {
    const mesh = this.layerMeshes.get(id);
    if (!mesh) return;
    if (visible != null) mesh.visible = visible;
    if (opacity != null) {
      mesh.material.opacity = opacity;
      mesh.material.transparent = opacity < 0.999;
      mesh.material.depthWrite = opacity > 0.9;
      mesh.material.needsUpdate = true;
    }
    this._rebuildPickables();
  }

  removeLayer(id) {
    const mesh = this.layerMeshes.get(id);
    if (!mesh) return;
    this.scene.remove(mesh);
    mesh.geometry.dispose();
    mesh.material.dispose();
    this.layerMeshes.delete(id);
    this._rebuildPickables();
  }

  setAnnotations(annotations) {
    while (this.annotationGroup.children.length) {
      const child = this.annotationGroup.children[0];
      this.annotationGroup.remove(child);
      child.traverse((node) => {
        if (node.geometry) node.geometry.dispose();
        if (node.material) node.material.dispose();
      });
    }
    for (const annotation of annotations) {
      const group = new THREE.Group();
      group.position.set(...annotation.position_ras);
      group.userData = { type: "annotation", id: annotation.id };
      const radius = Math.max(Number(annotation.radius_mm) || 0, 0);
      if (radius > 0) {
        const ring = new THREE.Mesh(
          new THREE.RingGeometry(radius * 0.92, radius, 48),
          new THREE.MeshBasicMaterial({
            color: 0xe8b86d,
            side: THREE.DoubleSide,
            transparent: true,
            opacity: 0.95,
            depthTest: false,
          }),
        );
        const sphere = new THREE.Mesh(
          new THREE.SphereGeometry(radius, 24, 16),
          new THREE.MeshBasicMaterial({
            color: 0xe8b86d,
            wireframe: true,
            transparent: true,
            opacity: 0.7,
            depthTest: false,
          }),
        );
        group.add(ring, sphere);
      }
      const arm = 8;
      const locator = new THREE.LineSegments(
        new THREE.BufferGeometry().setFromPoints([
          new THREE.Vector3(-arm, 0, 0),
          new THREE.Vector3(arm, 0, 0),
          new THREE.Vector3(0, -arm, 0),
          new THREE.Vector3(0, arm, 0),
          new THREE.Vector3(0, 0, -arm),
          new THREE.Vector3(0, 0, arm),
        ]),
        new THREE.LineBasicMaterial({ color: 0xf3ead8, depthTest: false }),
      );
      locator.renderOrder = 5;
      group.add(locator);
      this.annotationGroup.add(group);
    }
    this._rebuildPickables();
  }

  _rebuildPickables() {
    this.pickables = [...this.annotationGroup.children];
    if (this.sliceMesh.visible) this.pickables.push(this.sliceMesh);
    for (const mesh of this.layerMeshes.values()) {
      if (mesh.visible) this.pickables.push(mesh);
    }
  }

  pick(clientX, clientY) {
    const rect = this.canvas.getBoundingClientRect();
    this.pointer.x = ((clientX - rect.left) / rect.width) * 2 - 1;
    this.pointer.y = -((clientY - rect.top) / rect.height) * 2 + 1;
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const hits = this.raycaster.intersectObjects(this.pickables, true);
    const plane = {
      normal: [this.clipPlane.normal.x, this.clipPlane.normal.y, this.clipPlane.normal.z],
      constant: this.clipPlane.constant,
    };
    const mapped = hits.map((hit) => {
      const material = hit.object.material;
      const planes = material && material.clippingPlanes;
      return {
        hit,
        point: [hit.point.x, hit.point.y, hit.point.z],
        materialClipped: Boolean(this.renderer.localClippingEnabled && planes && planes.length),
      };
    });
    const chosen = firstUnclippedHit(mapped, plane, this.renderer.localClippingEnabled);
    if (!chosen) return null;
    const hit = chosen.hit;
    let node = hit.object;
    while (node && !node.userData.type) node = node.parent;
    const type = node && node.userData.type;
    return {
      type: type || "layer",
      id: node && node.userData.id,
      point: [hit.point.x, hit.point.y, hit.point.z],
    };
  }

  meshCount() {
    return this.layerMeshes.size;
  }

  dispose() {
    cancelAnimationFrame(this._raf);
    this.controls.dispose();
    this.renderer.dispose();
  }
}

function sizeZ(bounds) {
  return Math.abs(bounds.max[2] - bounds.min[2]);
}
