export const VIDEO_INFO_PATH = "/api/video-info";
export const VIDEO_PLAY_PATH = "/api/video";
export const VIDEO_DOWNLOAD_PATH = "/api/video?download=1";
export const VIDEO_DOWNLOAD_NAME = "ct-education-tour.mp4";
export const VIDEO_VERSIONS = Object.freeze([
  Object.freeze({ id: "demo", title: "Interface demo", url: VIDEO_PLAY_PATH, download_url: VIDEO_DOWNLOAD_PATH, filename: VIDEO_DOWNLOAD_NAME }),
  Object.freeze({ id: "rendered", title: "Rendered film", url: "/api/video/rendered", download_url: "/api/video/rendered?download=1", filename: "ct-education-film.mp4" }),
]);

function failUnavailable() {
  return { ok: false, available: false, status: "unavailable" };
}

export function isAllowedVideoHref(value, origin, kind = "play", id = "demo") {
  const version = VIDEO_VERSIONS.find((item) => item.id === id);
  if (!version || !["play", "download"].includes(kind)) return false;
  const expected = kind === "download" ? version.download_url : version.url;
  if (value === expected) return true;
  // Only exact relative paths or their exact same-origin absolute form are allowed.
  // URL parsing alone would normalize traversal, whitespace and other aliases.
  if (!origin || typeof value !== "string") return false;
  try {
    const base = new URL(origin);
    return ["http:", "https:"].includes(base.protocol) && value === base.origin + expected;
  } catch {
    return false;
  }
}

export function validateVideoInfo(data, origin) {
  if (!data || typeof data !== "object" || Array.isArray(data)) return failUnavailable();
  if (data.available === false) {
    if (data.versions !== undefined && (!Array.isArray(data.versions) || data.versions.length)) return failUnavailable();
    return { ok: true, available: false, status: "unavailable" };
  }
  if (data.available !== true) return failUnavailable();
  const entries = data.versions === undefined ? [{ id: "demo", title: "Interface demo", url: data.url, download_url: data.download_url }] : data.versions;
  if (!Array.isArray(entries) || entries.length < 1 || entries.length > 2) return failUnavailable();
  const ids = new Set();
  for (const entry of entries) {
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) return failUnavailable();
    const version = VIDEO_VERSIONS.find((item) => item.id === entry.id);
    if (!version || ids.has(entry.id) || entry.title !== version.title) return failUnavailable();
    if (Object.keys(entry).some((key) => !["id", "title", "url", "download_url"].includes(key))) return failUnavailable();
    if (!isAllowedVideoHref(entry.url, origin, "play", entry.id) || !isAllowedVideoHref(entry.download_url, origin, "download", entry.id)) return failUnavailable();
    ids.add(entry.id);
  }
  const versions = VIDEO_VERSIONS.filter((version) => ids.has(version.id)).map(({ filename, ...version }) => version);
  const selected = versions[0];
  if (!isAllowedVideoHref(data.url, origin, "play", selected.id) || !isAllowedVideoHref(data.download_url, origin, "download", selected.id)) return failUnavailable();
  return {
    ok: true,
    available: true,
    status: "available",
    url: selected.url,
    download_url: selected.download_url,
    versions,
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
  return check;
}

export function createVideoState() {
  return {
    status: "checking",
    available: false,
    url: null,
    download_url: null,
    versions: [],
    selectedId: null,
    open: false,
    srcAttached: false,
  };
}

export function applyVideoInfo(state, info) {
  const checked = validateVideoInfo(info);
  const available = checked.available;
  const selected = available ? checked.versions[0] : null;
  return {
    ...state,
    status: available ? "available" : "unavailable",
    available,
    url: selected?.url ?? null,
    download_url: selected?.download_url ?? null,
    versions: checked.versions || [],
    selectedId: selected?.id ?? null,
    open: false,
    srcAttached: false,
  };
}

export function selectVideo(state, id) {
  const selected = state.versions.find((version) => version.id === id);
  if (!selected || state.selectedId === id) return state;
  return { ...state, selectedId: id, url: selected.url, download_url: selected.download_url };
}

export function syncVideoElement(video, state, { play = false } = {}) {
  if (!video) return;
  video.pause();
  try { video.currentTime = 0; } catch { /* Media may not yet have a timeline. */ }
  video.removeAttribute("src");
  video.load();
  const src = videoSrc(state);
  if (!src) return;
  video.setAttribute("src", src);
  if (play) {
    const pending = video.play();
    if (pending && typeof pending.catch === "function") pending.catch(() => {});
  }
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
  return state.url;
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
