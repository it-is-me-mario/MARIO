const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {updateLinks, isGalleryContext, withGalleryContext} = require('../../doc/source/_static/docs-versions.js');

const catalogue = {versions: {
  latest: {url: 'https://www.marioproject.com/en/latest/', documents: {'guide/page': ['shared']}},
  dev: {url: 'https://www.marioproject.com/en/dev/', documents: {'guide/page': ['shared', 'new'], 'dev-only': []}},
}};

function targets(document, hash) {
  const links = ['latest', 'dev'].map(key => ({dataset: {docsVersion: key}}));
  const location = new URL('https://www.marioproject.com/en/latest/' + document + '.html' + hash);
  updateLinks({dataset: {document}, querySelectorAll: () => links}, catalogue, location);
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

test('switching between the library and Model Gallery keeps a page and anchor available in both', () => {
  const url = 'https://www.marioproject.com/en/model_gallery/';
  const versions = {...catalogue.versions, model_gallery: {
    url, kind: 'gallery', documents: {'guide/page': ['shared']},
  }};
  const gallery = {dataset: {docsVersion: 'model_gallery'}};
  const latest = {dataset: {docsVersion: 'latest'}};
  const menu = {dataset: {document: 'guide/page', channel: 'latest'},
    querySelectorAll: () => [gallery, latest]};
  const location = new URL(versions.latest.url + 'guide/page.html#shared');
  updateLinks(menu, {versions}, location);
  assert.equal(gallery.href, url + 'guide/page.html#shared');
  assert.equal(latest.href, versions.latest.url + 'guide/page.html#shared');

  menu.dataset.channel = 'model_gallery';
  updateLinks(menu, {versions}, new URL(gallery.href));
  assert.equal(latest.href, versions.latest.url + 'guide/page.html#shared');
  assert.equal(gallery.href, url + 'guide/page.html#shared');
});

test('the Gallery choice preserves the current page when there is no Gallery edition', () => {
  const gallery = {dataset: {docsVersion: 'model_gallery'}};
  const menu = {dataset: {document: 'guide/page'}, querySelectorAll: () => [gallery]};
  for (const address of [
    'https://tutorials.marioproject.com/bonsai-ghg/index.html',
    'https://explorer.marioproject.com/dev/resources/data-explorer/compare.html',
    'https://www.marioproject.com/en/latest/guide/page.html',
  ]) {
    const location = new URL(address + '?year=2021#shared');
    updateLinks(menu, catalogue, location);
    assert.equal(gallery.href, address + '?year=2021&mario_channel=model_gallery#shared');
    assert.equal(isGalleryContext(new URL(gallery.href), 'latest'), true);
  }
});

test('a compatibility redirect does not count as a page in the destination version', () => {
  const latest = {dataset: {docsVersion: 'latest'}};
  const latestVersion = {...catalogue.versions.latest, redirects: ['guide/page']};
  const menu = {dataset: {document: 'guide/page'}, querySelectorAll: () => [latest]};
  updateLinks(menu, {versions: {latest: latestVersion}},
    new URL('https://www.marioproject.com/en/model_gallery/guide/page.html'));
  assert.equal(latest.href, latestVersion.url + 'index.html');
});

test('version targets follow anchors selected after the page loads', async () => {
  const links = ['latest', 'dev'].map(key => ({dataset: {docsVersion: key}}));
  const events = {};
  const location = new URL('https://www.marioproject.com/en/latest/guide/page.html#shared');
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


test('Gallery visits carry the channel through Tutorials and Explorer links', () => {
  const from = new URL('https://www.marioproject.com/en/model_gallery/');
  assert.equal(isGalleryContext(from, 'model_gallery'), true);
  for (const hostname of ['tutorials.marioproject.com', 'explorer.marioproject.com']) {
    const destination = withGalleryContext(new URL('https://' + hostname + '/topic/index.html?year=2021#details'));
    assert.equal(destination.href, 'https://' + hostname + '/topic/index.html?year=2021&mario_channel=model_gallery#details');
    assert.equal(isGalleryContext(destination, 'latest'), true);
    assert.equal(isGalleryContext(new URL('https://' + hostname + '/dev/'), 'dev'), false);
    assert.equal(withGalleryContext(new URL('https://' + hostname + '/notebook.ipynb')), undefined);
  }
});

test('Gallery navigation returns from a shared site to its matching MARIO pages', () => {
  const target = withGalleryContext(new URL('https://www.marioproject.com/en/latest/user_guide/configuration/index.html'));
  assert.equal(target.href, 'https://www.marioproject.com/en/model_gallery/user_guide/configuration/index.html');
  const teaching = withGalleryContext(new URL('https://www.marioproject.com/en/dev/resources/teaching.html#courses'));
  assert.equal(teaching.href, 'https://www.marioproject.com/en/model_gallery/resources/teaching.html#courses');
  const formats = withGalleryContext(new URL('https://www.marioproject.com/en/latest/get_started/table_formats.html'));
  assert.equal(formats.href, 'https://www.marioproject.com/en/model_gallery/get_started/table_formats.html');
});

test('leaving Gallery mode through the selector keeps the available satellite page and anchor', () => {
  const link = {dataset: {docsVersion: 'dev'}};
  const options = {versions: {
    dev: {url: 'https://explorer.marioproject.com/dev/', documents: {'guide/page': ['shared']}},
  }};
  updateLinks({dataset: {document: 'guide/page', channel: 'model_gallery'}, querySelectorAll: () => [link]},
    options, new URL('https://explorer.marioproject.com/guide/page.html?mario_channel=model_gallery#shared'));
  assert.equal(link.href, 'https://explorer.marioproject.com/dev/guide/page.html#shared');
});
