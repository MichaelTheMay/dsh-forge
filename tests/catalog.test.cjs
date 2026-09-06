// Behavior tests for the exported logic. No browser, network, or local runner.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.join(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'web/index.html'), 'utf8');
const script = fs.readFileSync(path.join(root, 'web/launcher.js'), 'utf8');
const snapshot = JSON.parse(fs.readFileSync(path.join(root, 'data/public-repos.seed.json'), 'utf8'));
const packageFeed = JSON.parse(fs.readFileSync(path.join(root, 'data/package-catalog.seed.json'), 'utf8'));
class Logic {
  constructor(props) { this.props = props; }
  setState(change) { Object.assign(this.state, typeof change === 'function' ? change(this.state) : change); }
}
const windowStub = { location: { hash: '', href: 'http://127.0.0.1:3090/' }, __dcPrecompiledLogicFactories: {} };
const clipboard = [];
const navigatorStub = { clipboard: { writeText: async value => { clipboard.push(value); } } };
new Function('window', 'navigator', script)(windowStub, navigatorStub);
const Component = windowStub.__dcPrecompiledLogicFactories.$root(Logic);
const CATALOG = Component.catalog;
const CATALOG_SNAPSHOT = Component.catalogSnapshot;
function instance(props = {}, hash = '') {
  windowStub.location.hash = hash;
  const c = new Component(props);
  c.flash = value => { c.lastMessage = value; };
  return c;
}

