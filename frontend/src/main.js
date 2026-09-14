import { blobToCanvas, createApi } from "./api.js";
import { rasToVoxel, voxelToRas } from "./affine.js";
import { copy } from "./copy.js";
import {
  sliceOrientationLabels,
  slicePixelToVoxel,
  voxelToSlicePixel,
} from "./mapping.js";
import { drawSliceOverlay, drawSliceView, eventToPixel } from "./overlay.js";
import { detectWebGL, ObservatoryScene } from "./scene.js";
import {
  createAppState,
  selectVoxel,
  setAxis,
  setClip,
  setDisplayWindow,
  setLayerLoaded,
  setLayerOpacity,
  setLayerVisible,
  setSliceIndex,
  setTourStep,
  expandTour,
} from "./state.js";
import {
  hideFatal,
  mountApp,
  renderCandidates,
  renderLayers,
  renderOrientation,
  renderReadout,
  renderStats,
  renderTour,
  renderWarnings,
  showFatal,
  syncClipControls,
  syncSliceControls,
} from "./ui.js";
import { validateManifest, validateMesh } from "./validate.js";

const api = createApi("");
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

let ready = false;
let manifest = null;
let state = null;
let scene = null;
let refs = null;
let sliceSource = null;
let pointerDown = null;
let resizeObserver = null;
let tourStops = [];

function statsPayload(status) {
  return {
    status: status || (state && state.status) || "loadingManifest",
    meshCount: state ? state.meshCount : 0,
    candidateCount: manifest ? manifest.annotations.length : 0,
    sliceCount: manifest && manifest.source ? manifest.source.slice_count : 0,
    warningCount: manifest && manifest.warnings ? manifest.warnings.length : 0,
    loaded: state ? state.layers.filter((layer) => layer.loaded).length : 0,
    total: state ? state.layers.length : 0,
  };
}

function refreshChrome() {
  if (!refs || !state || !manifest) return;
  renderStats(refs, statsPayload(state.status));
  renderReadout(refs, state.selection);
  syncSliceControls(refs, state, manifest.shape);
  syncClipControls(refs, state, manifest.bounds_ras);
}

function overlayPixel() {
  if (!state || !state.selection || state.selection.i == null) return null;
  return voxelToSlicePixel(state.axis, state.selection);
}

function paintSlice() {
  if (!refs || !sliceSource || !manifest) return;
  drawSliceView(refs["slice-canvas"], sliceSource);
  drawSliceOverlay(refs["slice-overlay"], {
    sourceWidth: sliceSource.width,
    sourceHeight: sliceSource.height,
    pixel: overlayPixel(),
    annotations: manifest.annotations,
    axis: state.axis,
    index: state.index[state.axis],
    affineRas: manifest.affine_ras,
    shape: manifest.shape,
  });
  renderOrientation(
    refs,
    sliceOrientationLabels(state.axis, state.index[state.axis], manifest.shape, manifest.affine_ras),
  );
}

async function refreshSlice() {
  if (!manifest || !state) return;
  state.status = "loadingSlice";
  refreshChrome();
  try {
    const blob = await api.slice({
      axis: state.axis,
      index: state.index[state.axis],
      wc: state.wc,
      ww: state.ww,
    });
    if (!blob) return;
    sliceSource = await blobToCanvas(blob);
    paintSlice();
    if (scene) scene.setSlicePlane(state.axis, state.index[state.axis], sliceSource);
  } catch (caught) {
    state.status = caught && caught.code === "sliceFailed" ? "ready" : "ready";
    refs.stats.textContent = `${copy.errors.sliceFailed} | ${refs.stats.textContent}`;
  }
  if (state.status === "loadingSlice") state.status = "ready";
  refreshChrome();
}

async function applyVoxelSelection(i, j, k, rasHint) {
  state = selectVoxel(state, i, j, k, manifest.shape);
  if (state.selection.error === "outOfBounds") {
    if (scene) scene.setSelectionMarker(rasHint || null);
    refreshChrome();
    paintSlice();
    return state.selection;
  }
  try {
    const voxel = await api.voxel(state.selection.i, state.selection.j, state.selection.k);
    state.selection = {
      ...state.selection,
      hu: voxel.hu,
      lps: voxel.lps,
      ras: voxel.ras || voxelToRas(manifest.affine_ras, state.selection.i, state.selection.j, state.selection.k),
    };
  } catch {
    state.selection = {
      ...state.selection,
      error: "voxelError",
      ras: voxelToRas(manifest.affine_ras, state.selection.i, state.selection.j, state.selection.k),
    };
  }
  if (scene) scene.setSelectionMarker(state.selection.ras);
  await refreshSlice();
  refreshChrome();
  paintSlice();
  return state.selection;
}

async function selectRas(ras) {
  const fractional = rasToVoxel(manifest.affine_ras, ras);
  return applyVoxelSelection(fractional[0], fractional[1], fractional[2], ras);
}

