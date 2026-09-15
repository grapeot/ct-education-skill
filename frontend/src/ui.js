import { copy } from "./copy.js";
import { formatNumber } from "./affine.js";
import { sliceExtent } from "./mapping.js";
import { FALLBACK_LAYER_COLORS, layerHintForId, tourFallbackTitle } from "./state.js";
import { isCssHexColor } from "./validate.js";
import { VIDEO_VERSIONS } from "./video.js";

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function segment(name, legend, options) {
  const opts = options
    .map(
      ([value, label, checked, aria]) => `
        <label class="seg-opt">
          <input type="radio" name="${escapeHtml(name)}" value="${escapeHtml(value)}" ${checked ? "checked" : ""} aria-label="${escapeHtml(aria || label)}" />
          <span>${escapeHtml(label)}</span>
        </label>`,
    )
    .join("");
  return `
    <fieldset class="segment" data-ref="${escapeHtml(name)}">
      <legend class="sr">${escapeHtml(legend)}</legend>
      <div class="seg-track">${opts}</div>
    </fieldset>
  `;
}

function slider(ref, label, attrs, valueRef) {
  return `
    <label class="slider">
      <span class="slider-head">
        <span>${escapeHtml(label)}</span>
        <span class="num" data-ref="${escapeHtml(valueRef)}">0</span>
      </span>
      <input type="range" data-ref="${escapeHtml(ref)}" ${attrs} />
    </label>
  `;
}

function switchControl(ref, label) {
  return `
    <label class="switch">
      <input type="checkbox" data-ref="${escapeHtml(ref)}" />
      <span class="switch-ui" aria-hidden="true"></span>
      <span>${escapeHtml(label)}</span>
    </label>
  `;
}

