import { roundVoxel } from "./affine.js";
import { clampIndex, sliceExtent } from "./mapping.js";
import { copy } from "./copy.js";

export const DISPLAY_WINDOW = {
  wc: -600,
  ww: 1500,
};

export const FALLBACK_LAYER_COLORS = ["#c4b5fd", "#2ec9c0", "#e8b86d", "#9bb7c9"];

export function tourFallbackTitle(id) {
  const key = String(id || "").toLowerCase();
  const titles = copy.tour.fallbackTitles;
  if (key.includes("source") || key.includes("evidence") || key.includes("slice")) {
    return titles.sourceEvidence;
  }
  if (key.includes("vascular") || key.includes("vessel")) return titles.vascular;
  if (key.includes("airway")) return titles.airways;
  if (key.includes("lung")) return titles.lungs;
  if (key.includes("candidate") || key.includes("case")) return titles.caseCandidate;
  if (key.includes("overview") || key.includes("volume")) return titles.overview;
  return titles.overview;
}

export function defaultLayerOpacity(id) {
  const key = String(id || "").toLowerCase();
  if (key.includes("lung")) return 0.36;
  if (key.includes("airway")) return 0.88;
  if (key.includes("vessel")) return 0.42;
  if (key.includes("bone")) return 0.16;
  return 0.62;
}

export function defaultLayerVisible() {
  return true;
}

function boundsCenter(bounds) {
  return [
    (bounds.min[0] + bounds.max[0]) / 2,
    (bounds.min[1] + bounds.max[1]) / 2,
    (bounds.min[2] + bounds.max[2]) / 2,
  ];
}

function findLayer(layers, pattern) {
  return layers.find((layer) => pattern.test(layer.id) || pattern.test(layer.name || ""));
}

function stopText(stop) {
  return `${stop.id || ""} ${stop.title || ""}`.toLowerCase();
}

export function expandTour(manifest) {
  const apiTour = Array.isArray(manifest.tour) ? manifest.tour.filter((stop) => stop && stop.id) : [];
  const layers = manifest.layers || [];
  const annotations = manifest.annotations || [];
  const center = boundsCenter(manifest.bounds_ras);
  const firstAnn = annotations[0];
  const allLayerIds = layers.map((layer) => layer.id);
  const lung = findLayer(layers, /lung/i);
  const airway = findLayer(layers, /airway/i);
  const vessel = findLayer(layers, /vessel|vascular/i);
  const overviewIds = [lung, airway].filter(Boolean).map((layer) => layer.id);
  const overviewLayers = overviewIds.length ? overviewIds : allLayerIds;
  const used = new Set();
  const takeApi = (pattern) => {
    const index = apiTour.findIndex((stop, i) => !used.has(i) && pattern.test(stopText(stop)));
    if (index < 0) return null;
    used.add(index);
    return apiTour[index];
  };
  const ordered = [];
  ordered.push(
    takeApi(/overview|volume/) || {
      id: "fallback-overview",
      title: copy.tour.fallbackTitles.overview,
      layer_ids: overviewLayers,
      target_ras: center,
    },
  );
  if (lung) {
    ordered.push(
      takeApi(/lung/) || {
        id: "fallback-lungs",
        title: copy.tour.fallbackTitles.lungs,
        layer_ids: [lung.id],
        target_ras: center,
      },
    );
  }
  if (airway) {
    ordered.push(
      takeApi(/airway/) || {
        id: "fallback-airways",
        title: copy.tour.fallbackTitles.airways,
        layer_ids: lung ? [airway.id, lung.id] : [airway.id],
        target_ras: center,
      },
    );
  }
  if (vessel) {
    ordered.push(
      takeApi(/vascular|vessel/) || {
        id: "fallback-vascular",
        title: copy.tour.fallbackTitles.vascular,
        layer_ids: [vessel.id],
        target_ras: center,
      },
    );
  }
  if (firstAnn) {
    ordered.push(
      takeApi(/candidate|case/) || {
        id: "fallback-case-candidate",
        title: copy.tour.fallbackTitles.caseCandidate,
        layer_ids: lung ? [lung.id] : overviewLayers,
        target_ras: firstAnn.position_ras,
        annotation_id: firstAnn.id,
      },
    );
  }
  ordered.push(
    takeApi(/source|evidence|slice/) || {
      id: "fallback-source-evidence",
      title: copy.tour.fallbackTitles.sourceEvidence,
      layer_ids: lung ? [lung.id] : allLayerIds,
      target_ras: firstAnn ? firstAnn.position_ras : center,
      annotation_id: firstAnn ? firstAnn.id : undefined,
    },
  );
  apiTour.forEach((stop, index) => {
    if (!used.has(index)) ordered.push(stop);
  });
  return ordered;
}

