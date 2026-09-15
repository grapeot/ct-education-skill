import assert from "node:assert/strict";
import test from "node:test";
import {
  VIDEO_DOWNLOAD_PATH,
  VIDEO_PLAY_PATH,
  VIDEO_VERSIONS,
  applyVideoInfo,
  canOpenVideo,
  closeVideo,
  createVideoState,
  isAllowedVideoHref,
  isMediaFullscreen,
  openVideo,
  routeVideoEscape,
  selectVideo,
  syncVideoElement,
  validateVideoInfo,
  videoActionEnabled,
  videoInfoFromResponse,
  videoSrc,
} from "../src/video.js";
import { applyVideoModal } from "../src/ui.js";

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
const versions = VIDEO_VERSIONS.map(({ filename, ...version }) => version);
const catalog = (entries = versions) => ({ available: true, url: entries[0].url, download_url: entries[0].download_url, versions: entries });

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
  state = applyVideoInfo(state, catalog());
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

test("catalog supports both versions, either alone, and legacy demo metadata", () => {
  for (const entries of [versions, [versions[0]], [versions[1]]]) {
    const info = videoInfoFromResponse(true, 200, catalog(entries), origin);
    assert.equal(info.available, true);
    assert.deepEqual(info.versions, entries);
    const state = applyVideoInfo(createVideoState(), info);
    assert.equal(state.selectedId, entries[0].id);
    assert.equal(videoSrc(state), "");
    assert.equal(videoSrc(openVideo(state)), entries[0].url);
  }
  assert.equal(validateVideoInfo(catalog([...versions].reverse()), origin).ok, false);
  const reversed = { ...catalog(), versions: [...versions].reverse() };
  assert.deepEqual(validateVideoInfo(reversed, origin).versions, versions);
  const { versions: unused, ...legacy } = catalog([versions[0]]);
  assert.deepEqual(validateVideoInfo(legacy, origin).versions, [versions[0]]);
});

test("catalog rejects unknown or duplicate IDs, mismatched labels and inconsistent defaults", () => {
  const invalid = [[], [...versions, versions[0]], [versions[0], versions[0]],
    [{ ...versions[0], id: "other" }], [{ ...versions[0], title: "Rendered film" }],
    [{ ...versions[1], url: versions[0].url }], [null], [{ ...versions[0], filename: "synthetic-private.mp4" }]];
  for (const entries of invalid) {
    assert.equal(validateVideoInfo({ ...catalog(), versions: entries }, origin).ok, false);
  }
  assert.equal(validateVideoInfo({ ...catalog(), available: false }, origin).ok, false);
  assert.equal(validateVideoInfo({ available: false, versions: [] }, origin).ok, true);
  assert.equal(validateVideoInfo({ ...catalog(), versions: {} }, origin).ok, false);
  assert.equal(validateVideoInfo({ ...catalog([versions[1]]), url: versions[0].url }, origin).ok, false);
  assert.equal(applyVideoInfo(createVideoState(), { available: true }).available, false);
});

test("catalog accepts only exact per-version paths, never arbitrary same-origin files", () => {
  for (const version of versions) {
    for (const bad of ["/videos/synthetic-private.mp4", "/api/video/other.mp4", "//127.0.0.1:8788" + version.url,
      "/api/./video", "/api/%76ideo", "/api/other/../video", version.url + "?file=synthetic-private.mp4",
      version.url + "/", version.url + "#", " " + version.url, version.url + "\n",
      "https://external.invalid" + version.url, "http://user@127.0.0.1:8788" + version.url]) {
      assert.equal(validateVideoInfo(catalog([{ ...version, url: bad }]), origin).available, false, bad);
      assert.equal(validateVideoInfo(catalog([{ ...version, download_url: bad }]), origin).available, false, bad);
    }
    const absolute = { ...version, url: origin + version.url, download_url: origin + version.download_url };
    const checked = validateVideoInfo(catalog([absolute]), origin);
    assert.equal(checked.ok, true);
    assert.deepEqual(checked.versions, [version]);
  }
});