export function mountApp(root) {
  root.innerHTML = `
    <div class="shell">
      <header class="top">
        <div class="brand">
          <p class="kicker">${escapeHtml(copy.appKicker)}</p>
          <p class="app-title">${escapeHtml(copy.appTitle)}</p>
        </div>
        <div class="header-actions">
          <button type="button" class="btn-watch" data-ref="watch-tour" disabled aria-label="${escapeHtml(copy.a11y.watchTourChecking)}">${escapeHtml(copy.video.checking)}</button>
        </div>
        <p class="banner">${escapeHtml(copy.banner)}</p>
        <div class="top-meta">
          <details class="notes-fold">
            <summary>${escapeHtml(copy.notesSummary)}</summary>
            <p>${escapeHtml(copy.disclaimer)}</p>
            <p>${escapeHtml(copy.colorNote)}</p>
            <p>${escapeHtml(copy.coordNote)}</p>
            <p>${escapeHtml(copy.candidates.notDiagnosis)}</p>
            <ul class="warnings" data-ref="warnings"></ul>
          </details>
          <div class="stats" data-ref="stats" role="status">${escapeHtml(copy.stats.loadingManifest)}</div>
        </div>
      </header>
      <aside class="rail rail-left">
        ${panel("layers", copy.panels.layers, copy.accordion.layers, `
          <div class="stack" data-ref="layers"></div>
        `)}
        ${panel("clip", copy.panels.clip, copy.accordion.clip, `
          ${switchControl("clip-enable", copy.clip.enable)}
          ${segment("clip-axis", copy.a11y.clipEnable, [
            ["x", "X", false, copy.clip.axisX],
            ["y", "Y", false, copy.clip.axisY],
            ["z", "Z", true, copy.clip.axisZ],
          ])}
          ${slider("clip-pos", copy.clip.position, 'min="0" max="1" step="0.001" value="0.5"', "clip-pos-value")}
          <p class="warn clip-warn hidden" data-ref="clip-warn">${escapeHtml(copy.clip.uncappedWarning)}</p>
        `)}
        ${panel("tour", copy.panels.tour, copy.accordion.tour, `
          <p class="tour-status hidden" data-ref="tour-status">${escapeHtml(copy.tour.active)}</p>
          <div class="tour-nav">
            <button type="button" data-ref="tour-prev">${escapeHtml(copy.tour.previous)}</button>
            <button type="button" class="btn-quiet-fill" data-ref="tour-next">${escapeHtml(copy.tour.start)}</button>
            <button type="button" data-ref="tour-exit">${escapeHtml(copy.tour.exit)}</button>
          </div>
          <ol class="stops" data-ref="tour"></ol>
        `)}
      </aside>
      <section class="stage">
        <div class="stage-chrome">
          <div class="focus-card" data-ref="focus-card">
            <p class="focus-title" data-ref="focus-title">${escapeHtml(copy.focus.overviewTitle)}</p>
            <p class="focus-body" data-ref="focus-body">${escapeHtml(copy.focus.overviewBody)}</p>
          </div>
          <div class="stage-actions">
            <label class="switch slice3d-toggle">
              <input type="checkbox" data-ref="slice3d" />
              <span class="switch-ui" aria-hidden="true"></span>
              <span>${escapeHtml(copy.showSlice3d)}</span>
            </label>
            <button type="button" data-ref="reset">${escapeHtml(copy.buttons.resetView)}</button>
          </div>
        </div>
        <canvas id="view3d" data-ref="view3d" role="img" aria-label="${escapeHtml(copy.a11y.viewer)}"></canvas>
        <div class="stage-readout" data-ref="readout">${escapeHtml(copy.readout.noSelection)}</div>
      </section>
      <aside class="rail rail-right">
        ${panel("slice", copy.panels.slice, copy.accordion.slice, `
          ${segment("slice-axis", copy.a11y.sliceAxis, [
            ["axial", copy.slice.axial, true],
            ["coronal", copy.slice.coronal, false],
            ["sagittal", copy.slice.sagittal, false],
          ])}
          <div class="slice-frame">
            <span class="ori ori-top" data-ref="ori-top"></span>
            <span class="ori ori-left" data-ref="ori-left"></span>
            <span class="ori ori-right" data-ref="ori-right"></span>
            <span class="ori ori-bottom" data-ref="ori-bottom"></span>
            <div class="slice-stack" data-ref="slice-stack">
              <canvas data-ref="slice-canvas" role="img" aria-label="${escapeHtml(copy.a11y.sliceImage)}"></canvas>
              <canvas data-ref="slice-overlay"></canvas>
            </div>
          </div>
          ${slider("slice-index", copy.slice.index, 'min="0" max="1" step="1" value="0"', "slice-index-value")}
          ${slider("wc", copy.slice.windowCenter, 'min="-1200" max="400" step="1" value="-600"', "wc-value")}
          ${slider("ww", copy.slice.windowWidth, 'min="50" max="4000" step="10" value="1500"', "ww-value")}
          <p class="note">${escapeHtml(copy.slice.nativeNote)}</p>
          <p class="note hidden" data-ref="axis-fallback">${escapeHtml(copy.slice.sourceAxisFallback)}</p>
        `)}
        ${panel("candidates", copy.panels.candidates, copy.accordion.candidates, `
          <div class="stack" data-ref="candidates"></div>
        `)}
        ${panel("notes", copy.panels.notes, copy.accordion.notes, `
          <p class="note">${escapeHtml(copy.slice.nativeNote)}</p>
          <p class="note">${escapeHtml(copy.clip.uncappedWarning)}</p>
        `)}
      </aside>
      <div class="fatal hidden" data-ref="fatal" role="alert">
        <p data-ref="fatal-text"></p>
        <button type="button" data-ref="retry">${escapeHtml(copy.buttons.retry)}</button>
      </div>
      <div class="video-backdrop hidden" data-ref="video-backdrop">
        <div class="video-dialog" data-ref="video-dialog" role="dialog" aria-modal="true" aria-labelledby="video-title" tabindex="-1">
          <div class="video-head">
            <h2 id="video-title">${escapeHtml(copy.video.title)}</h2>
            <button type="button" data-ref="video-close" aria-label="${escapeHtml(copy.a11y.videoClose)}">${escapeHtml(copy.video.close)}</button>
          </div>
          <p class="video-body">${escapeHtml(copy.video.body)}</p>
          <div class="video-versions" role="group" aria-label="${escapeHtml(copy.video.title)}">
            ${VIDEO_VERSIONS.map((version) => `<button type="button" data-ref="video-${version.id}" aria-pressed="false" disabled>${escapeHtml(version.title)}</button>`).join("")}
          </div>
          <p class="video-body" data-ref="video-description"></p>
          <p class="video-status" data-ref="video-status" role="status"></p>
          <video data-ref="video" controls playsinline preload="metadata" aria-label="${escapeHtml(copy.a11y.videoPlayer)}"></video>
          <div class="video-foot">
            <a class="video-download" data-ref="video-play" target="_blank" rel="noopener noreferrer">${escapeHtml(copy.video.play)}</a>
            <a class="video-download" data-ref="video-download">${escapeHtml(copy.video.download)}</a>
          </div>
        </div>
      </div>
    </div>
  `;
  const refs = {};
  root.querySelectorAll("[data-ref]").forEach((node) => {
    refs[node.getAttribute("data-ref")] = node;
  });
  root.querySelectorAll("[data-acc]").forEach((button) => {
    button.addEventListener("click", () => {
      const panel = button.closest(".panel");
      const open = panel.classList.toggle("open");
      button.setAttribute("aria-expanded", open ? "true" : "false");
      button.setAttribute("aria-label", open ? copy.a11y.closePanel : copy.a11y.openPanel);
    });
  });
  applyMobileAccordions(root);
  return refs;
}

