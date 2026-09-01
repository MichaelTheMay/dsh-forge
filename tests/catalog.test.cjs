// Behavior tests for the exported logic. No browser, network, or local runner.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.join(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'web/index.html'), 'utf8');
const script = fs.readFileSync(path.join(root, 'web/launcher.js'), 'utf8');
const snapshot = JSON.parse(fs.readFileSync(path.join(root, 'data/public-repos.seed.json'), 'utf8'));
class Logic {
  constructor(props) { this.props = props; }
  setState(change) { Object.assign(this.state, typeof change === 'function' ? change(this.state) : change); }
}
const windowStub = { location: { hash: '' }, __dcPrecompiledLogicFactories: {} };
const clipboard = [];
const navigatorStub = { clipboard: { writeText: async value => { clipboard.push(value); } } };
new Function('window', 'navigator', script)(windowStub, navigatorStub);
const Component = windowStub.__dcPrecompiledLogicFactories.$root(Logic);
const CATALOG = Component.catalog;
const CATALOG_SNAPSHOT = Component.catalogSnapshot;
function instance(props = {}) { const c = new Component(props); c.flash = value => { c.lastMessage = value; }; return c; }

test('browser entrypoint uses precompiled logic under the strict CSP', () => {
  const inline = html.match(/<script type="text\/x-dc"[^>]*>([\s\S]*?)<\/script>/)[1];
  assert.equal(inline.trim(), '');
  assert.match(html, /<script src="\.\/launcher\.js"><\/script>/);
  assert(!/\beval\s*\(|new Function\s*\(/.test(script));
  assert.equal(typeof Component, 'function');
});

test('embedded snapshot exactly matches the JSON and GitHub top-ten response', () => {
  assert.deepEqual(CATALOG_SNAPSHOT, snapshot);
  const raw = JSON.parse(fs.readFileSync(path.join(root, 'data/github-forks.response.json'), 'utf8'));
  assert.equal(CATALOG.length, 10);
  assert.deepEqual(CATALOG.map(r => [r.github_id, r.github_stars]), raw.map(r => [r.id, r.stargazers_count]));
  assert.equal(new Set(CATALOG.map(r => r.github_id)).size, 10);
  assert(CATALOG.every(r => /^[a-f0-9]{40}$/.test(r.head_sha)));
});
test('launcher remains the default and Public Repos is a separate view', () => {
  const c = instance(); assert(c.renderVals().showLaunch); assert(!c.renderVals().showCatalog);
  assert.equal(c.state.cells.length, 0);
  assert.equal(c.renderVals().modeLabel, 'portable preview');
  assert.match(c.renderVals().launchHint, /No sample process is presented as real/);
  c.renderVals().goCatalog(); assert(c.renderVals().showCatalog); assert(!c.renderVals().showLaunch);
  assert.equal(windowStub.location.hash, 'public-repos');
  c.renderVals().goLaunch(); assert(c.renderVals().showLaunch);
});
test('preview contains no personal-name or private-home leakage', () => {
  assert(!/michael(?:the)?may|\/home\/[^/]+\//i.test(html));
  assert(!/pid:\s*4\d{4}|loader settled|process alive · pid/i.test(html));
});
test('live status replaces preview inventory instead of merging it', () => {
  const c = instance();
  c.applyStatus({
    trees: [{ id: 'real', name: 'detected', short: 'detected', kind: 'source', version: '1', path: '~/dsh', exe: '~/dsh/dsh', node: 'bundled', git: null, trust: 'personal', launchability: 'ready' }],
    cells: [], suggested_port: 3210, coverage_gaps: [], credentials: []
  });
  assert.equal(c.state.trees.length, 1);
  assert.equal(c.state.trees[0].id, 'real');
  assert.equal(c.renderVals().modeLabel, 'launcher alpha');
  assert.equal(c.renderVals().suggested, 3210);
});
test('most-starred order retains GitHub order for ties', () => {
  const rows = instance().renderVals().results;
  const stars = rows.map(r => r.github_stars);
  assert.deepEqual(stars, [...stars].sort((a,b) => b-a));
  for (const count of new Set(stars)) {
    assert.deepEqual(rows.filter(r => r.github_stars === count).map(r => r.id),
      CATALOG.filter(r => r.github_stars === count).map(r => r.id));
  }
});
test('search handles case, whitespace, and multiple terms', () => {
  const c = instance(); const target = CATALOG[1];
  c.renderVals().setQuery({ target: { value: '  ' + target.owner.toUpperCase() + '   ' + target.name + '  ' } });
  assert.deepEqual(c.renderVals().results.map(r => r.id), [target.id]);
});
test('filtered-out selection never leaves stale detail content', () => {
  const c = instance(); c.renderVals().results[3].select();
  c.renderVals().setQuery({ target: { value: CATALOG[4].slug } });
  assert.equal(c.renderVals().detail.id, CATALOG[4].id);
  c.renderVals().setQuery({ target: { value: 'no-such-repository-000' } });
  assert(c.renderVals().noResults); assert(!c.renderVals().hasDetail);
  assert.deepEqual(c.renderVals().detailRows, []);
});
test('Plugins has an honest empty state and reset recovers all ten forks', () => {
  const c = instance(); c.renderVals().repoTypes.find(f => f.id === 'plugin').select();
  assert.equal(c.renderVals().results.length, 0);
  assert.equal(c.renderVals().emptyTitle, 'No plugins imported yet');
  c.renderVals().resetCatalogFilters(); assert.equal(c.renderVals().results.length, 10);
});
test('recent and name sort change order without changing catalog membership', () => {
  const c = instance(); c.renderVals().setCatalogSort({ target: { value: 'recent' } });
  const dates = c.renderVals().results.map(r => Date.parse(r.pushed_at));
  assert.deepEqual(dates, [...dates].sort((a,b) => b-a));
  c.renderVals().setCatalogSort({ target: { value: 'name' } });
  const names = c.renderVals().results.map(r => r.slug);
  assert.deepEqual(names, [...names].sort((a,b) => a.localeCompare(b)));
});
test('license filter is based on reported metadata, not a verification claim', () => {
  const c = instance(); c.renderVals().toggleKnownLicense({ target: { checked: true } });
  assert(c.renderVals().results.every(r => r.licenseOk));
  assert(CATALOG.every(r => r.verification.security_verified === false));
});
test('copy pinned ref actually writes the captured commit URL', async () => {
  const c = instance(); await c.renderVals().copyRef();
  assert.equal(clipboard.at(-1), snapshot.entries[0].repository_url + '/tree/' + snapshot.entries[0].head_sha);
  assert.equal(c.lastMessage, 'Copied repository reference');
});
test('catalog interactions cannot add, stop, or modify local cells', () => {
  const c = instance(); const before = JSON.stringify(c.state.cells);
  c.renderVals().goCatalog(); c.renderVals().results[5].select();
  c.renderVals().setQuery({ target: { value: 'desktop' } });
  c.renderVals().goLaunch(); assert.equal(JSON.stringify(c.state.cells), before);
});
test('public code actions are disabled and the snapshot has no fabricated analysis', () => {
  const section = html.slice(html.indexOf('<main class="public-browser"'), html.indexOf('<sc-if value="{{ previewOpen }}"'));
  assert.equal((section.match(/<button disabled title=/g) || []).length, 3);
  assert(!/onClick="{{.*(?:install|clone|run|sandbox)/i.test(section));
  assert(!/signed snapshot v42|nmarquez\/|@kv\/|orbit-labs\//.test(script));
  assert(CATALOG.every(r => r.analysis_status === 'not_analyzed'));
});
