export const VIDEO_INFO_PATH = "/api/video-info";
export const VIDEO_PLAY_PATH = "/api/video";
export const VIDEO_DOWNLOAD_PATH = "/api/video?download=1";
export const VIDEO_DOWNLOAD_NAME = "tour.mp4";

function failUnavailable() {
  return { ok: false, available: false, status: "unavailable" };
}

function parseHref(value, origin) {
  if (typeof value !== "string" || value.length === 0) return null;
  if (value.includes("\\") || value.includes("..")) return null;
  if (value.startsWith("//")) return null;
  try {
    return new URL(value, origin || "http://127.0.0.1");
  } catch {
    return null;
  }
}

export function isAllowedVideoHref(value, origin, kind = "play") {
  const parsed = parseHref(value, origin);
  if (!parsed) return false;
  if (parsed.username || parsed.password || parsed.hash) return false;
  if (parsed.pathname !== "/api/video") return false;
  const query = parsed.search.startsWith("?") ? parsed.search.slice(1) : parsed.search;
  if (kind === "download") {
    if (query !== "download=1") return false;
  } else if (query) {
    return false;
  }
  if (origin) {
    let expected;
    try {
      expected = new URL(origin);
    } catch {
      return false;
    }
    if (parsed.origin !== expected.origin) return false;
  } else if (/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(value)) {
    return false;
  }
  return true;
}

export function validateVideoInfo(data, origin) {
  if (!data || typeof data !== "object" || Array.isArray(data)) return failUnavailable();
  if (data.available === false) {
    return { ok: true, available: false, status: "unavailable" };
  }
  if (data.available !== true) return failUnavailable();
  if (!isAllowedVideoHref(data.url, origin, "play")) return failUnavailable();
  if (!isAllowedVideoHref(data.download_url, origin, "download")) return failUnavailable();
  return {
    ok: true,
    available: true,
    status: "available",
    url: VIDEO_PLAY_PATH,
    download_url: VIDEO_DOWNLOAD_PATH,
  };
}

export function videoInfoFromResponse(ok, status, data, origin) {
  if (!ok || status === 404 || status === 501 || status === 405) {
    return { available: false, status: "unavailable" };
  }
  const check = validateVideoInfo(data, origin);
  if (!check.ok || !check.available) {
    return { available: false, status: "unavailable" };
  }
  return {
    available: true,
    status: "available",
    url: VIDEO_PLAY_PATH,
    download_url: VIDEO_DOWNLOAD_PATH,
  };
}

export function createVideoState() {
  return {
    status: "checking",
    available: false,
    url: null,
    download_url: null,
    open: false,
    srcAttached: false,
  };
}

export function applyVideoInfo(state, info) {
  const available = Boolean(info && info.available);
  return {
    ...state,
    status: available ? "available" : "unavailable",
    available,
    url: available ? VIDEO_PLAY_PATH : null,
    download_url: available ? VIDEO_DOWNLOAD_PATH : null,
  };
}

export function canOpenVideo(state) {
  return Boolean(state && state.available && state.status === "available");
}

export function openVideo(state) {
  if (!canOpenVideo(state)) return state;
  return { ...state, open: true, srcAttached: true };
}

export function closeVideo(state) {
  return { ...state, open: false, srcAttached: false };
}

export function videoSrc(state) {
  if (!state || !state.open || !state.srcAttached || !state.available) return "";
  return VIDEO_PLAY_PATH;
}

export function videoActionEnabled(state) {
  return canOpenVideo(state) && !state.open;
}

export function isMediaFullscreen(video) {
  if (typeof document !== "undefined") {
    if (document.fullscreenElement || document.webkitFullscreenElement || document.msFullscreenElement) {
      return true;
    }
  }
  if (video && (video.webkitDisplayingFullscreen || video.mozDisplayingFullscreen)) return true;
  return false;
}

function eventTargetIsVideoControl(target) {
  if (!target) return false;
  if (target.tagName === "VIDEO") return true;
  if (typeof target.closest === "function") {
    try {
      return Boolean(target.closest("video"));
    } catch {
      return false;
    }
  }
  return false;
}

export function routeVideoEscape(event, { open, fullscreen } = {}) {
  if (!open) return { close: false, reason: "closed" };
  if (!event || event.key !== "Escape") return { close: false, reason: "other-key" };
  if (fullscreen) return { close: false, reason: "fullscreen" };
  if (typeof event.preventDefault === "function") event.preventDefault();
  if (typeof event.stopImmediatePropagation === "function") event.stopImmediatePropagation();
  else if (typeof event.stopPropagation === "function") event.stopPropagation();
  const fromControls = eventTargetIsVideoControl(event.target);
  return { close: true, reason: fromControls ? "video-control" : "dialog", fromControls };
}