export function applyMobileAccordions(root) {
  const mobile = window.matchMedia("(max-width: 900px)").matches;
  root.querySelectorAll(".panel").forEach((panel) => {
    const keepOpen = !mobile || panel.getAttribute("data-panel") === "slice";
    panel.classList.toggle("open", keepOpen);
    const button = panel.querySelector("[data-acc]");
    if (button) {
      button.setAttribute("aria-expanded", keepOpen ? "true" : "false");
      button.setAttribute("aria-label", keepOpen ? copy.a11y.closePanel : copy.a11y.openPanel);
    }
  });
}

function panel(id, title, accordion, body) {
  return `
    <section class="panel open" data-panel="${id}">
      <button type="button" class="acc" data-acc="${id}" aria-expanded="true">${escapeHtml(accordion)}</button>
      <h2 class="panel-title">${escapeHtml(title)}</h2>
      <div class="panel-body">${body}</div>
    </section>
  `;
}

export function paintSlider(input) {
  if (!input) return;
  const min = Number(input.min);
  const max = Number(input.max);
  const value = Number(input.value);
  const p = max === min || !Number.isFinite(min) || !Number.isFinite(max) ? 0 : ((value - min) / (max - min)) * 100;
  input.style.setProperty("--p", `${Math.min(100, Math.max(0, p))}%`);
}

export function renderStats(refs, { status, meshCount, candidateCount, sliceCount, warningCount, loaded, total }) {
  const parts = [];
  if (status === "loadingManifest") parts.push(copy.stats.loadingManifest);
  else if (status === "loadingMeshes") {
    parts.push(`${copy.stats.loadingMeshes} ${loaded}/${total}`);
  } else if (status === "loadingSlice") parts.push(copy.stats.loadingSlice);
  else parts.push(copy.stats.ready);
  parts.push(`${copy.stats.meshCount}: ${meshCount}`);
  parts.push(`${copy.stats.candidateCount}: ${candidateCount}`);
  parts.push(`${copy.stats.sliceCount}: ${sliceCount}`);
  refs.stats.textContent = parts.join(" | ");
  void warningCount;
}

function layerStatus(local) {
  if (local && local.error === "missingMesh") return { text: copy.layers.missing, kind: "missing" };
  if (local && local.error) return { text: copy.layers.missing, kind: "missing" };
  if (local && !local.loaded && local.visible) return { text: copy.layers.loading, kind: "loading" };
  if (local && local.visible) return { text: copy.layers.on, kind: "on" };
  return { text: copy.layers.off, kind: "off" };
}

