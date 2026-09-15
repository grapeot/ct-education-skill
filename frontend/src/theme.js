export const THEME_KEY = "ct-education-theme";
export const PREVIEW_TITLE = "Choose your explorer style";
export const THEMES = [
  { id: "clinical", name: "Clinical", description: "Crisp cobalt. Precise cardless grid.", background: "#eaf0f6", ink: "#284763", line: "#a4b5c7" },
  { id: "atlas", name: "Atlas", description: "Warm paper. Quiet rules. Serif type.", background: "#eee6d7", ink: "#514637", line: "#b6ab98" },
  { id: "blueprint", name: "Blueprint", description: "Navy and cyan. Compact monospace.", background: "#102b43", ink: "#c9eafa", line: "#4b7591" },
  { id: "aurora", name: "Aurora", description: "Ice and lavender. Airy research.", background: "#e8eaf7", ink: "#494e79", line: "#b4b8d4" },
  { id: "studio", name: "Studio", description: "Cream, coral and sage. Softly rounded.", background: "#e5ebe2", ink: "#3e5548", line: "#a7b7a4" },
];
export const DEFAULT_THEME = THEMES.find((theme) => theme.id === "aurora");

export function resolveTheme(id) {
  return THEMES.find((theme) => theme.id === id) || DEFAULT_THEME;
}

export function readTheme(storage) {
  try {
    return resolveTheme(storage.getItem(THEME_KEY));
  } catch {
    return DEFAULT_THEME;
  }
}

export function saveTheme(storage, id) {
  try {
    storage.setItem(THEME_KEY, resolveTheme(id).id);
  } catch {
    // A denied storage permission must not prevent live previewing.
  }
}

export function mountThemePicker(root, onChange) {
  let current;
  try {
    current = readTheme(window.localStorage);
  } catch {
    current = DEFAULT_THEME;
  }
  const picker = document.createElement("section");
  picker.className = "theme-picker";
  picker.setAttribute("aria-label", PREVIEW_TITLE);
  picker.innerHTML = `
    <div class="theme-heading"><span class="preview-label">Preview</span><h1>${PREVIEW_TITLE}</h1><span class="theme-active" role="status"></span></div>
    <div class="theme-choices" role="group" aria-label="Explorer style">
      ${THEMES.map((theme, i) => `<button type="button" class="theme-choice" data-theme-choice="${theme.id}" aria-pressed="false" aria-label="${i + 1}. ${theme.name}: ${theme.description}"><span class="theme-number" aria-hidden="true">${i + 1}</span><span class="theme-name">${theme.name}</span><span class="theme-description">${theme.description}</span></button>`).join("")}
    </div>
    <p class="theme-mobile-description"></p>
    <p class="theme-reassurance">Switching styles keeps your active slice and view intact. Only your theme preference is saved.</p>`;
  root.prepend(picker);
  function apply(theme) {
    current = theme;
    document.documentElement.dataset.theme = theme.id;
    picker.querySelector(".theme-active").textContent = theme.name;
    picker.querySelector(".theme-mobile-description").textContent = theme.description;
    picker.querySelectorAll("[data-theme-choice]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.themeChoice === theme.id));
    });
    onChange(theme);
  }
  picker.addEventListener("click", (event) => {
    const button = event.target.closest("[data-theme-choice]");
    if (!button) return;
    apply(resolveTheme(button.dataset.themeChoice));
    try { saveTheme(window.localStorage, current.id); } catch { /* Storage may be unavailable. */ }
  });
  picker.addEventListener("keydown", (event) => {
    const button = event.target.closest("[data-theme-choice]");
    if (!button || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const buttons = Array.from(picker.querySelectorAll("[data-theme-choice]"));
    const index = buttons.indexOf(button);
    const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length;
    buttons[next].focus();
    buttons[next].click();
  });
  apply(current);
  return () => current;
}
