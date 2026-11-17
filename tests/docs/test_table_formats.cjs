"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "../..");
const script = fs.readFileSync(path.join(root, "doc/source/_static/table-formats.js"), "utf8");

for (const kind of ["iot", "sut"]) {
  const html = fs.readFileSync(path.join(root, `doc/source/get_started/_generated/${kind}_structure.html`), "utf8");
  const fields = {};
  for (const match of html.matchAll(/<select data-config="([^"]+)">([\s\S]*?)<\/select>/g)) {
    fields[match[1]] = { dataset: { config: match[1] }, value: match[2].match(/value="([^"]+)"/)[1] };
  }
  const templates = Array.from(html.matchAll(/<template data-config-grid="([^"]+)">/g), (match) => ({
    dataset: { configGrid: match[1] },
    content: { cloneNode: () => ({ key: match[1] }) },
  }));
  const factorName = kind === "iot" ? "V" : "Va";
  const importName = kind === "iot" ? "IMP" : "IMP_a";
  const definitions = [factorName, importName].map((name) => ({
    id: `matrix-${name}`, rows: { dataset: { defaultRows: "Default row indices" } },
    querySelector() { return this.rows; },
  }));
  const links = definitions.map((definition) => ({
    dataset: { matrixLink: definition.id }, setAttribute() {}, removeAttribute() {},
  }));
  const imports = [{}, {}, {}];
  const trade = {};
  const regionalLegend = {};
  const importLegend = {};
  const explanation = {};
  let selectedKey;
  let change;
  let hashChange;
  const controls = {
    querySelectorAll: () => Object.values(fields),
    addEventListener(event, handler) { change = handler; },
  };
  const scroll = {
    querySelectorAll: () => links,
    replaceChildren(content) { selectedKey = content.key; },
  };
  const map = {
    classList: { add() {}, toggle() {} },
    querySelector(selector) {
      return {
        ".table-map__controls": controls, ".table-map__scroll": scroll,
        "[data-trade-control]": kind === "sut" ? trade : null,
        "[data-regional-legend]": regionalLegend, "[data-import-legend]": importLegend,
        "[data-config-explanation]": explanation,
      }[selector];
    },
    querySelectorAll(selector) {
      return {
        "[data-matrix-definition]": definitions, "[data-config-grid]": templates,
        "[data-import-control]": imports,
      }[selector];
    },
    addEventListener() {},
  };
  const window = {
    location: { hash: "" },
    addEventListener(event, handler) { hashChange = handler; },
  };
  const document = {
    querySelectorAll: (selector) => selector === "[data-table-map]" ? [map] : [],
    addEventListener(event, handler) { handler(); },
  };
  vm.runInNewContext(script, { document, window });

  const details = kind === "sut" ? ["total", "commodity", "activity"] : ["total", "sector"];
  for (const mode of ["flows", "coefficients"]) {
    fields.mode.value = mode;
    fields.scope.value = "single-region";
    for (const representation of ["factor-accounts", "separate"]) {
      fields.imports.value = representation;
      for (const resolution of ["aggregate", "by_region"]) {
        fields.resolution.value = resolution;
        for (const detail of details) {
          fields.detail.value = detail;
          change();
          assert.equal(selectedKey, `single-region/external-trade/${representation}/${mode}/${resolution}/${detail}`);
          assert.ok(imports.every((control) => control.hidden === false));
          const rows = definitions[1].rows.textContent;
          assert.equal(rows.includes("Foreign region"), resolution === "by_region");
          assert.equal(rows.includes("One total-import row"), detail === "total" && resolution === "aggregate");
          const factorRows = definitions[0].rows.textContent;
          assert.equal(factorRows.includes("followed by import rows"), representation === "factor-accounts");
          if (representation === "factor-accounts") assert.ok(factorRows.includes(rows));
          assert.equal(importLegend.hidden, false);
        }
      }
    }
    fields.scope.value = "multi-region";
    for (const representation of kind === "sut" ? ["isard", "chenery-moses"] : ["bilateral"]) {
      if (fields.trade) fields.trade.value = representation;
      change();
      assert.equal(selectedKey, `multi-region/${representation}/factor-accounts/${mode}`);
      assert.ok(imports.every((control) => control.hidden === true));
      assert.equal(importLegend.hidden, true);
      assert.equal(definitions[0].rows.textContent, "Default row indices");
      assert.equal(definitions[1].rows.textContent, "Default row indices");
    }
  }
  window.location.hash = `#matrix-${importName}`;
  hashChange();
  assert.equal(fields.scope.value, "single-region");
  assert.equal(fields.imports.value, "separate");
}

console.log("PASS: IOT/SUT parameter selectors, dynamic axes, regional scope and import anchors");
