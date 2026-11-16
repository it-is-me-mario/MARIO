"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const test = require("node:test");

const themeRoot = path.resolve(__dirname, "../../doc/source/_themes/mario");
const bootstrap = fs.readFileSync(path.join(themeRoot, "partials/theme.html"), "utf8")
  .match(/<script>([\s\S]*)<\/script>/)[1];
const controls = fs.readFileSync(path.join(themeRoot, "static/mario.js"), "utf8");

function page(address, jar = [], options = {}) {
  const location = new URL(address);
  const local = options.local || new Map();
  const listeners = new Map();
  const clicks = [];
  let systemDark = Boolean(options.systemDark);
  const on = (name, callback) => {
    if (!listeners.has(name)) listeners.set(name, []);
    listeners.get(name).push(callback);
  };
  const root = { dataset: {}, classList: { add() {}, remove() {}, toggle() {} } };
  const document = {
    documentElement: root, hidden: false, readyState: "complete",
    addEventListener: on,
    querySelector() { return null; },
    querySelectorAll(selector) {
      return selector === "[data-theme-toggle]" ? [0, 1].map((index) => ({
        addEventListener(name, callback) { if (name === "click") clicks[index] = callback; },
      })) : [];
    },
    getElementById() { return null; },
    get cookie() {
      if (options.cookiesBlocked) throw new Error("Cookies blocked");
      return jar.filter((cookie) => location.hostname === cookie.domain || location.hostname.endsWith("." + cookie.domain))
        .map((cookie) => cookie.pair).join("; ");
    },
    set cookie(value) {
      if (options.cookiesBlocked) throw new Error("Cookies blocked");
      const domain = value.match(/; Domain=([^;]+)/)?.[1] || location.hostname;
      const name = value.split("=")[0];
      assert.ok(location.hostname === domain || location.hostname.endsWith("." + domain));
      const previous = jar.findIndex((cookie) => cookie.domain === domain && cookie.name === name);
      if (previous >= 0) jar.splice(previous, 1);
      jar.push({ domain, name, pair: value.split(";")[0], attributes: value });
    },
  };
  const window = {
    location, addEventListener: on,
    matchMedia(query) { return { matches: query === "(prefers-color-scheme: dark)" && systemDark }; },
    localStorage: {
      getItem(key) { if (options.storageBlocked) throw new Error("Storage blocked"); return local.get(key) ?? null; },
      setItem(key, value) { if (options.storageBlocked) throw new Error("Storage blocked"); local.set(key, value); },
    },
    sessionStorage: { getItem() { return null; }, removeItem() {} },
    setTimeout() { return 1; }, clearTimeout() {},
  };
  const context = vm.createContext({ window, document, location, URL, performance: { getEntriesByType() { return []; } } });
  vm.runInContext(bootstrap, context);
  return {
    root, local, jar, document, theme: window.MarioTheme,
    dispatch(name, event = {}) { for (const callback of listeners.get(name) || []) callback(event); },
    changeSystem(dark) { systemDark = dark; },
    click(index = 0) {
      if (!clicks.length) vm.runInContext(controls, context);
      clicks[index]();
    },
  };
}

test("a new visitor follows the system without saving an automatic default", () => {
  const site = page("https://www.marioproject.com/en/preview/", [], { systemDark: true });
  assert.equal(site.root.dataset.theme, undefined);
  assert.equal(site.theme.current(), "dark");
  site.changeSystem(false);
  assert.equal(site.theme.current(), "light");
  assert.equal(site.local.size, 0);
  assert.equal(site.jar.length, 0);
});