test("switching selects only configured versions and close keeps all media detached", () => {
  let state = applyVideoInfo(createVideoState(), catalog());
  state = selectVideo(state, "rendered");
  assert.equal(videoSrc(state), "");
  state = openVideo(state);
  assert.equal(videoSrc(state), "/api/video/rendered");
  assert.equal(state.download_url, "/api/video/rendered?download=1");
  assert.equal(selectVideo(state, "unknown"), state);
  assert.equal(selectVideo(state, "rendered"), state);
  state = selectVideo(state, "demo");
  assert.equal(videoSrc(state), "/api/video");
  assert.equal(state.download_url, "/api/video?download=1");
  state = closeVideo(state);
  assert.equal(videoSrc(state), "");
  assert.equal(state.srcAttached, false);
  const onlyRendered = applyVideoInfo(createVideoState(), catalog([versions[1]]));
  assert.equal(selectVideo(onlyRendered, "demo"), onlyRendered);
});

test("media switching pauses, resets and unloads before attaching; play is explicitly requested", async () => {
  const calls = [];
  const video = {
    pause() { calls.push("pause"); },
    set currentTime(value) { calls.push(["time", value]); },
    removeAttribute(name) { calls.push(["remove", name]); },
    load() { calls.push("load"); },
    setAttribute(name, value) { calls.push([name, value]); },
    play() { calls.push("play"); return Promise.reject(new Error("synthetic play rejection")); },
  };
  let state = openVideo(applyVideoInfo(createVideoState(), catalog()));
  state = selectVideo(state, "rendered");
  const cleanup = ["pause", ["time", 0], ["remove", "src"], "load"];
  syncVideoElement(video, state);
  assert.deepEqual(calls, [...cleanup, ["src", "/api/video/rendered"]]);
  calls.length = 0;
  syncVideoElement(video, state, { play: true });
  await Promise.resolve();
  assert.deepEqual(calls, [...cleanup, ["src", "/api/video/rendered"], "play"]);
  calls.length = 0;
  syncVideoElement(video, closeVideo(state), { play: true });
  assert.deepEqual(calls, cleanup);
});

test("modal buttons, descriptions and both links track the selected version and clean up on close", () => {
  function node() {
    return { attributes: {}, classList: { toggle() {} }, setAttribute(key, value) { this.attributes[key] = value; }, removeAttribute(key) { delete this.attributes[key]; } };
  }
  const refs = Object.fromEntries(["backdrop", "dialog", "status", "description", "demo", "rendered", "play", "download"].map((key) => ["video-" + key, node()]));
  let state = applyVideoInfo(createVideoState(), catalog());
  applyVideoModal(refs, state, "");
  assert.equal(refs["video-play"].attributes.href, undefined);
  assert.equal(refs["video-download"].attributes.href, undefined);
  state = openVideo(state);
  for (const version of VIDEO_VERSIONS) {
    state = selectVideo(state, version.id);
    applyVideoModal(refs, state, "");
    assert.equal(refs[`video-${version.id}`].attributes["aria-pressed"], "true");
    assert.equal(refs["video-play"].attributes.href, version.url);
    assert.equal(refs["video-download"].attributes.href, version.download_url);
    assert.equal(refs["video-download"].attributes.download, version.filename);
    assert.match(refs["video-description"].textContent, version.id === "demo" ? /browser interface/ : /offline-rendered/);
  }
  applyVideoModal(refs, closeVideo(state), "");
  assert.equal(refs["video-play"].attributes.href, undefined);
  assert.equal(refs["video-download"].attributes.href, undefined);
  assert.equal(refs["video-download"].attributes.download, undefined);
  state = openVideo(applyVideoInfo(createVideoState(), catalog([versions[1]])));
  applyVideoModal(refs, state, "");
  assert.equal(refs["video-demo"].disabled, true);
  assert.equal(refs["video-rendered"].disabled, false);
  assert.equal(refs["video-rendered"].attributes["aria-pressed"], "true");
});