async function selectSource(i, j, k) {
  if (!manifest) return null;
  return applyVoxelSelection(i, j, k, voxelToRas(manifest.affine_ras, i, j, k));
}

function lookAt(target, distance) {
  if (!scene) return;
  if (reducedMotion) scene.jumpTo(target, distance);
  else scene.flyTo(target, distance);
}

function boundDistance() {
  const min = manifest.bounds_ras.min;
  const max = manifest.bounds_ras.max;
  return Math.max(
    Math.hypot(max[0] - min[0], max[1] - min[1], max[2] - min[2]) * 0.35,
    36,
  );
}

async function focusAnnotation(id, moveCamera = true) {
  const annotation = manifest.annotations.find((item) => item.id === id);
  if (!annotation) return;
  state.focusId = id;
  renderCandidates(refs, manifest.annotations, state.focusId, focusAnnotation);
  if (moveCamera) lookAt(annotation.position_ras, Math.max(annotation.radius_mm * 10, 28));
  await selectRas(annotation.position_ras);
}

async function goTour(index) {
  const tour = tourStops;
  state = setTourStep(state, index, tour.length);
  renderTour(refs, tour, state.tourIndex, goTour);
  if (state.tourIndex < 0) return;
  const stop = tour[state.tourIndex];
  if (Array.isArray(stop.layer_ids)) {
    for (const layer of state.layers) {
      const visible = stop.layer_ids.includes(layer.id);
      state = setLayerVisible(state, layer.id, visible);
      if (scene) scene.setLayerAppearance(layer.id, { visible });
    }
    renderLayers(refs, manifest, state, { onToggle, onOpacity });
  }
  if (stop.annotation_id) await focusAnnotation(stop.annotation_id, false);
  const target =
    stop.target_ras ||
    (stop.annotation_id &&
      manifest.annotations.find((item) => item.id === stop.annotation_id)?.position_ras);
  if (target) {
    lookAt(target, boundDistance());
    if (!stop.annotation_id) await selectRas(target);
  }
}

async function loadOneMesh(layer) {
  const local = state.layers.find((item) => item.id === layer.id);
  try {
    const data = await api.mesh(layer.id);
    const check = validateMesh(data, manifest.bounds_ras);
    if (!check.ok) {
      state = setLayerLoaded(state, layer.id, false, check.code);
      return;
    }
    scene.upsertLayer(
      { ...layer, opacity: local.opacity, visible: local.visible },
      data,
      local.order,
    );
    state = setLayerLoaded(state, layer.id, true);
  } catch {
    state = setLayerLoaded(state, layer.id, false, layer.mesh ? "invalidMesh" : "missingMesh");
  }
}

async function loadVisibleMeshes() {
  state.status = "loadingMeshes";
  refreshChrome();
  for (const layer of manifest.layers) {
    await loadOneMesh(layer);
    const local = state.layers.find((item) => item.id === layer.id);
    if (scene && local) scene.setLayerAppearance(layer.id, { visible: local.visible, opacity: local.opacity });
    renderLayers(refs, manifest, state, { onToggle, onOpacity });
    refreshChrome();
  }
}

async function onToggle(id, visible) {
  state = setLayerVisible(state, id, visible);
  const local = state.layers.find((item) => item.id === id);
  const layer = manifest.layers.find((item) => item.id === id);
  if (visible && layer && !local.loaded && !local.error) await loadOneMesh(layer);
  if (scene) scene.setLayerAppearance(id, { visible });
  renderLayers(refs, manifest, state, { onToggle, onOpacity });
  refreshChrome();
}

function onOpacity(id, opacity) {
  state = setLayerOpacity(state, id, opacity);
  if (scene) scene.setLayerAppearance(id, { opacity: state.layers.find((item) => item.id === id).opacity });
}

function exposeHooks() {
  window.ctEducation = {
    get ready() {
      return ready;
    },
    get tourStep() {
      return state ? state.tourIndex : -1;
    },
    get meshCount() {
      return scene ? scene.meshCount() : 0;
    },
    get tourLength() {
      return tourStops.length;
    },
    selectSource,
    renderFrame(t) {
      if (scene) scene.renderFrame(Number(t) || 0);
    },
    setTourStep: goTour,
    getSelection() {
      return state ? state.selection : null;
    },
    setOrbit(options) {
      if (scene) scene.setOrbit(options || {});
    },
    setScripted(value) {
      if (scene) scene.setScripted(value);
    },
    capturePng() {
      return scene ? scene.capturePng() : null;
    },
    resetView() {
      if (scene) scene.fitBounds();
    },
  };
}

