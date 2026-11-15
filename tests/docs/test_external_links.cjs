"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const test = require("node:test");

const script = fs.readFileSync(path.resolve(__dirname, "../../doc/source/_static/external-links.js"), "utf8");

function applyLinks(addresses) {
  const links = addresses.map((href) => ({
    href,
    hostname: URL.canParse(href) ? new URL(href).hostname : "",
    attributes: new Map([["target", "_blank"]]),
    setAttribute(name, value) { this.attributes.set(name, value); },
    removeAttribute(name) { this.attributes.delete(name); },
  }));
  const document = {
    addEventListener(name, callback) { callback(); },
    querySelectorAll() { return links; },
    querySelector() { return null; },
  };
  vm.runInNewContext(script, { document, URL });
  return links;
}

test("MARIO sites navigate in the current tab", () => {
  const links = applyLinks([
    "https://marioproject.com/",
    "https://www.marioproject.com/en/latest/",
    "https://tutorials.marioproject.com/economy-wide-impact-assessment/",
    "https://explorer.marioproject.com/resources/data-explorer/scope.html#countries",
  ]);
  for (const link of links) assert.equal(link.attributes.has("target"), false);
});

test("Other websites retain external-link behaviour", () => {
  const links = applyLinks([
    "https://github.com/it-is-me-mario/Tutorials",
    "https://cvxlab.readthedocs.io/en/dev/",
    "https://marioproject.com.example.org/",
    "https://marioproject.com@example.org/",
    "http://",
  ]);
  for (const link of links) {
    assert.equal(link.attributes.get("target"), "_blank");
    assert.equal(link.attributes.get("rel"), "noopener noreferrer");
  }
});
