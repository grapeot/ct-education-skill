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
  if (key.includes("lung")) return 0.46;
  if (key.includes("airway")) return 0.92;
  if (key.includes("vessel")) return 0.5;
  if (key.includes("bone")) return 0.2;
  return 0.7;
}

export function defaultLayerVisible(id) {
  const key = String(id || "").toLowerCase();
  if (key.includes("vessel") || key.includes("bone")) return false;
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
        target_ras: firstAnn ? firstAnn.position_ras : center,
      },
    );
  }
  if (firstAnn) {
    ordered.push(
      takeApi(/candidate|case/) || {
        id: "fallback-case-candidate",
        title: copy.tour.fallbackTitles.caseCandidate,
        layer_ids: allLayerIds,
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

export function visibleLayerIds(state) {
  return state.layers.filter((layer) => layer.visible).map((layer) => layer.id);
}