export function slice3dDefaultForStop(stop) {
  if (!stop) return false;
  const id = String(stop.id || "").toLowerCase();
  if (/overview|volume/.test(id)) return false;
  if (/source-evidence|fallback-source/.test(id)) return true;
  return Boolean(stop.annotation_id);
}

export function visibleIdsForTourStop(stop) {
  if (!stop || !Array.isArray(stop.layer_ids)) return null;
  const id = String(stop.id || "").toLowerCase();
  const closeUp = Boolean(stop.annotation_id) || /source-evidence|fallback-source/.test(id);
  if (!closeUp) return stop.layer_ids.slice();
  return stop.layer_ids.filter((layerId) => !/bone/i.test(String(layerId)));
}

export function focusForStop(stop) {
  if (!stop) {
    return { title: copy.focus.overviewTitle, body: copy.focus.overviewBody };
  }
  const id = String(stop.id || "").toLowerCase();
  if (/overview|volume/.test(id)) {
    return { title: copy.focus.overviewTitle, body: copy.focus.overviewBody };
  }
  if (/source-evidence|fallback-source/.test(id)) {
    return { title: copy.focus.sourceTitle, body: copy.focus.sourceBody };
  }
  if (/airway/.test(id)) {
    return { title: copy.focus.airwaysTitle, body: copy.focus.airwaysBody };
  }
  if (/lung/.test(id)) {
    return { title: copy.focus.lungsTitle, body: copy.focus.lungsBody };
  }
  if (/vessel|vascular/.test(id) && !/tour-candidate|case-candidate|fallback-case/.test(id)) {
    return { title: copy.focus.vesselsTitle, body: copy.focus.vesselsBody };
  }
  if (stop.annotation_id || /candidate|case/.test(id)) {
    return { title: copy.focus.candidateTitle, body: copy.focus.candidateBody };
  }
  return { title: copy.focus.overviewTitle, body: copy.focus.overviewBody };
}

export function layerHintForId(id) {
  const key = String(id || "").toLowerCase();
  if (key.includes("lung")) return copy.layerHint.lungs;
  if (key.includes("airway")) return copy.layerHint.airways;
  if (key.includes("vessel") || key.includes("vascular")) return copy.layerHint.vessels;
  if (key.includes("bone")) return copy.layerHint.bones;
  return "";
}

export function createAppState(manifest) {
  const [nz, ny, nx] = manifest.shape;
  const zMid = (manifest.bounds_ras.min[2] + manifest.bounds_ras.max[2]) / 2;
  return {
    axis: "axial",
    wc: DISPLAY_WINDOW.wc,
    ww: DISPLAY_WINDOW.ww,
    index: {
      axial: Math.floor(nz / 2),
      coronal: Math.floor(ny / 2),
      sagittal: Math.floor(nx / 2),
    },
    selection: null,
    tourIndex: -1,
    focusId: null,
    showSlice3d: false,
    clip: {
      enabled: false,
      axis: "z",
      value: zMid,
    },
    layers: manifest.layers.map((layer, order) => ({
      id: layer.id,
      visible: defaultLayerVisible(layer.id),
      opacity: defaultLayerOpacity(layer.id),
      loaded: false,
      error: null,
      color: layer.color,
      order,
    })),
    status: "loadingManifest",
    meshCount: 0,
    sliceLoading: false,
  };
}

export function setAxis(state, axis) {
  if (axis !== "axial" && axis !== "coronal" && axis !== "sagittal") return state;
  return { ...state, axis };
}

export function setSliceIndex(state, axis, index, shape) {
  const extent = sliceExtent(axis, shape);
  return {
    ...state,
    index: {
      ...state.index,
      [axis]: clampIndex(index, extent.maxIndex),
    },
  };
}

