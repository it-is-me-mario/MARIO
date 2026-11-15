const test = require('node:test');
const assert = require('node:assert/strict');
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
