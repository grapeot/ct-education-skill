import assert from "node:assert/strict";
import test from "node:test";
import {
  VIDEO_DOWNLOAD_PATH,
  VIDEO_PLAY_PATH,
  applyVideoInfo,
  canOpenVideo,
  closeVideo,
  createVideoState,
  isAllowedVideoHref,
  isMediaFullscreen,
  openVideo,
  routeVideoEscape,
  validateVideoInfo,
  videoActionEnabled,
  videoInfoFromResponse,
  videoSrc,
} from "../src/video.js";

function makeKeyEvent(key, target) {
  const calls = { preventDefault: 0, stopPropagation: 0, stopImmediatePropagation: 0 };
  return {
    key,
    target,
    preventDefault() {
      calls.preventDefault += 1;
    },
    stopPropagation() {
      calls.stopPropagation += 1;
    },
    stopImmediatePropagation() {
      calls.stopImmediatePropagation += 1;
    },
    calls,
  };
}

const origin = "http://127.0.0.1:8788";

test("valid same-origin video info is canonicalized to fixed paths", () => {
  const check = validateVideoInfo(
    { available: true, url: "/api/video", download_url: "/api/video?download=1" },
    origin,
  );
  assert.equal(check.ok, true);
  assert.equal(check.available, true);
  assert.equal(check.url, VIDEO_PLAY_PATH);
  assert.equal(check.download_url, VIDEO_DOWNLOAD_PATH);
});

test("available false is a quiet unavailable state", () => {
  const check = validateVideoInfo({ available: false }, origin);
  assert.equal(check.ok, true);
  assert.equal(check.available, false);
  assert.equal(check.status, "unavailable");
});

test("external and protocol-relative video URLs are rejected", () => {
  const evil = {
    available: true,
    url: "https://example.com/api/video",
    download_url: "/api/video?download=1",
  };
  assert.equal(validateVideoInfo(evil, origin).available, false);
  assert.equal(isAllowedVideoHref("//example.com/api/video", origin, "play"), false);
  assert.equal(isAllowedVideoHref("https://127.0.0.1:8788/api/video", origin, "play"), false);
});

test("path traversal and non-video API paths are rejected", () => {
  assert.equal(isAllowedVideoHref("/api/video/../manifest", origin, "play"), false);
  assert.equal(isAllowedVideoHref("/api/manifest", origin, "play"), false);
  assert.equal(isAllowedVideoHref("/api/video?download=1", origin, "play"), false);
  assert.equal(isAllowedVideoHref("/api/video", origin, "download"), false);
});

test("absolute same-origin paths still canonicalize rather than follow the payload URL", () => {
  const check = validateVideoInfo(
    {
      available: true,
      url: "http://127.0.0.1:8788/api/video",
      download_url: "http://127.0.0.1:8788/api/video?download=1",
    },
    origin,
  );
  assert.equal(check.available, true);
  assert.equal(check.url, "/api/video");
  assert.equal(check.download_url, "/api/video?download=1");
});

test("missing or 404 video-info does not enable playback", () => {
  assert.equal(videoInfoFromResponse(false, 404, null, origin).available, false);
  assert.equal(videoInfoFromResponse(true, 200, null, origin).available, false);
  assert.equal(videoInfoFromResponse(true, 501, { available: true }, origin).available, false);
});

test("video src attaches only after an allowed user open", () => {
  let state = createVideoState();
  assert.equal(state.status, "checking");
  assert.equal(videoActionEnabled(state), false);
  assert.equal(videoSrc(state), "");
  state = applyVideoInfo(state, { available: false });
  assert.equal(canOpenVideo(state), false);
  assert.equal(openVideo(state).open, false);
  state = applyVideoInfo(state, { available: true });
  assert.equal(videoActionEnabled(state), true);
  const opened = openVideo(state);
  assert.equal(opened.open, true);
  assert.equal(videoSrc(opened), VIDEO_PLAY_PATH);
  const closed = closeVideo(opened);
  assert.equal(closed.open, false);
  assert.equal(closed.srcAttached, false);
  assert.equal(videoSrc(closed), "");
});

test("escape from a focused video control closes and stops the event", () => {
  const video = { tagName: "VIDEO", closest(selector) { return selector === "video" ? video : null; } };
  const event = makeKeyEvent("Escape", video);
  const result = routeVideoEscape(event, { open: true, fullscreen: false });
  assert.equal(result.close, true);
  assert.equal(result.fromControls, true);
  assert.equal(result.reason, "video-control");
  assert.equal(event.calls.preventDefault, 1);
  assert.equal(event.calls.stopImmediatePropagation, 1);
});

test("escape during native fullscreen does not close or consume the key", () => {
  const video = { tagName: "VIDEO", webkitDisplayingFullscreen: true };
  const event = makeKeyEvent("Escape", video);
  const result = routeVideoEscape(event, { open: true, fullscreen: true });
  assert.equal(result.close, false);
  assert.equal(result.reason, "fullscreen");
  assert.equal(event.calls.preventDefault, 0);
  assert.equal(event.calls.stopImmediatePropagation, 0);
  assert.equal(isMediaFullscreen(video), true);
});

test("escape is ignored when the dialog is closed or the key is not Escape", () => {
  const video = { tagName: "VIDEO" };
  assert.equal(routeVideoEscape(makeKeyEvent("Escape", video), { open: false }).close, false);
  assert.equal(routeVideoEscape(makeKeyEvent("Tab", video), { open: true, fullscreen: false }).close, false);
  const dialog = { tagName: "BUTTON" };
  const result = routeVideoEscape(makeKeyEvent("Escape", dialog), { open: true, fullscreen: false });
  assert.equal(result.close, true);
  assert.equal(result.fromControls, false);
});
