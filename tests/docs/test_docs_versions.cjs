const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {updateLinks} = require('../../doc/source/_static/docs-versions.js');

const catalogue = {versions: {
  latest: {url: 'https://www.marioproject.com/en/latest/', documents: {'guide/page': ['shared']}},
  dev: {url: 'https://www.marioproject.com/en/dev/', documents: {'guide/page': ['shared', 'new'], 'dev-only': []}},
}};

function targets(document, hash) {
  const links = ['latest', 'dev'].map(key => ({dataset: {docsVersion: key}}));
  updateLinks({dataset: {document}, querySelectorAll: () => links}, catalogue, {hash});
  return links.map(link => link.href);
}

test('switching preserves a shared page and anchor', () => {
  assert.deepEqual(targets('guide/page', '#shared'), [
    'https://www.marioproject.com/en/latest/guide/page.html#shared',
    'https://www.marioproject.com/en/dev/guide/page.html#shared',
  ]);
});
test('new pages fall back to the other version home', () => {
  assert.deepEqual(targets('dev-only', ''), [
    'https://www.marioproject.com/en/latest/index.html',
    'https://www.marioproject.com/en/dev/dev-only.html',
  ]);
});
test('new anchors are kept only where present', () => {
  assert.deepEqual(targets('guide/page', '#new'), [
    'https://www.marioproject.com/en/latest/guide/page.html',
    'https://www.marioproject.com/en/dev/guide/page.html#new',
  ]);
});
test('malformed URL fragments retain valid page links', () => {
  assert.deepEqual(targets('guide/page', '#%'), [
    'https://www.marioproject.com/en/latest/guide/page.html',
    'https://www.marioproject.com/en/dev/guide/page.html',
  ]);
});

test('Model Gallery opens its index even when both sections have a page with the same name', () => {
  const url = 'https://www.marioproject.com/en/model_gallery/';
  const versions = {...catalogue.versions, model_gallery: {
    url, kind: 'gallery', documents: {'guide/page': ['shared']},
  }};
  const gallery = {dataset: {docsVersion: 'model_gallery'}};
  const latest = {dataset: {docsVersion: 'latest'}};
  const menu = {dataset: {document: 'guide/page', channel: 'latest'},
    querySelectorAll: () => [gallery, latest]};
  updateLinks(menu, {versions}, {hash: '#shared'});
  assert.equal(gallery.href, url);
  assert.equal(latest.href, versions.latest.url + 'guide/page.html#shared');

  menu.dataset.channel = 'model_gallery';
  updateLinks(menu, {versions}, {hash: '#shared'});
  assert.equal(latest.href, versions.latest.url);
  assert.equal(gallery.href, url + 'guide/page.html#shared');
});

test('version targets follow anchors selected after the page loads', async () => {
  const links = ['latest', 'dev'].map(key => ({dataset: {docsVersion: key}}));
  const events = {};
  const location = {hash: '#shared'};
  const menu = {dataset: {document: 'guide/page'}, querySelectorAll: () => links,
    addEventListener: () => {}};
  const script = fs.readFileSync(path.join(__dirname, '../../doc/source/_static/docs-versions.js'), 'utf8');
  vm.runInNewContext(script, {
    URL, document: {querySelector: () => menu, addEventListener: () => {}},
    window: {location, addEventListener: (name, listener) => { events[name] = listener; }},
    fetch: async () => ({ok: true, json: async () => catalogue}),
  });
  await new Promise(resolve => setImmediate(resolve));
  location.hash = '#new';
  events.hashchange();
  assert.deepEqual(links.map(link => link.href), [
    'https://www.marioproject.com/en/latest/guide/page.html',
    'https://www.marioproject.com/en/dev/guide/page.html#new',
  ]);
});