export function setDisplayWindow(state, wc, ww) {
  const nextWc = Number.isFinite(wc) ? wc : state.wc;
  const nextWw = Number.isFinite(ww) && ww > 0 ? ww : state.ww;
  return { ...state, wc: nextWc, ww: nextWw };
}

export function selectVoxel(state, i, j, k, shape, extra = {}) {
  const rounded = roundVoxel(i, j, k, shape);
  if (!rounded.inBounds) {
    return {
      ...state,
      selection: {
        error: "outOfBounds",
        i: rounded.i,
        j: rounded.j,
        k: rounded.k,
        fractional: rounded.fractional,
      },
    };
  }
  return {
    ...state,
    selection: {
      error: null,
      i: rounded.i,
      j: rounded.j,
      k: rounded.k,
      fractional: rounded.fractional,
      ...extra,
    },
    index: {
      axial: rounded.k,
      coronal: rounded.j,
      sagittal: rounded.i,
    },
  };
}

export function clearSelection(state) {
  return { ...state, selection: null };
}

export function setTourStep(state, index, tourLength) {
  if (!Number.isInteger(index) || index < -1 || index >= tourLength) return state;
  return { ...state, tourIndex: index };
}

export function setLayerVisible(state, id, visible) {
  return {
    ...state,
    layers: state.layers.map((layer) =>
      layer.id === id ? { ...layer, visible: Boolean(visible) } : layer,
    ),
  };
}

export function setLayerOpacity(state, id, opacity) {
  const value = Math.min(1, Math.max(0, Number(opacity)));
  return {
    ...state,
    layers: state.layers.map((layer) =>
      layer.id === id ? { ...layer, opacity: value } : layer,
    ),
  };
}

export function setLayerLoaded(state, id, ok, error) {
  return {
    ...state,
    layers: state.layers.map((layer) =>
      layer.id === id
        ? { ...layer, loaded: Boolean(ok), error: ok ? null : error || "invalidMesh" }
        : layer,
    ),
    meshCount: state.layers.reduce((count, layer) => {
      const loaded = layer.id === id ? Boolean(ok) : layer.loaded;
      return count + (loaded ? 1 : 0);
    }, 0),
  };
}

export function setClip(state, patch) {
  return {
    ...state,
    clip: { ...state.clip, ...patch },
  };
}

export function setShowSlice3d(state, visible) {
  return { ...state, showSlice3d: Boolean(visible) };
}

export function moveSelectionToSlice(selection, axis, index) {
  if (!selection || selection.i == null) return null;
  const next = {
    i: selection.i,
    j: selection.j,
    k: selection.k,
    error: null,
  };
  if (axis === "axial") next.k = index;
  else if (axis === "coronal") next.j = index;
  else next.i = index;
  return next;
}

export function isSelectionOnSlice(selection, axis, index) {
  if (!selection || selection.error || selection.i == null) return false;
  if (axis === "axial") return selection.k === index;
  if (axis === "coronal") return selection.j === index;
  return selection.i === index;
}

export function tourUsesLayerFit(stop) {
  if (!stop) return false;
  const id = String(stop.id || "").toLowerCase();
  if (/tour-candidate|case-candidate|fallback-case|source-evidence|fallback-source/.test(id)) {
    return false;
  }
  return true;
}

export function tourFitPad(stop) {
  const id = String(stop && stop.id ? stop.id : "").toLowerCase();
  if (/airway/.test(id)) return 1.55;
  if (/vessel|vascular/.test(id)) return 1.45;
  return 1.22;
}

export function boxCenter(min, max) {
  return [
    (min[0] + max[0]) / 2,
    (min[1] + max[1]) / 2,
    (min[2] + max[2]) / 2,
  ];
}

export function cameraDistanceForBox(min, max, fovDeg, pad) {
  const radius = Math.hypot(max[0] - min[0], max[1] - min[1], max[2] - min[2]) * 0.5;
  const fov = (fovDeg * Math.PI) / 180;
  return Math.max((radius / Math.sin(fov / 2)) * pad, 40);
}

export function visibleLayerIds(state) {
  return state.layers.filter((layer) => layer.visible).map((layer) => layer.id);
}