export function renderLayers(refs, manifest, state, handlers) {
  refs.layers.replaceChildren();
  manifest.layers.forEach((layer, order) => {
    const local = state.layers.find((item) => item.id === layer.id);
    const row = document.createElement("div");
    row.className = "layer";
    const rawColor = (local && local.color) || layer.color;
    const color = isCssHexColor(rawColor)
      ? rawColor
      : FALLBACK_LAYER_COLORS[order % FALLBACK_LAYER_COLORS.length];
    const status = layerStatus(local);
    row.innerHTML = `
      <div class="layer-head">
        <label class="switch">
          <input type="checkbox" data-layer="${escapeHtml(layer.id)}" ${local && local.visible ? "checked" : ""} />
          <span class="switch-ui" aria-hidden="true"></span>
          <span class="swatch" style="background:${escapeHtml(color)}"></span>
          <span class="layer-name">${escapeHtml(layer.name || layer.id)}</span>
        </label>
        <span class="layer-status is-${status.kind}">${escapeHtml(status.text)}</span>
      </div>
      <p class="hint">${escapeHtml(layerHintForId(layer.id))}</p>
      <p class="meta">${escapeHtml(layer.review_status || copy.layers.educationalColor)}</p>
      <label class="slider">
        <span class="slider-head">
          <span>${escapeHtml(copy.layers.opacity)}</span>
          <span class="num">${local ? Math.round(local.opacity * 100) : 78}</span>
        </span>
        <input type="range" min="0" max="1" step="0.01" value="${local ? local.opacity : 0.78}" data-opacity="${escapeHtml(layer.id)}" />
      </label>
      <p class="error hidden" data-layer-error="${escapeHtml(layer.id)}"></p>
    `;
    const toggle = row.querySelector("input[data-layer]");
    toggle.setAttribute("aria-label", `${copy.a11y.toggleLayer}: ${layer.name || layer.id}`);
    toggle.addEventListener("change", () => handlers.onToggle(layer.id, toggle.checked));
    const opacity = row.querySelector("input[data-opacity]");
    opacity.setAttribute("aria-label", `${copy.a11y.layerOpacity}: ${layer.name || layer.id}`);
    paintSlider(opacity);
    opacity.addEventListener("input", () => {
      const valueNode = row.querySelector(".slider-head .num");
      if (valueNode) valueNode.textContent = String(Math.round(Number(opacity.value) * 100));
      paintSlider(opacity);
      handlers.onOpacity(layer.id, Number(opacity.value));
    });
    if (local && local.error) {
      const errorNode = row.querySelector("[data-layer-error]");
      errorNode.classList.remove("hidden");
      errorNode.textContent =
        local.error === "missingMesh" ? copy.layers.missingMesh : copy.layers.meshError;
    }
    refs.layers.append(row);
    void order;
  });
}

export function renderTour(refs, tour, activeIndex, onSelect) {
  refs.tour.replaceChildren();
  if (!tour.length) {
    const empty = document.createElement("li");
    empty.textContent = copy.tour.empty;
    refs.tour.append(empty);
    syncTourNav(refs, activeIndex, tour.length);
    return;
  }
  tour.forEach((stop, index) => {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = index === activeIndex ? "stop is-active" : "stop";
    if (index === activeIndex) button.setAttribute("aria-current", "step");
    button.setAttribute("aria-label", `${copy.a11y.tourStop}: ${stop.title || tourFallbackTitle(stop.id)}`);
    button.innerHTML = `<span class="n">${String(index + 1).padStart(2, "0")}</span><span>${escapeHtml(stop.title || tourFallbackTitle(stop.id))}</span>`;
    if (stop.description) {
      const note = document.createElement("small");
      note.textContent = stop.description;
      button.append(note);
    }
    button.addEventListener("click", () => onSelect(index));
    item.append(button);
    refs.tour.append(item);
  });
  syncTourNav(refs, activeIndex, tour.length);
}

export function syncTourNav(refs, tourIndex, tourLength) {
  const started = tourIndex >= 0;
  if (refs["tour-next"]) {
    refs["tour-next"].textContent = started ? copy.tour.next : copy.tour.start;
    refs["tour-next"].disabled = tourLength === 0 || (started && tourIndex >= tourLength - 1);
  }
  if (refs["tour-prev"]) refs["tour-prev"].disabled = !started || tourIndex <= 0;
  if (refs["tour-exit"]) refs["tour-exit"].disabled = !started;
  if (refs["tour-status"]) {
    refs["tour-status"].textContent = started ? copy.tour.active : "";
    refs["tour-status"].classList.toggle("hidden", !started);
  }
  const panel = refs.tour && refs.tour.closest(".panel");
  if (panel) panel.classList.toggle("tour-running", started);
}

