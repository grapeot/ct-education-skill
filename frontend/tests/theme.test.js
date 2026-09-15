import test from "node:test";
import assert from "node:assert/strict";
import { THEMES, THEME_KEY, resolveTheme, readTheme, saveTheme } from "../src/theme.js";

test("preview has five unique choices and the selected Aurora fallback", () => {
  assert.deepEqual(THEMES.map(({ id }) => id), ["clinical", "atlas", "blueprint", "aurora", "studio"]);
  for (const id of [undefined, null, "", "unknown", "__proto__", { id: "atlas" }]) {
    assert.equal(resolveTheme(id).id, "aurora");
  }
});

test("theme persistence stores only an allowlisted style identifier", () => {
  const stored = new Map();
  const storage = { getItem: (key) => stored.get(key), setItem: (key, value) => stored.set(key, value) };
  for (const { id } of THEMES) {
    saveTheme(storage, id);
    assert.equal(readTheme(storage).id, id);
    assert.deepEqual([...stored.entries()], [[THEME_KEY, id]]);
  }
  saveTheme(storage, { selection: "not a theme" });
  assert.equal(stored.get(THEME_KEY), "aurora");
});

test("blocked browser storage cannot break the preview", () => {
  const storage = { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); } };
  assert.equal(readTheme(storage).id, "aurora");
  assert.doesNotThrow(() => saveTheme(storage, "atlas"));
  assert.equal(readTheme(null).id, "aurora");
});

test("old preview choices do not override the selected default", () => {
  const values = new Map([["ct-education-preview-theme", "studio"]]);
  assert.equal(readTheme({ getItem: (key) => values.get(key) }).id, "aurora");
});
