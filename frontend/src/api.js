import { videoInfoFromResponse } from "./video.js";

const FETCH_OPTS = { cache: "no-store" };

function errorFromResponse(response, fallback) {
  if (response.status === 404) return fallback === "invalidManifest" ? "noManifest" : fallback;
  return fallback;
}

async function readJson(response, fallback) {
  if (!response.ok) {
    const error = new Error(errorFromResponse(response, fallback));
    error.code = error.message;
    throw error;
  }
  try {
    return await response.json();
  } catch {
    const error = new Error(fallback);
    error.code = fallback;
    throw error;
  }
}

export function createApi(base = "") {
  let sliceGeneration = 0;
  let sliceAbort = null;

  return {
    async manifest() {
      let response;
      try {
        response = await fetch(`${base}/api/manifest`, FETCH_OPTS);
      } catch {
        const error = new Error("apiUnreachable");
        error.code = "apiUnreachable";
        throw error;
      }
      if (response.status === 404) {
        const error = new Error("noManifest");
        error.code = "noManifest";
        throw error;
      }
      const data = await readJson(response, "invalidManifest");
      if (data == null) {
        const error = new Error("noManifest");
        error.code = "noManifest";
        throw error;
      }
      return data;
    },

    async mesh(id, signal) {
      let response;
      try {
        response = await fetch(`${base}/api/mesh/${encodeURIComponent(id)}`, {
          ...FETCH_OPTS,
          signal,
        });
      } catch (caught) {
        if (caught && caught.name === "AbortError") throw caught;
        const error = new Error("invalidMesh");
        error.code = "invalidMesh";
        throw error;
      }
      return readJson(response, "invalidMesh");
    },

    async slice({ axis, index, wc, ww }) {
      if (sliceAbort) sliceAbort.abort();
      const controller = new AbortController();
      sliceAbort = controller;
      const generation = (sliceGeneration += 1);
      const params = new URLSearchParams({
        axis,
        index: String(index),
        wc: String(wc),
        ww: String(ww),
      });
      try {
        const response = await fetch(`${base}/api/slice?${params.toString()}`, {
          ...FETCH_OPTS,
          signal: controller.signal,
        });
        if (generation !== sliceGeneration) return null;
        if (!response.ok) {
          const error = new Error("sliceFailed");
          error.code = "sliceFailed";
          throw error;
        }
        const blob = await response.blob();
        if (generation !== sliceGeneration) return null;
        return blob;
      } catch (caught) {
        if (caught && caught.name === "AbortError") return null;
        if (caught && caught.code) throw caught;
        const error = new Error("sliceFailed");
        error.code = "sliceFailed";
        throw error;
      }
    },

    async videoInfo(origin = "") {
      let response;
      try {
        response = await fetch(`${base}/api/video-info`, FETCH_OPTS);
      } catch {
        return { available: false, status: "unavailable" };
      }
      let data = null;
      try {
        data = await response.json();
      } catch {
        data = null;
      }
      return videoInfoFromResponse(response.ok, response.status, data, origin);
    },

    async voxel(i, j, k) {
      const params = new URLSearchParams({
        i: String(i),
        j: String(j),
        k: String(k),
      });
      let response;
      try {
        response = await fetch(`${base}/api/voxel?${params.toString()}`, FETCH_OPTS);
      } catch {
        const error = new Error("voxelError");
        error.code = "voxelError";
        throw error;
      }
      return readJson(response, "voxelError");
    },
  };
}

export function blobToCanvas(blob) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const image = new Image();
    image.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = image.width;
      canvas.height = image.height;
      const context = canvas.getContext("2d", { willReadFrequently: false });
      context.drawImage(image, 0, 0);
      URL.revokeObjectURL(url);
      resolve(canvas);
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      const error = new Error("sliceFailed");
      error.code = "sliceFailed";
      reject(error);
    };
    image.src = url;
  });
}