export function renderCandidates(refs, annotations, focusId, onFocus) {
  refs.candidates.replaceChildren();
  if (!annotations.length) {
    const empty = document.createElement("p");
    empty.className = "note";
    empty.textContent = copy.candidates.empty;
    refs.candidates.append(empty);
    return;
  }
  annotations.forEach((annotation) => {
    const card = document.createElement("article");
    card.className = annotation.id === focusId ? "card is-active" : "card";
    card.innerHTML = `
      <h3>${escapeHtml(annotation.label || annotation.id)}</h3>
      <p class="meta">${escapeHtml(copy.candidates.statusPrefix)} ${escapeHtml(annotation.review_status || "unverified candidate")}</p>
      <p class="meta">${escapeHtml(copy.candidates.radius)} ${escapeHtml(formatNumber(annotation.radius_mm, 1))}</p>
      <p class="note">${escapeHtml(annotation.description || "")}</p>
      <button type="button">${escapeHtml(copy.candidates.focus)}</button>
    `;
    const button = card.querySelector("button");
    button.setAttribute("aria-label", `${copy.a11y.focusCandidate}: ${annotation.label || annotation.id}`);
    button.addEventListener("click", () => onFocus(annotation.id));
    refs.candidates.append(card);
  });
}

export function renderWarnings(refs, warnings) {
  refs.warnings.replaceChildren();
  (warnings || []).forEach((warning) => {
    const item = document.createElement("li");
    item.textContent = warning;
    refs.warnings.append(item);
  });
  if (!(warnings && warnings.length)) {
    const item = document.createElement("li");
    item.className = "muted";
    item.textContent = copy.stats.ready;
    refs.warnings.append(item);
  }
}

export function renderReadout(refs, selection) {
  if (!selection) {
    refs.readout.textContent = copy.readout.noSelection;
    return;
  }
  if (selection.error === "outOfBounds") {
    refs.readout.textContent = copy.readout.outOfBounds;
    return;
  }
  if (selection.error === "voxelError") {
    refs.readout.textContent = copy.readout.voxelError;
    return;
  }
  const hu = selection.hu == null ? "--" : formatNumber(selection.hu, 0);
  const ras = selection.ras
    ? selection.ras.map((value) => formatNumber(value, 1)).join(", ")
    : "--";
  const lps = selection.lps
    ? selection.lps.map((value) => formatNumber(value, 1)).join(", ")
    : "--";
  const frac = selection.fractional
    ? selection.fractional.map((value) => formatNumber(value, 2)).join(", ")
    : "--";
  refs.readout.textContent = [
    `${copy.readout.hu} ${hu}`,
    `${copy.readout.indices} ${selection.i}, ${selection.j}, ${selection.k}`,
    `${copy.readout.ras} ${ras}`,
    `${copy.readout.lps} ${lps}`,
    `${copy.readout.fractional} ${frac}`,
  ].join(" | ");
}

export function applySliceAspect(refs, aspect) {
  if (!refs["slice-stack"]) return;
  refs["slice-stack"].style.setProperty("--slice-aspect", String(aspect));
}

export function renderOrientation(refs, labels) {
  refs["ori-top"].textContent = labels.top;
  refs["ori-left"].textContent = labels.left;
  refs["ori-right"].textContent = labels.right;
  refs["ori-bottom"].textContent = labels.bottom;
  refs["axis-fallback"].classList.toggle("hidden", labels.mode !== "source-axis");
}

export function renderFocus(refs, stop) {
  const { title, body } = stop || { title: copy.focus.overviewTitle, body: copy.focus.overviewBody };
  refs["focus-title"].textContent = title;
  refs["focus-body"].textContent = body;
}