test("header and footer controls carry the latest explicit choice across all three hosts", () => {
  const jar = [];
  const mario = page("https://www.marioproject.com/en/preview/", jar);
  mario.click();
  assert.equal(mario.root.dataset.theme, "dark");
  const tutorials = page("https://tutorials.marioproject.com/preview/", jar);
  assert.equal(tutorials.root.dataset.theme, "dark");
  tutorials.click(1);
  const explorer = page("https://explorer.marioproject.com/preview/", jar, { systemDark: true });
  assert.equal(explorer.root.dataset.theme, "light");
  explorer.click();
  assert.equal(page("https://www.marioproject.com/en/preview/user_guide/index.html", jar).root.dataset.theme, "dark");
  assert.match(jar[0].attributes, /Domain=marioproject\.com; Path=\//);
  assert.match(jar[0].attributes, /Max-Age=\d+; SameSite=Lax; Secure/);
});

test("an existing local choice migrates once and stale preferences cannot overwrite it", () => {
  const jar = [];
  page("https://www.marioproject.com/en/preview/", jar, { local: new Map([["mario-theme", "light"]]) });
  const oldLocal = new Map([["mario-theme", "dark"]]);
  const tutorials = page("https://tutorials.marioproject.com/preview/", jar, { local: oldLocal });
  assert.equal(tutorials.root.dataset.theme, "light");
  assert.equal(oldLocal.get("mario-theme"), "light");
  assert.equal(jar[0].pair, "mario-theme=light");
});

for (const event of ["pageshow", "focus", "visibilitychange"]) {
  test(`returning to a page resynchronizes the last choice on ${event}`, () => {
    const jar = [];
    const mario = page("https://www.marioproject.com/en/preview/", jar);
    mario.click();
    const explorer = page("https://explorer.marioproject.com/preview/", jar);
    explorer.click();
    assert.equal(mario.root.dataset.theme, "dark");
    mario.dispatch(event, { persisted: true });
    assert.equal(mario.root.dataset.theme, "light");
    assert.equal(jar[0].pair, "mario-theme=light");
  });
}

test("same-origin tab changes work with the local fallback", () => {
  const local = new Map();
  const first = page("http://localhost:8773/", [], { local });
  const second = page("http://localhost:8773/guide.html", [], { local });
  second.click();
  first.dispatch("storage", { key: "mario-theme", newValue: "dark" });
  assert.equal(first.root.dataset.theme, "dark");
  assert.equal(first.jar.length, 0);
});

test("blocked local storage still permits cross-host preference sharing", () => {
  const jar = [];
  const mario = page("https://www.marioproject.com/en/preview/", jar, { storageBlocked: true });
  mario.click();
  const tutorials = page("https://tutorials.marioproject.com/preview/", jar, { storageBlocked: true });
  assert.equal(tutorials.root.dataset.theme, "dark");
});

test("blocked cookies retain a local preference and do not break the controls", () => {
  const local = new Map();
  const first = page("https://www.marioproject.com/en/preview/", [], { local, cookiesBlocked: true });
  first.click();
  assert.equal(page("https://www.marioproject.com/en/preview/guide.html", [], { local, cookiesBlocked: true }).root.dataset.theme, "dark");
  const blocked = page("https://www.marioproject.com/", [], { cookiesBlocked: true, storageBlocked: true });
  blocked.click();
  blocked.dispatch("focus");
  assert.equal(blocked.root.dataset.theme, "dark");
});

test("invalid preferences and unrelated hostnames do not become shared choices", () => {
  const jar = [{ domain: "marioproject.com", name: "mario-theme", pair: "mario-theme=invalid" }];
  const mario = page("https://www.marioproject.com/", jar, { local: new Map([["mario-theme", "invalid"]]) });
  assert.equal(mario.root.dataset.theme, undefined);
  mario.theme.set("invalid");
  assert.equal(jar[0].pair, "mario-theme=invalid");
  for (const address of ["https://marioproject.com.example.org/", "https://fake-marioproject.com/", "http://127.0.0.1:8773/"]) {
    const unrelated = page(address);
    unrelated.click();
    assert.equal(unrelated.root.dataset.theme, "dark");
    assert.equal(unrelated.jar.length, 0);
  }
});

test("the shared bootstrap is in the head so the stored choice precedes rendering", () => {
  const layout = fs.readFileSync(path.join(themeRoot, "layout.html"), "utf8");
  const head = layout.match(/block extrahead([\s\S]*?)endblock/)[1];
  assert.match(head, /include "partials\/theme\.html"/);
});