function wire() {
  refs.retry.addEventListener("click", () => {
    loadCase();
  });
  refs.reset.addEventListener("click", () => {
    if (scene) scene.fitBounds();
  });
  refs["slice-axis"].addEventListener("change", async (event) => {
    if (event.target.name !== "slice-axis") return;
    state = setAxis(state, event.target.value);
    await refreshSlice();
  });
  refs["slice-index"].addEventListener("input", async () => {
    state = setSliceIndex(state, state.axis, Number(refs["slice-index"].value), manifest.shape);
    await refreshSlice();
  });
  refs.wc.addEventListener("input", async () => {
    state = setDisplayWindow(state, Number(refs.wc.value), state.ww);
    await refreshSlice();
  });
  refs.ww.addEventListener("input", async () => {
    state = setDisplayWindow(state, state.wc, Number(refs.ww.value));
    await refreshSlice();
  });
  refs["clip-enable"].addEventListener("change", () => {
    state = setClip(state, { enabled: refs["clip-enable"].checked });
    if (scene) scene.setClip(state.clip);
    refreshChrome();
  });
  refs["clip-axis"].addEventListener("change", (event) => {
    if (event.target.name !== "clip-axis") return;
    const axis = event.target.value;
    const axisIndex = axis === "x" ? 0 : axis === "y" ? 1 : 2;
    const mid = (manifest.bounds_ras.min[axisIndex] + manifest.bounds_ras.max[axisIndex]) / 2;
    state = setClip(state, { axis, value: mid });
    if (scene) scene.setClip(state.clip);
    refreshChrome();
  });
  refs["clip-pos"].addEventListener("input", () => {
    state = setClip(state, { value: Number(refs["clip-pos"].value) });
    if (scene) scene.setClip(state.clip);
  });
  refs["tour-prev"].addEventListener("click", () => {
    const next = Math.max(0, (state.tourIndex < 0 ? 0 : state.tourIndex) - 1);
    goTour(next);
  });
  refs["tour-next"].addEventListener("click", () => {
    const next = Math.min(tourStops.length - 1, state.tourIndex + 1);
    if (next >= 0) goTour(next);
  });
  refs["tour-exit"].addEventListener("click", () => {
    state = setTourStep(state, -1, tourStops.length);
    renderTour(refs, tourStops, state.tourIndex, goTour);
  });
  refs["slice-canvas"].addEventListener("pointerdown", async (event) => {
    const pixel = eventToPixel(event, refs["slice-canvas"]);
    const voxel = slicePixelToVoxel(state.axis, state.index[state.axis], pixel.col, pixel.row);
    await applyVoxelSelection(voxel.i, voxel.j, voxel.k);
  });
  refs.view3d.addEventListener("pointerdown", (event) => {
    pointerDown = { x: event.clientX, y: event.clientY };
  });
  refs.view3d.addEventListener("pointerup", async (event) => {
    if (!pointerDown || !scene) return;
    const dx = event.clientX - pointerDown.x;
    const dy = event.clientY - pointerDown.y;
    pointerDown = null;
    if (dx * dx + dy * dy > 25) return;
    const hit = scene.pick(event.clientX, event.clientY);
    if (!hit) return;
    if (hit.type === "annotation" && hit.id) {
      await focusAnnotation(hit.id, false);
      return;
    }
    await selectRas(hit.point);
  });
  window.addEventListener("resize", () => {
    if (scene) scene.resize();
  });
}

async function loadCase() {
  ready = false;
  exposeHooks();
  hideFatal(refs);
  renderStats(refs, statsPayload("loadingManifest"));
  if (!detectWebGL()) {
    showFatal(refs, "webgl");
    return;
  }
  try {
    manifest = await api.manifest();
  } catch (caught) {
    showFatal(refs, (caught && caught.code) || "apiUnreachable");
    return;
  }
  const valid = validateManifest(manifest);
  if (!valid.ok) {
    showFatal(refs, valid.code);
    return;
  }
  state = createAppState(manifest);
  if (scene) {
    scene.dispose();
    scene = null;
  }
  try {
    scene = new ObservatoryScene(refs.view3d, {
      bounds: manifest.bounds_ras,
      affineRas: manifest.affine_ras,
      shape: manifest.shape,
    });
  } catch {
    showFatal(refs, "webgl");
    return;
  }
  scene.setAnnotations(manifest.annotations);
  tourStops = expandTour(manifest);
  renderWarnings(refs, manifest.warnings || []);
  renderLayers(refs, manifest, state, { onToggle, onOpacity });
  renderTour(refs, tourStops, state.tourIndex, goTour);
  renderCandidates(refs, manifest.annotations, state.focusId, focusAnnotation);
  refreshChrome();
  if (resizeObserver) resizeObserver.disconnect();
  resizeObserver = new ResizeObserver(() => scene && scene.resize());
  resizeObserver.observe(refs.view3d.parentElement);
  scene.resize();
  scene.fitBounds();
  await loadVisibleMeshes();
  await refreshSlice();
  state.status = "ready";
  ready = true;
  exposeHooks();
  refreshChrome();
}

refs = mountApp(document.getElementById("app"));
document.title = copy.appTitle;
wire();
exposeHooks();
loadCase();