export function syncSliceControls(refs, state, shape) {
  const extent = sliceExtent(state.axis, shape);
  refs["slice-index"].min = "0";
  refs["slice-index"].max = String(extent.maxIndex);
  refs["slice-index"].value = String(state.index[state.axis]);
  refs.wc.value = String(state.wc);
  refs.ww.value = String(state.ww);
  refs["slice-axis"].querySelectorAll("input").forEach((input) => {
    input.checked = input.value === state.axis;
  });
  if (refs.slice3d) refs.slice3d.checked = Boolean(state.showSlice3d);
  if (refs["slice-index-value"]) refs["slice-index-value"].textContent = String(state.index[state.axis]);
  if (refs["wc-value"]) refs["wc-value"].textContent = String(state.wc);
  if (refs["ww-value"]) refs["ww-value"].textContent = String(state.ww);
  paintSlider(refs["slice-index"]);
  paintSlider(refs.wc);
  paintSlider(refs.ww);
}

export function syncClipControls(refs, state, bounds) {
  refs["clip-enable"].checked = state.clip.enabled;
  refs["clip-warn"].classList.toggle("hidden", !state.clip.enabled);
  refs["clip-axis"].querySelectorAll("input").forEach((input) => {
    input.checked = input.value === state.clip.axis;
  });
  const axisIndex = state.clip.axis === "x" ? 0 : state.clip.axis === "y" ? 1 : 2;
  const min = bounds.min[axisIndex];
  const max = bounds.max[axisIndex];
  refs["clip-pos"].min = String(min);
  refs["clip-pos"].max = String(max);
  refs["clip-pos"].step = String(Math.max((max - min) / 500, 0.1));
  refs["clip-pos"].value = String(state.clip.value);
  if (refs["clip-pos-value"]) refs["clip-pos-value"].textContent = formatNumber(state.clip.value, 1);
  paintSlider(refs["clip-pos"]);
}

export function renderVideoAction(refs, videoState) {
  const button = refs["watch-tour"];
  if (!button) return;
  const status = videoState && videoState.status;
  if (status === "available") {
    button.disabled = Boolean(videoState.open);
    button.textContent = copy.video.watch;
    button.setAttribute("aria-label", copy.a11y.watchTour);
    button.classList.add("is-ready");
  } else if (status === "checking") {
    button.disabled = true;
    button.textContent = copy.video.checking;
    button.setAttribute("aria-label", copy.a11y.watchTourChecking);
    button.classList.remove("is-ready");
  } else {
    button.disabled = true;
    button.textContent = copy.video.unavailable;
    button.setAttribute("aria-label", copy.a11y.watchTourUnavailable);
    button.classList.remove("is-ready");
  }
}

export function applyVideoModal(refs, videoState, message) {
  const open = Boolean(videoState && videoState.open);
  refs["video-backdrop"].classList.toggle("hidden", !open);
  refs["video-dialog"].setAttribute("aria-hidden", open ? "false" : "true");
  const selected = VIDEO_VERSIONS.find((version) => version.id === videoState?.selectedId);
  for (const version of VIDEO_VERSIONS) {
    const button = refs[`video-${version.id}`];
    button.disabled = !videoState?.versions.some((item) => item.id === version.id);
    button.setAttribute("aria-pressed", String(selected?.id === version.id));
  }
  refs["video-description"].textContent = selected ? copy.video[`${selected.id}Description`] : "";
  if (open && selected) {
    refs["video-play"].setAttribute("href", selected.url);
    refs["video-download"].setAttribute("href", selected.download_url);
    refs["video-download"].setAttribute("download", selected.filename);
  } else {
    refs["video-play"].removeAttribute("href");
    refs["video-download"].removeAttribute("href");
    refs["video-download"].removeAttribute("download");
  }
  if (refs["video-status"]) {
    refs["video-status"].textContent = message || "";
    refs["video-status"].classList.toggle("hidden", !message);
  }
  if (open) {
    refs["video-dialog"].setAttribute("aria-label", copy.a11y.videoDialog);
  }
}

export function showFatal(refs, code) {
  refs.fatal.classList.remove("hidden");
  refs["fatal-text"].textContent = copy.errors[code] || copy.errors.noData;
}

export function hideFatal(refs) {
  refs.fatal.classList.add("hidden");
}