test('browser entrypoint uses precompiled logic under the strict CSP', () => {
  const inline = html.match(/<script type="text\/x-dc"[^>]*>([\s\S]*?)<\/script>/)[1];
  assert.equal(inline.trim(), '');
  assert.match(html, /<script src="\.\/launcher\.js"><\/script>/);
  assert(!/\beval\s*\(|new Function\s*\(/.test(script));
  assert.equal(typeof Component, 'function');
});

test('embedded snapshot preserves forks and plugins and adds only schema-generated packages', () => {
  assert.deepEqual(CATALOG_SNAPSHOT, {
    ...snapshot,
    package_entries: packageFeed.packages,
    package_catalog_digest: packageFeed.catalog_digest,
  });
  const raw = JSON.parse(fs.readFileSync(path.join(root, 'data/github-forks.response.json'), 'utf8'));
  const forks = CATALOG.filter(r => r.type === 'fork');
  const plugins = CATALOG.filter(r => r.type === 'plugin');
  const packages = CATALOG.filter(r => r.type === 'package');
  assert.equal(CATALOG.length, 20);
  assert.equal(forks.length, 10);
  assert.equal(plugins.length, 7);
  assert.equal(packages.length, 3);
  assert.equal(snapshot.package_browser.status, 'metadata_catalog_preview');
  assert.equal(snapshot.package_browser.composition_enabled, true);
  assert.equal(snapshot.package_browser.upload_enabled, false);
  assert.equal(snapshot.package_browser.download_enabled, false);
  assert.equal(snapshot.package_browser.execution_enabled, false);
  assert.deepEqual(forks.map(r => [r.github_id, r.github_stars]), raw.map(r => [r.id, r.stargazers_count]));
  assert.deepEqual(plugins.map(r => r.curation.rank), [1, 2, 3, 4, 5, 6, 7]);
  assert(plugins.every(r => r.package.version && /^(?:sha512|sha256)-/.test(r.package.integrity)));
  assert.equal(new Set([...forks, ...plugins].map(r => r.github_id)).size, 17);
  assert([...forks, ...plugins].every(r => /^[a-f0-9]{40}$/.test(r.head_sha)));
  assert.deepEqual(packages.map(r => r.rank), [1, 2, 3]);
  assert(packages.every(r => r.page.route === '#packages/' + r.slug));
  assert(packages.every(r => r.acquisition.enabled === false));
});
test('launcher remains default and Community has stable plugin, fork, and package routes', () => {
  const c = instance(); assert(c.renderVals().showLaunch); assert(!c.renderVals().showCatalog);
  assert.equal(c.state.cells.length, 0);
  assert.equal(c.renderVals().modeLabel, 'portable preview');
  assert.match(c.renderVals().launchHint, /No sample process is presented as real/);
  c.renderVals().goCatalog(); assert(c.renderVals().showCatalog); assert(!c.renderVals().showLaunch);
  assert.equal(windowStub.location.hash, 'packages');
  c.renderVals().results[0].select();
  assert.equal(windowStub.location.hash, 'packages/agent-teams-builder');
  c.renderVals().repoTypes.find(f => f.id === 'fork').select();
  assert.equal(windowStub.location.hash, 'forks');
  c.renderVals().repoTypes.find(f => f.id === 'package').select();
  assert.equal(windowStub.location.hash, 'packages');
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
  assert.equal(c.renderVals().modeLabel, 'sandbox fleet');
  assert.equal(c.renderVals().suggested, 3210);
});
test('portable preview has two immutable official pins and no fabricated cells', () => {
  const c = instance(); const values = c.renderVals();
  assert.equal(values.versions.length, 2);
  assert.deepEqual(values.versions.map(v => v.version), ['0.1.2-alpha.3', '0.1.2-alpha.2']);
  assert.deepEqual(values.versions.map(v => v.commit), ['dd6322d', '0a53fb5']);
  assert(values.versions.every(v => v.disabled));
  assert.equal(values.cells.length, 0);
  assert.match(html, /Fail-closed cell fleet/);
  assert.match(html, /sandbox failure never falls back to a host process/);
  assert.match(script, /sandbox test .*network none .*no launcher secrets/);
});
test('launcher keeps discovery controls out of the primary UI', () => {
  assert(!/>\s*Rescan\s*</i.test(html));
  assert(!/>\s*Scan roots\s*</i.test(html));
  assert(!/>\s*Add folder(?:…|\.\.\.)?\s*</i.test(html));
  assert(!/window\.prompt\s*\(/.test(script));
  assert(!/\b(?:scanLabel|addFolder|rescanLauncher)\b/.test(script));
});
test('one-click version launch requests automatic isolation', async () => {
  const c = instance(); let request;
  c.applyStatus({
    trees: [
      { id: 'a3', name: 'official', short: 'official', kind: 'source', version: '0.1.2-alpha.3', path: '~/a3', exe: '~/a3/dsh', node: 'node', git: { sha: 'dd6322dabc', branch: 'tag', dirty: false }, trust: 'readonly', launchability: 'ready' },
      { id: 'a2', name: 'official', short: 'official', kind: 'source', version: '0.1.2-alpha.2', path: '~/a2', exe: '~/a2/dsh', node: 'node', git: { sha: '0a53fb5abc', branch: 'tag', dirty: false }, trust: 'readonly', launchability: 'ready' }
    ], cells: [], suggested_port: 3100, coverage_gaps: [], credentials: [],
    sandbox: {
      mode: 'apptainer-cell-v1', ready: true, reason: 'capability probe passed',
      resource_limits: { cpus: '4', memory: '8G' }
    }
  });
  c.api = async (url, options) => {
    if (url === '/api/v1/cells') { request = JSON.parse(options.body); return { id: 'cell-one', name: 'cell', port: 3100 }; }
    return { trees: c.state.trees, cells: [], suggested_port: 3101, coverage_gaps: [], credentials: [] };
  };
  c.refreshStatus = async () => {};
  const version = c.renderVals().versions[0];
  assert.equal(version.disabled, false);
  await version.launch();
  assert.equal(request.port, 'auto');
  assert.equal(request.home_mode, 'fresh');
  assert.equal(request.workspace, 'managed');
  assert.equal(request.network, 'host');
  assert.equal(request.resources.gpu, 'none');
  assert.equal(request.tree_id, 'a3');
});
test('detected community trees use the probe endpoint and never become complete cells', async () => {
  const c = instance(); let request;
  const foreign = {
    id: 'fork-1', name: 'community fork', short: 'fork', kind: 'source', version: '1.0.0',
    path: '~/fork', exe: '~/fork/dsh.js', node: 'sandbox',
    git: { sha: 'abc123', branch: 'main', dirty: false }, trust: 'foreign', launchability: 'sandbox-testable'
  };
  c.applyStatus({
    trees: [foreign], cells: [], suggested_port: 3100, coverage_gaps: [], credentials: [],
    sandbox: {
      mode: 'apptainer-cell-v1', ready: true, reason: 'capability probe passed',
      hostile_code_isolation: false, resource_limits: { cpus: '4', memory: '8G' }
    }
  });
  c.api = async (url, options) => {
    request = { url, method: options.method, body: options.body };
    return { status: 'passed' };
  };
  c.refreshStatus = async () => {};
  const values = c.renderVals();
  assert.equal(values.communityTrees.length, 1);
  assert.equal(values.communityTrees[0].disabled, false);
  assert.equal(values.launchDisabled, true);
  assert.equal(values.primaryLabel, 'Sandbox test only');
  await values.communityTrees[0].run();
  assert.deepEqual(request, {
    url: '/api/v1/trees/fork-1/sandbox-test', method: 'POST', body: '{}'
  });
  assert.match(c.lastMessage, /sandbox test passed/);
});
test('fork star sorting retains captured GitHub order for ties', () => {
  const c = instance();
  c.renderVals().repoTypes.find(f => f.id === 'fork').select();
  c.renderVals().setCatalogSort({ target: { value: 'stars' } });
  const rows = c.renderVals().results;
  const forks = CATALOG.filter(r => r.type === 'fork');
  const stars = rows.map(r => r.github_stars);
  assert.deepEqual(stars, [...stars].sort((a,b) => b-a));
  for (const count of new Set(stars)) {
    assert.deepEqual(rows.filter(r => r.github_stars === count).map(r => r.id),
      forks.filter(r => r.github_stars === count).map(r => r.id));
  }
});
test('search handles case, whitespace, and multiple terms', () => {
  const c = instance(); const target = CATALOG.filter(r => r.type === 'plugin')[1];
  c.renderVals().repoTypes.find(f => f.id === 'plugin').select();
  c.renderVals().setQuery({ target: { value: '  ' + target.owner.toUpperCase() + '   ' + target.name + '  ' } });
  assert.deepEqual(c.renderVals().results.map(r => r.id), [target.id]);
});
test('filtered-out selection never leaves stale detail content', () => {
  const c = instance(); const plugins = CATALOG.filter(r => r.type === 'plugin');
  c.renderVals().repoTypes.find(f => f.id === 'plugin').select();
  c.renderVals().results[3].select();
  c.renderVals().setQuery({ target: { value: plugins[4].slug } });
  assert.equal(c.renderVals().detail.id, plugins[4].id);
  c.renderVals().setQuery({ target: { value: 'no-such-repository-000' } });
  assert(c.renderVals().noResults); assert(!c.renderVals().hasDetail);
  assert.deepEqual(c.renderVals().detailRows, []);
});
test('package-first browser exposes generated packages, plugins, and captured forks', () => {
  const c = instance();
  c.renderVals().goCatalog();
  assert.equal(c.renderVals().results.length, 3);
  assert.deepEqual(c.renderVals().repoTypes.map(f => [f.id, f.count]), [['package', 3], ['plugin', 7], ['fork', 10]]);
  const packageDetail = c.renderVals();
  assert.equal(packageDetail.detail.schema, 'dsh-forge.catalog-package/v1');
  assert.equal(packageDetail.acquireLabel, 'Acquire verified bytes');
  assert.equal(packageDetail.isPackageDetail, true);
  assert(packageDetail.packageComponents.length >= 1);
  c.renderVals().repoTypes.find(f => f.id === 'plugin').select();
  assert.equal(c.renderVals().results.length, 7);
  assert.equal(windowStub.location.hash, 'plugins');
  c.renderVals().repoTypes.find(f => f.id === 'fork').select();
  assert.equal(c.renderVals().results.length, 10);
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
  const c = instance(); const plugin = snapshot.supplemental_entries[0];
  c.renderVals().repoTypes.find(f => f.id === 'plugin').select();
  await c.renderVals().copyRef();
  assert.equal(clipboard.at(-1), plugin.repository_url + '/tree/' + plugin.head_sha);
  assert.equal(c.lastMessage, 'Copied repository reference');
});
test('catalog interactions cannot add, stop, or modify local cells', () => {
  const c = instance(); const before = JSON.stringify(c.state.cells);
  c.renderVals().goCatalog(); c.renderVals().repoTypes.find(f => f.id === 'plugin').select(); c.renderVals().results[5].select();
  c.renderVals().setQuery({ target: { value: 'desktop' } });
  c.renderVals().goLaunch(); assert.equal(JSON.stringify(c.state.cells), before);
});
test('public code actions are disabled and the snapshot has no fabricated analysis', () => {
  const section = html.slice(html.indexOf('<main class="public-browser"'), html.indexOf('<sc-if value="{{ previewOpen }}"'));
  assert.equal((section.match(/<button disabled title=/g) || []).length, 3);
  assert(!/onClick="{{.*(?:install|clone|run|sandbox)/i.test(section));
  assert(!/signed snapshot v42|nmarquez\/|@kv\/|orbit-labs\//.test(script));
  assert(CATALOG.filter(r => r.type === 'fork').every(r => r.analysis_status === 'not_analyzed'));
  assert(CATALOG.filter(r => r.type === 'plugin').every(r => r.analysis_status === 'manifest_reviewed'));
  assert(CATALOG.every(r => r.verification.metadata_only && !r.verification.executed && !r.verification.security_verified));
  assert(CATALOG.filter(r => r.type === 'package').every(r => !r.verification.installed && !r.verification.sandbox_verified && !r.acquisition.enabled));
});

test('dedicated package route selects the requested metadata page and remains non-executable', async () => {
  const c = instance({}, '#packages/code-review-lab');
  const values = c.renderVals();
  assert(values.showCatalog);
  assert.equal(c.state.catalogType, 'package');
  assert.equal(values.detail.slug, 'code-review-lab');
  assert.equal(values.detail.components.length, 2);
  await values.sharePackagePage();
  assert.equal(clipboard.at(-1), 'http://127.0.0.1:3090/#packages/code-review-lab');
  assert.equal(c.lastMessage, 'Copied package page');
});
