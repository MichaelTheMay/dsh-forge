// Behavior tests for the exported logic. No browser, network, or local runner.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { createHash } = require('node:crypto');
const { gzipSync } = require('node:zlib');
const { pathToFileURL } = require('node:url');
const root = path.join(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'web/index.html'), 'utf8');
const script = fs.readFileSync(path.join(root, 'web/launcher.js'), 'utf8');
const snapshot = JSON.parse(fs.readFileSync(path.join(root, 'data/public-repos.seed.json'), 'utf8'));
const packageFeed = JSON.parse(fs.readFileSync(path.join(root, 'data/package-catalog.seed.json'), 'utf8'));
const vercel = JSON.parse(fs.readFileSync(path.join(root, 'web/vercel.json'), 'utf8'));
const rootVercel = JSON.parse(fs.readFileSync(path.join(root, 'vercel.json'), 'utf8'));
const vercelIgnore = fs.readFileSync(path.join(root, '.vercelignore'), 'utf8').split(/\r?\n/);
class Logic {
  constructor(props) { this.props = props; }
  setState(change, callback) {
    Object.assign(this.state, typeof change === 'function' ? change(this.state) : change);
    if (callback) callback();
  }
}
const stored = new Map();
const listeners = new Map();
const windowStub = {
  location: { hash: '', href: 'http://127.0.0.1:3090/', protocol: 'http:', hostname: '127.0.0.1' },
  addEventListener: (name, listener) => listeners.set(name, listener),
  removeEventListener: name => listeners.delete(name),
  localStorage: {
    getItem: key => stored.get(key) || null,
    setItem: (key, value) => stored.set(key, value),
    removeItem: key => stored.delete(key)
  },
  __dcPrecompiledLogicFactories: {}
};
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

test('assistant iframe is inert in source and accepts only an explicit loopback URL', () => {
  assert(!/iframe[^>]+src="\{\{\s*assistantUrl/.test(html));
  assert.match(html, /iframe data-assistant-url="\{\{ assistantUrl \}\}"/);
  const c = instance();
  const frame = {
    dataset: { assistantUrl: 'http://127.0.0.1:3100/session' },
    src: '',
    removeAttribute(name) { if (name === 'src') this.src = ''; }
  };
  global.document = { querySelector: () => frame };
  try {
    c.syncAssistantFrame();
    assert.equal(frame.src, 'http://127.0.0.1:3100/session');
    frame.dataset.assistantUrl = 'https://example.com/unsafe';
    c.syncAssistantFrame();
    assert.equal(frame.src, '');
  } finally {
    delete global.document;
  }
});

test('public preview includes a real favicon asset', () => {
  assert.match(html, /<link rel="icon" href="\.\/favicon\.svg" type="image\/svg\+xml">/);
  assert.match(fs.readFileSync(path.join(root, 'web/favicon.svg'), 'utf8'), /^<svg/);
});

test('mobile fork layout removes every unused desktop grid column', () => {
  assert.match(html, /@media \(max-width: 800px\)[\s\S]*\.app-header > \.spacer \{ display: none; \}/);
  assert.match(html, /@media \(max-width: 800px\)[\s\S]*\.col-forks, \.col-upstream, \.col-push, \.col-license, \.frow \.gem \{ display: none; \}/);
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
test('launcher remains default and Community opens individual plugins and forks', () => {
  const c = instance(); assert(c.renderVals().showLaunch); assert(!c.renderVals().showCatalog);
  assert.equal(c.state.cells.length, 0);
  assert.equal(c.renderVals().sidecarLabel, 'Offline preview');
  assert.match(c.renderVals().emptyVersionsText, /No sample process is presented as real/);
  c.renderVals().goPlugins(); assert(c.renderVals().showCatalog); assert(!c.renderVals().showLaunch);
  assert.equal(windowStub.location.hash, 'plugins');
  assert.equal(c.renderVals().pluginsTabCurrent, 'page');
  const plugin = c.renderVals().results[0];
  plugin.select();
  assert.equal(windowStub.location.hash, 'plugins/' + encodeURIComponent(plugin.id));
  assert(c.renderVals().showArtifactPage);
  c.renderVals().backToCatalog();
  c.renderVals().goForks();
  assert.equal(windowStub.location.hash, 'forks');
  assert.equal(c.renderVals().forksTabCurrent, 'page');
  assert.equal(c.renderVals().pluginsTabCurrent, 'false');
  c.renderVals().goLaunch(); assert(c.renderVals().showLaunch);
});

test('public root presents the product site and routes into the working application', async () => {
  const previous = { ...windowStub.location };
  Object.assign(windowStub.location, {
    hash: '', href: 'https://dsh-forge.vercel.app/', protocol: 'https:', hostname: 'dsh-forge.vercel.app'
  });
  try {
    const c = instance();
    const landing = c.renderVals();
    assert.equal(landing.showLanding, true);
    assert.equal(landing.showAppShell, false);
    assert.match(html, /Every plugin\. <span>Every fork\. One launcher\.<\/span>/);
    assert.doesNotMatch(html, /Apple silicon and Intel|macOS releases/);
    assert.match(html, /Windows 10 and 11/);
    assert.doesNotMatch(html, /curl\s+-fsSL\s+dshforge\.dev/);
    await landing.landingCopyInstall();
    assert.equal(clipboard.at(-1), 'git clone https://github.com/MichaelTheMay/dsh-forge && cd dsh-forge && python3 scripts/serve.py --desktop --sync-catalog');
    // The hero leads to the Discover page, not to a launcher preview.
    assert(!('landingOpenLauncher' in landing));
    landing.landingCommunity();
    assert.equal(c.renderVals().showCatalog, true);
    assert.equal(c.renderVals().showDiscover, true);
    assert.equal(windowStub.location.hash, 'discover');
  } finally {
    Object.assign(windowStub.location, previous);
  }
});

test('browser back navigation refreshes the newly selected catalog type', async () => {
  const c = instance();
  const refreshed = [];
  c.refreshStatus = async () => {};
  c.scheduleCatalogRefresh = () => refreshed.push(c.state.catalogType);
  c.componentDidMount();
  try {
    windowStub.location.hash = '#forks';
    listeners.get('hashchange')();
    windowStub.location.hash = '#plugins';
    listeners.get('hashchange')();
    assert.deepEqual(refreshed, ['fork', 'plugin']);
    assert.equal(c.state.catalogType, 'plugin');
  } finally {
    c.componentWillUnmount();
    windowStub.location.hash = '';
  }
});
test('preview contains no personal-name or private-home leakage', () => {
  assert(!/michael(?:the)?may|\/home\/[^/]+\//i.test(html));
  assert(!/pid:\s*4\d{4}|loader settled|process alive · pid/i.test(html));
});
test('live status replaces preview inventory instead of merging it', () => {
  const c = instance();
  c.applyStatus({
    trees: [{ id: 'real', name: 'detected', short: 'detected', kind: 'source', version: '1', path: '~/dsh', exe: '~/dsh/dsh', node: 'bundled', git: null, trust: 'personal', launchability: 'ready' }],
    saved_versions: [{ id: 'version_123456789abc', path: '~/dsh', state: 'ready', tree_ids: ['real'], primary_tree: { id: 'real', name: 'detected', kind: 'source', version: '1', path: '~/dsh', git: null, trust: 'personal', launchability: 'ready' } }],
    cells: [], suggested_port: 3210, coverage_gaps: [], credentials: []
  });
  assert.equal(c.state.trees.length, 1);
  assert.equal(c.state.trees[0].id, 'real');
  assert.equal(c.state.savedVersions.length, 1);
  assert.match(c.renderVals().sidecarLabel, /^Connected · /);
  assert.deepEqual(c.renderVals().versions.map(item => item.version), ['1']);
});
test('portable preview shows no versions or cells that are not locally detected', () => {
  const c = instance(); const values = c.renderVals();
  assert.equal(values.versions.length, 0);
  assert(values.noVersions);
  assert.equal(values.versionGroups.length, 0);
  assert.equal(values.hasLocalRows, false);
  assert.equal(values.sandboxTitle, 'Isolation setup required');
  assert(!/Fail-closed cell fleet/.test(html));
  assert(!/quota unenforced/.test(html));
});
test('launcher auto-detects local versions and opens a native directory picker', async () => {
  assert.match(html, />Add folder</);
  assert.match(html, /onClick="\{\{ pickVersion \}\}"/);
  assert(!/placeholder="\/path\/to\/deepseek-harness"/.test(html));
  assert(!/Rescan saved versions/.test(html));
  assert(!/>\s*Scan roots\s*</i.test(html));
  assert(!/window\.prompt\s*\(/.test(script));
  const c = instance(); let request;
  c.api = async (url, options) => {
    request = { url, method: options.method, body: JSON.parse(options.body) };
    return {
      trees: [], cells: [], saved_versions: [{
        id: 'version_123456789abc', path: '~/dsh', state: 'no-harness-found', tree_ids: [], primary_tree: null
      }], suggested_port: 3100, coverage_gaps: ['~/dsh · no strong DSH signature'], credentials: []
    };
  };
  c.setState({ sidecarConnected: true });
  await c.pickLocalVersion();
  assert.deepEqual(request, {
    url: '/api/v1/versions/pick', method: 'POST', body: {}
  });
  assert.equal(c.state.savedVersions.length, 1);
  // A picked folder without a Harness is never launchable, but it can still be forgotten.
  const values = c.renderVals();
  assert.equal(values.versions.length, 0);
  assert.deepEqual(values.unavailableVersions.map(item => [item.path, item.reason]),
    [['~/dsh', 'No Harness found in this folder']]);
});
test('saved-version rescan and forget use explicit non-destructive endpoints', async () => {
  const c = instance(); const requests = [];
  c.setState({
    sidecarConnected: true,
    savedVersions: [{ id: 'version_123456789abc', path: '~/dsh', state: 'missing', tree_ids: [], primary_tree: null }]
  });
  c.api = async (url, options) => {
    requests.push({ url, body: JSON.parse(options.body) });
    return { trees: [], cells: [], saved_versions: [], suggested_port: 3100, coverage_gaps: [], credentials: [] };
  };
  await c.rescanVersions();
  await c.forgetLocalVersion({ id: 'version_123456789abc' });
  assert.deepEqual(requests, [
    { url: '/api/v1/scan', body: {} },
    { url: '/api/v1/versions/remove', body: { id: 'version_123456789abc' } }
  ]);
  assert.match(c.lastMessage, /source files were not changed/);
});
test('saved launch preferences use the limited settings endpoint', async () => {
  const c = instance(); let request;
  const saved = {
    id: 'version_123456789abc', path: '~/dsh', source: 'manual', state: 'ready', tree_ids: ['real'],
    launch: { surface: 'web', profile: 'tui-min', port: 'auto', open_browser: false, home_mode: 'fresh', workspace: 'managed', network: 'host', resources: { gpu: 'none' } },
    primary_tree: { id: 'real', name: 'detected', kind: 'source', version: '1', path: '~/dsh', git: null, trust: 'personal', launchability: 'ready' }
  };
  c.applyStatus({
    trees: [saved.primary_tree], cells: [], saved_versions: [saved], suggested_port: 3100,
    coverage_gaps: [], credentials: [], versions_directory: { path: '~/dsh-versions', available: true, auto_scan: true },
    sandbox: { ready: true, reason: 'ready', resource_limits: {} }
  });
  c.api = async (url, options) => {
    request = { url, body: JSON.parse(options.body) };
    return { trees: [saved.primary_tree], cells: [], saved_versions: [saved], coverage_gaps: [], credentials: [] };
  };
  await c.renderVals().versions[0].setGpuMode({ target: { value: 'allocated' } });
  assert.deepEqual(request, {
    url: '/api/v1/versions/settings',
    body: { id: saved.id, launch: { open_browser: false, gpu: 'allocated' } }
  });
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
test('detected community trees never become launchable local versions', () => {
  const c = instance();
  const foreign = {
    id: 'fork-1', name: 'community fork', short: 'fork', kind: 'source', version: '1.0.0',
    path: '~/fork', git: { sha: 'abc123', branch: 'main', dirty: false }, trust: 'foreign', launchability: 'ready'
  };
  c.applyStatus({ trees: [foreign], cells: [], sandbox: { ready: true, reason: 'capability probe passed' } });
  const values = c.renderVals();
  assert.equal(values.versions.length, 0);
  assert.equal(values.noVersions, true);
});
test('fork star sorting retains captured GitHub order for ties', () => {
  const c = instance();
  c.renderVals().goForks();
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
  c.renderVals().goPlugins();
  c.renderVals().setQuery({ target: { value: '  ' + target.owner.toUpperCase() + '   ' + target.name + '  ' } });
  assert.deepEqual(c.renderVals().results.map(r => r.id), [target.id]);
});
test('filtered-out selection never leaves stale detail content', () => {
  const c = instance(); const plugins = CATALOG.filter(r => r.type === 'plugin');
  c.renderVals().goPlugins();
  c.renderVals().results[3].select();
  assert.equal(c.renderVals().detail.id, plugins[3].id);
  // Searching returns to the list; the old page's record is not carried along.
  c.renderVals().setQuery({ target: { value: plugins[4].slug } });
  assert.equal(c.renderVals().showArtifactPage, false);
  assert.equal(c.renderVals().hasDetail, false);
  assert.deepEqual(c.renderVals().results.map(r => r.id), [plugins[4].id]);
  c.renderVals().setQuery({ target: { value: 'no-such-repository-000' } });
  assert(c.renderVals().noResults); assert(!c.renderVals().hasDetail);
  assert.deepEqual(c.renderVals().detailRows, []);
});
test('community browser exposes plugins and forks without provisional package promotion', () => {
  const c = instance();
  c.renderVals().goPlugins();
  assert.equal(c.renderVals().results.length, 7);
  assert.equal(c.renderVals().resultCount, '7 plugins');
  assert.equal(windowStub.location.hash, 'plugins');
  c.renderVals().goForks();
  assert.equal(c.renderVals().results.length, 10);
  assert.equal(c.renderVals().resultCount, '10 forks');
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
  c.renderVals().goPlugins();
  c.renderVals().results.find(r => r.id === plugin.artifact_id).select();
  await c.renderVals().copyRef();
  assert.equal(clipboard.at(-1), plugin.repository_url + '/tree/' + plugin.head_sha);
  assert.equal(c.lastMessage, 'Copied repository reference');
});
test('catalog interactions cannot add, stop, or modify local cells', () => {
  const c = instance(); const before = JSON.stringify(c.state.cells);
  c.renderVals().goPlugins(); c.renderVals().results[5].select();
  c.renderVals().setQuery({ target: { value: 'desktop' } });
  c.renderVals().goLaunch(); assert.equal(JSON.stringify(c.state.cells), before);
});
test('repository actions stay disabled while signed package install is locally gated', () => {
  const section = html.slice(html.indexOf('<main class="public-browser"'), html.indexOf('<sc-if value="{{ previewOpen }}"'));
  // Composition and upload remain the only statically disabled affordance. A bare
  // `disabled` reaches React as "" (not disabled), so static buttons spell it out.
  const disabled = section.match(/<button disabled="disabled"(?: title="([^"]*)")?/g) || [];
  assert(!/<button disabled[\s>]/.test(section), 'a bare disabled attribute does not disable the button');
  // No dead buttons: an action that isn't available is not shown at all.
  assert.equal(disabled.length, 0);
  assert.match(section, /onClick="{{ installPackage }}" disabled="{{ installDisabled }}"/);
  assert(!/signed snapshot v42|nmarquez\/|@kv\/|orbit-labs\//.test(script));
  assert(CATALOG.filter(r => r.type === 'fork').every(r => r.analysis_status === 'not_analyzed'));
  assert(CATALOG.filter(r => r.type === 'plugin').every(r => r.analysis_status === 'manifest_reviewed'));
  assert(CATALOG.every(r => r.verification.metadata_only && !r.verification.executed && !r.verification.security_verified));
  assert(CATALOG.filter(r => r.type === 'package').every(r => !r.verification.installed && !r.verification.sandbox_verified && !r.acquisition.enabled));
});

test('installed-profile rail one-clicks web and headless and copies the rest', async () => {
  const c = instance();
  const status = {
    trees: [], cells: [], saved_versions: [], package_installations: [],
    trusted_package_recipes: [], suggested_port: 3100, coverage_gaps: [], credentials: [],
    sandbox: { ready: true },
    profiles: [
      { id: 'profile_' + 'a'.repeat(16), name: 'web', home: '~/.dsh', surface: 'web', bundles: ['@deepseek-ai/dsh-web-app'], dependencies: ['dsh-vet'], launchability: 'one-click', command: 'run-web' },
      { id: 'profile_' + 'b'.repeat(16), name: 'coding', home: '~/.dsh', surface: 'terminal', bundles: ['@deepseek-ai/dsh-tui-app'], dependencies: [], launchability: 'terminal-only', command: 'run-coding' }
    ]
  };
  c.applyStatus(status);
  let values = c.renderVals();
  assert.equal(values.profileCountLabel, '2 profiles found');
  assert.equal(values.localProfiles[0].bundleLabel, '1 bundle');
  assert.equal(values.localProfiles[0].dependencyLabel, '1 plugin');
  // Without a launch-ready tree, one-click is refused but the CLI path stays open.
  assert.equal(values.localProfiles[0].disabled, true);
  assert.equal(values.localProfiles[1].buttonLabel, 'Copy terminal command');
  assert.equal(values.localProfiles[1].disabled, false);
  await values.localProfiles[1].run();
  assert.equal(clipboard.at(-1), 'run-coding');

  const tree = { id: 'tree_123456789abc', trust: 'trusted', launchability: 'ready', version: '0.1.2-rc.1', short: 'dsh' };
  c.applyStatus({ ...status, trees: [tree] });
  values = c.renderVals();
  assert.equal(values.localProfiles[0].disabled, false);
  let request;
  c.api = async (url, options) => {
    request = { url, body: JSON.parse(options.body) };
    return {
      profile: status.profiles[0], tree: { ...tree, path: '~/dsh' },
      argv: ['/usr/bin/dsh', '--profile', 'web', '--host', '127.0.0.1', '--port', '3100', '--no-open'],
      command: "DSH_HOME=~/.dsh /usr/bin/dsh --profile web", cwd: '~/dsh-forge', home: '~/.dsh',
      environment_keys: ['PATH'], credential_keys: [],
      notes: ['This is an existing local profile, so it runs directly on the host rather than inside Apptainer.']
    };
  };
  await values.localProfiles[0].run();
  // One-click always previews first; it never posts straight to the run endpoint.
  assert.equal(request.url, '/api/v1/profiles/preview');
  assert.deepEqual(request.body, {
    profile_id: status.profiles[0].id, tree_id: tree.id, task: '', port: 'auto', open_browser: true
  });
  assert.equal(c.renderVals().previewTitle, 'Confirm local profile — direct host process');
  assert.equal(c.renderVals().previewConfirmLabel, 'Run local profile');
});

test('plugin detail never exposes a host install command', () => {
  const c = instance();
  c.applyStatus({
    trees: [], cells: [], saved_versions: [], package_installations: [],
    trusted_package_recipes: [], suggested_port: 3100, coverage_gaps: [], credentials: [],
    sandbox: { ready: true },
    profiles: [
      { id: 'profile_' + 'a'.repeat(16), name: 'web', home: '~/.dsh', surface: 'web', bundles: [], dependencies: [], launchability: 'one-click' },
      { id: 'profile_' + 'b'.repeat(16), name: 'coding', home: '~/.dsh', surface: 'terminal', bundles: [], dependencies: [], launchability: 'terminal-only' }
    ]
  });
  const plugin = snapshot.supplemental_entries.find(entry => entry.package.registry === 'npm');
  c.selectCatalogArtifact({ id: plugin.artifact_id, type: 'plugin' });
  const values = c.renderVals();
  assert.equal(values.isPluginDetail, true);
  assert(!Object.keys(values).some(key => /InstallCommand|Download(?:Url|Command)/.test(key)));
  assert.equal(values.installAndRunDisabled, true);
  assert.equal(values.installAndRunLabel, 'Sandbox recipe required');
  assert(!/Copy exact-version install command/.test(html));
});

test('eligible plugin requires a large risk confirmation before the stable-ID install-run request', async () => {
  const c = instance();
  const saved = {
    id: 'version_123456789abc', path: '~/dsh', state: 'ready', tree_ids: ['tree_123456789abc'],
    primary_tree: { id: 'tree_123456789abc', version: '0.1.2-rc.1' }
  };
  c.applyStatus({
    trees: [], cells: [], saved_versions: [saved], configurations: [], package_installations: [],
    trusted_package_recipes: [{ slug: 'single-vet', configured: true }],
    suggested_port: 3100, coverage_gaps: [], credentials: [], sandbox: { ready: true }
  });
  const plugin = CATALOG.find(item => item.type === 'plugin');
  c.setState({
    detailOpen: true,
    artifactId: plugin.id,
    detailArtifact: {
      ...plugin,
      execution: {
        eligible: true, reason: 'Exact signed recipe is ready for sandbox installation',
        recipe_slug: 'single-vet', recipe_name: 'Single vet', reviewer: 'Release curator'
      }
    }
  });
  let values = c.renderVals();
  assert.equal(values.installAndRunDisabled, false);
  values.installAndRun();
  values = c.renderVals();
  assert.equal(values.artifactRunConfirmationOpen, true);
  assert.equal(values.artifactRunConfirmDisabled, true);
  values.toggleArtifactRisk({ target: { checked: true } });
  let request;
  c.api = async (url, options) => {
    request = { url, body: JSON.parse(options.body) };
    return { cell: { id: 'cell_plugin' } };
  };
  c.refreshStatus = async () => {};
  await c.renderVals().startArtifactRun();
  assert.deepEqual(request, {
    url: '/api/v1/catalog/install-run',
    body: { artifact_id: plugin.id, version_id: saved.id, acknowledge_risk: true }
  });
  // The new session opens on the Local tab with its startup logs showing.
  assert.equal(c.state.view, 'launch');
  assert.equal(c.state.logCell, 'cell_plugin');
  assert.equal(c.state.artifactRunConfirmation, null);
  assert.match(html, /Sandboxing reduces risk but does not eliminate it/);
  assert.match(html, /Apptainer shares the host kernel/);
});

test('raw plugins and forks cannot bypass sandbox acquisition', () => {
  const c = instance();
  const mcpb = snapshot.supplemental_entries.find(entry => entry.package.registry !== 'npm');
  const hostPath = values => Object.keys(values).some(key => /InstallCommand|Download(?:Url|Command)/.test(key));
  c.selectCatalogArtifact({ id: mcpb.artifact_id, type: 'plugin' });
  let values = c.renderVals();
  assert.equal(values.installAndRunDisabled, true);
  assert.equal(hostPath(values), false);

  const fork = snapshot.entries[0];
  c.selectCatalogArtifact({ id: fork.artifact_id, type: 'fork' });
  values = c.renderVals();
  assert.equal(values.isForkDetail, true);
  assert.equal(values.isPluginDetail, false);
  assert.equal(hostPath(values), false);
  assert(!/Download \.tar\.gz|Copy command/.test(html));
});

test('community browser does not publish provisional curated packages or featured strips', () => {
  // The header offers exactly four sections; packages have no tab of their own.
  const tabs = [...html.matchAll(/class="\{\{ (\w+)TabClass \}\}"/g)].map(match => match[1]);
  assert.deepEqual(tabs, ['discover', 'plugins', 'forks', 'launch', 'assistant']);
  assert(!/Forge picks/.test(html));
  assert(!/Administrator curated hidden gems/.test(html));
});

test('plugin and fork cards open stable dedicated pages and favorites persist locally', () => {
  stored.clear();
  const c = instance();
  c.renderVals().goPlugins();
  const plugin = c.renderVals().results[0];
  plugin.select();
  let values = c.renderVals();
  assert(values.showArtifactPage);
  assert.equal(values.detail.id, plugin.id);
  assert.equal(values.favoriteClass, 'btn fav');
  values.toggleFavorite();
  assert.equal(c.renderVals().favoriteLabel, 'Saved');
  // Saving turns the button gold and plays the pop once.
  assert.equal(c.renderVals().favoriteClass, 'btn fav fav-on fav-pop');

  const reopened = instance({}, '#plugins/' + encodeURIComponent(plugin.id));
  values = reopened.renderVals();
  assert(values.showArtifactPage);
  assert.equal(values.detail.id, plugin.id);
  assert.equal(values.favoriteLabel, 'Saved');
  // A saved page reopens gold without replaying the animation.
  assert.equal(values.favoriteClass, 'btn fav fav-on');
  // Removing a favorite fades back to neutral with no pop.
  values.toggleFavorite();
  assert.equal(reopened.renderVals().favoriteClass, 'btn fav');
  clearTimeout(c.favoritePopTimer);
  stored.clear();
});

test('home hides saved paths that are missing or not launch ready', () => {
  const c = instance();
  const ready = { id: 'ready', trust: 'personal', launchability: 'ready', version: '1.0.0', name: 'DSH' };
  c.applyStatus({
    trees: [ready], cells: [], profiles: [], sandbox: { ready: true }, credentials: [], coverage_gaps: [],
    saved_versions: [
      { id: 'version_ready000000', state: 'ready', tree_ids: ['ready'], primary_tree: ready },
      { id: 'version_missing0000', state: 'missing', tree_ids: [], primary_tree: null },
      { id: 'version_setup000000', state: 'no-harness-found', tree_ids: [], primary_tree: null }
    ]
  });
  assert.deepEqual(c.renderVals().versions.map(item => item.version), ['1.0.0']);
  assert(!/Certified packages|Detected community trees/.test(html));
});

test('community feed loads more as its scroll container nears the end', () => {
  assert.match(html, /onScroll="\{\{ loadMoreOnScroll \}\}"/);
  assert(!/repo-load-more" onClick/.test(html));
  const c = instance();
  let calls = 0;
  c.refreshCatalog = async (options = {}) => { calls += options.append ? 1 : 0; };
  connectedStore(c);
  c.setState({ storeCursor: '1.50', storeLoading: false });
  c.renderVals().loadMoreOnScroll({ currentTarget: { scrollHeight: 1000, scrollTop: 600, clientHeight: 300 } });
  assert.equal(calls, 1);
});

function connectedStore(c, store = { available: true, artifact_count: 24000 }) {
  c.applyStatus({
    trees: [], cells: [], saved_versions: [], package_installations: [],
    trusted_package_recipes: [], configurations: [], profiles: [],
    suggested_port: 3100, coverage_gaps: [], credentials: [], sandbox: { ready: true },
    catalog_store: store
  });
}

test('hosted preview pages use the live read-only catalog without enabling local execution', async () => {
  const c = instance();
  const previousLocation = { ...windowStub.location };
  const plugin = snapshot.supplemental_entries[0];
  const requests = [];
  c.api = async url => {
    requests.push(url);
    return {
      artifacts: [plugin], total: 10430, next_cursor: '50', research: {},
      catalog_store: {
        available: true, public: true, artifact_count: 37083,
        counts: { plugin: 10430, fork: 26653, package: 0 }, coverage: []
      }
    };
  };
  Object.assign(windowStub.location, {
    protocol: 'https:', hostname: 'dsh-forge.vercel.app', href: 'https://dsh-forge.vercel.app/#plugins'
  });
  try {
    await c.loadPublicCatalog('plugin');
  } finally {
    Object.assign(windowStub.location, previousLocation);
  }
  const values = c.renderVals();
  assert.equal(c.usingCatalogStore(), true);
  assert.equal(values.catalogSourceLabel, 'Updated daily from GitHub');
  assert.match(values.resultCount, /1 of 10,430 plugins/);
  assert.equal(values.installAndRunDisabled, true);
  assert(requests[0].startsWith('/api/catalog?'));
});

test('public catalog endpoint verifies gzip assets and searches deterministically', async () => {
  const endpoint = await import(pathToFileURL(path.join(root, 'api/catalog.mjs')).href);
  const payload = Buffer.from(JSON.stringify({ ok: true }));
  const compressed = gzipSync(payload);
  const sha = value => createHash('sha256').update(value).digest('hex');
  const metadata = {
    compression: 'gzip', media_type: 'application/json',
    compressed_bytes: compressed.length, compressed_sha256: sha(compressed),
    uncompressed_bytes: payload.length, uncompressed_sha256: sha(payload)
  };
  assert.deepEqual(endpoint.parseVerifiedGzip(compressed, metadata, 1024, 1024), { ok: true });
  assert.throws(
    () => endpoint.parseVerifiedGzip(compressed, { ...metadata, compressed_sha256: '0'.repeat(64) }, 1024, 1024),
    /digest does not match/
  );

  const artifacts = [
    { artifact_id: 'github:1', artifact_type: 'plugin', full_name: 'acme/memory-kit', name: 'memory-kit', description: 'durable memory', github_stars: 2, pushed_at: '2026-01-01', license: { spdx: 'MIT' } },
    { artifact_id: 'github:2', artifact_type: 'plugin', full_name: 'small/agent-tools', name: 'agent-tools', description: 'agent memory', github_stars: 0, pushed_at: '2026-02-01', license: { spdx: null } },
    { artifact_id: 'github:3', artifact_type: 'fork', full_name: 'fork/dsh', name: 'dsh', description: 'fork', github_stars: 9, pushed_at: '2026-03-01', license: { spdx: 'MIT' } }
  ];
  const catalog = {
    artifacts,
    hiddenGems: new Map([['github:2', { rank: 1 }], ['github:1', { rank: 2 }]])
  };
  const ranked = endpoint.queryCatalog(catalog, new URL('https://forge.test/api/catalog?type=plugin&q=memory&sort=rank&limit=1'));
  assert.deepEqual(ranked.artifacts.map(item => item.artifact_id), ['github:2']);
  assert.equal(ranked.total, 2);
  assert.equal(ranked.next_cursor, '1');
  const licensed = endpoint.queryCatalog(catalog, new URL('https://forge.test/api/catalog?type=plugin&licensed=1&sort=name'));
  assert.deepEqual(licensed.artifacts.map(item => item.artifact_id), ['github:1']);
  assert.throws(
    () => endpoint.queryCatalog(catalog, new URL('https://forge.test/api/catalog?type=plugin&cursor=50001')),
    /Invalid catalog cursor/
  );
});

test('public discover view returns ranked gems per type, resolved packs, and records by id', async () => {
  const endpoint = await import(pathToFileURL(path.join(root, 'api/catalog.mjs')).href);
  const plugin = (id, stars = 0) => ({ artifact_id: 'github:' + id, artifact_type: 'plugin', full_name: 'o' + id + '/p' + id, name: 'p' + id, github_stars: stars });
  const registry = {
    schema_version: 1, snapshot_id: 's', entries: [{ artifact_id: 'github:9', artifact_type: 'fork', full_name: 'f/dsh', name: 'dsh' }],
    supplemental_entries: [plugin(1), plugin(2), plugin(3), plugin(4)], package_entries: []
  };
  const report = (id, rank, candidate = true) => ({ research: { artifact_id: 'github:' + id, rank, candidate, reasons: ['Reason ' + id] } });
  const research = {
    schema: 'dsh-forge.discovery-queue/v2', policy: 'dsh-forge.hidden-gems/v3', snapshot_id: 's',
    claims: { metadata_only: true, security_verified: false, executed: false },
    candidates: [report(3, 1), report(1, 2), report(2, 3, false), report(9, 1)],
    packs: [
      { id: 'memory-and-context', title: 'Memory & context', summary: 'Remember', members: [1, 2, 3].map(id => ({ artifact_id: 'github:' + id, role: 'R' + id, why: 'W' + id })) },
      { id: 'Bad Id!', title: 'x', members: [1, 2, 3].map(id => ({ artifact_id: 'github:' + id })) },
      { id: 'too-small', title: 'y', members: [{ artifact_id: 'github:1' }, { artifact_id: 'github:404' }] }
    ]
  };
  const feed = { snapshot_id: 's', counts: { forks: 1, plugins: 4, packages: 0, candidates: 4 } };
  const catalog = endpoint.validateCatalog(feed, registry, research);
  const view = endpoint.discoverView(catalog, { plugins: 5, forks: 5 });
  assert.equal(view.policy, 'dsh-forge.hidden-gems/v3');
  assert.deepEqual(view.gems.plugins.map(item => item.artifact_id), ['github:3', 'github:1']);
  assert.deepEqual(view.gems.forks.map(item => item.artifact_id), ['github:9']);
  assert.equal(view.gems.plugins[0].hidden_gem.reasons[0], 'Reason 3');
  assert.deepEqual(view.packs.map(pack => pack.id), ['memory-and-context']);
  assert.deepEqual(view.packs[0].members.map(member => [member.role, member.artifact.artifact_id]), [['R1', 'github:1'], ['R2', 'github:2'], ['R3', 'github:3']]);
  assert.equal(view.packs[0].members[1].artifact.hidden_gem.candidate, false);
});

test('without an imported store the browser still reads the embedded snapshot', () => {
  const c = instance();
  c.renderVals().goPlugins();
  let values = c.renderVals();
  assert.equal(c.usingCatalogStore(), false);
  assert.equal(values.catalogSourceLabel, 'A small sample');
  assert.equal(values.catalogFeedStatus, '');
  assert(values.results.length > 0);

  // A connected sidecar with nothing imported keeps using the embedded corpus.
  c.api = async () => ({ artifacts: [], total: 0 });
  connectedStore(c, { available: false, reason: 'No catalog store is imported yet' });
  values = c.renderVals();
  assert.equal(c.usingCatalogStore(), false);
  assert.match(values.catalogSourceLabel, /sync the catalog to see everything/);
});

test('an imported store replaces the embedded inventory and maps records identically', async () => {
  const c = instance();
  const fork = snapshot.entries[0];
  const requests = [];
  c.api = async url => {
    requests.push(url);
    return { artifacts: [fork], total: 23890, next_cursor: '77.50', generation: 77 };
  };
  c.renderVals().goForks();
  connectedStore(c, { available: true, artifact_count: 33839, counts: { plugin: 9949, fork: 23890, package: 0 } });
  await c.refreshCatalog();

  const values = c.renderVals();
  assert.equal(c.usingCatalogStore(), true);
  assert.equal(values.catalogSourceLabel, 'From your synced catalog');
  assert.equal(values.sortExplanation, 'Hidden gems first');
  assert.equal(values.results.length, 1);
  // The store hands back snapshot records; the browser applies its one mapping.
  const embedded = CATALOG.find(item => item.id === fork.artifact_id);
  assert.equal(values.results[0].slug, embedded.slug);
  assert.equal(values.results[0].rankLabel, embedded.rankLabel);
  assert.equal(values.results[0].commitUrl, embedded.commitUrl);
  // The count reports the corpus size, not just the page.
  assert.match(values.resultCount, /1 of 23,890 forks/);
  assert.equal(values.catalogFeedStatus, 'Scroll for more');
  assert(requests.at(-1).startsWith('/api/v1/catalog/search?'));
});

test('analyzed forks disclose immutable divergence evidence without claiming execution', async () => {
  const c = instance();
  const fork = snapshot.entries[0];
  const analyzed = {
    ...fork,
    divergence: {
      status: 'diverged', ahead_by: 4, behind_by: 2, listed_file_count: 300,
      files_truncated: true, changed_paths: ['plugins/memory/index.ts']
    },
    compatibility: {
      status: 'inferred_metadata', changed_surfaces: ['plugin runtime'],
      summary: 'Source-diff signals only; runtime compatibility has not been tested.'
    },
    analysis_evidence: {
      digest: 'sha256:' + 'a'.repeat(64), analyzer: 'dsh-forge.github-compare/v1'
    }
  };
  c.api = async () => ({
    artifacts: [analyzed], total: 1, next_cursor: '', generation: 8,
    research: { [fork.artifact_id]: {
      policy: 'dsh-forge.hidden-gems/v2', candidate: true, score: 91, rank: 1,
      confidence: 'source-diff-metadata', signals: [], gaps: []
    } }
  });
  c.renderVals().goForks();
  connectedStore(c, { available: true, counts: { plugin: 0, fork: 1, package: 0 } });
  await c.refreshCatalog();
  const row = c.renderVals().results[0];
  assert.deepEqual([row.aheadLabel, row.behindLabel, row.compared], ['+4', '/ −2', true]);
  row.select();
  const values = c.renderVals();
  assert.match(values.detailRows.find(item => item.k === 'Source difference').v, /4 fork-only commit/);
  assert.match(values.detailRows.find(item => item.k === 'Changed files').v, /provider limit reached/);
  assert.match(values.detailRows.find(item => item.k === 'Trust').v, /not executed or security-reviewed/);
  assert.match(values.detailEvidenceText, /300-file response limit/);
  // The lineage card reports the same evidence and marks the file list as partial.
  assert.deepEqual([values.forkAhead, values.forkBehind, values.forkFiles], ['4', '2', '300+']);
  assert.deepEqual(values.forkSurfaces, ['plugin runtime']);
});

test('fork coverage is disclosed beside imported results', () => {
  const c = instance();
  c.renderVals().goForks();
  connectedStore(c, {
    available: true,
    counts: { plugin: 9949, fork: 100, package: 0 },
    coverage: [{
      source: 'github-rest/fork-network', status: 'incomplete',
      discovered_count: 100, reported_count_after: 26095
    }]
  });
  assert.equal(c.renderVals().forkCoverageNote, 'Showing 100 of about 26,095 forks. The rest are still being added.');
});

test('recursive fork coverage does not compare descendants to a direct-root count', () => {
  const c = instance();
  c.renderVals().goForks();
  connectedStore(c, {
    available: true,
    counts: { plugin: 9949, fork: 26137, package: 0 },
    coverage: [{
      source: 'github-rest/fork-network', status: 'incomplete',
      discovered_count: 26137, descendant_count: 112, reported_count_after: 26099
    }]
  });
  assert.match(c.renderVals().forkCoverageNote, /Showing 26,137 forks found so far, including forks of forks\. GitHub lists 26,099 direct forks/);
});

test('permanent static deployment preserves the launcher security headers', () => {
  const headers = Object.fromEntries(vercel.headers[0].headers.map(item => [item.key, item.value]));
  assert.match(headers['Content-Security-Policy'], /script-src 'self'/);
  assert.match(headers['Content-Security-Policy'], /frame-ancestors 'none'/);
  assert.equal(headers['X-Content-Type-Options'], 'nosniff');
  assert.equal(headers['X-Frame-Options'], 'DENY');
  assert.equal(headers['Referrer-Policy'], 'no-referrer');
  assert.equal(rootVercel.outputDirectory, 'web');
  assert.deepEqual(rootVercel.headers, vercel.headers);
  assert.ok(vercelIgnore.includes('.serena'));
  assert.ok(vercelIgnore.includes('dist'));
});

test('imported research evidence marks only bounded hidden-gem candidates', async () => {
  const c = instance();
  const plugin = snapshot.supplemental_entries[0];
  const report = {
    policy: 'dsh-forge.hidden-gems/v2', artifact_id: plugin.artifact_id,
    score: 94, rank: 7, visibility: 'hidden', confidence: 'metadata-only',
    candidate: true, capabilities: ['orchestration'], quality_rank: 2,
    selection: { policy: 'dsh-forge.discovery-diversity/v1', score_window: 5, capability_lane: 'orchestration', owner_exposure_before: 0, capability_exposure_before: 1 },
    signals: [{ id: 'capability', points: 6, evidence: 'orchestration' }],
    gaps: ['compatibility unverified'], security_verified: false, executed: false
  };
  c.api = async () => ({
    artifacts: [plugin], research: { [plugin.artifact_id]: report },
    total: 9949, next_cursor: '', generation: 7
  });
  connectedStore(c, { available: true, artifact_count: 9949, counts: { plugin: 9949, fork: 0, package: 0 } });
  await c.refreshCatalog();

  const values = c.renderVals();
  assert.equal(values.results[0].rankLabel, 'H07');
  assert.equal(values.results[0].featuredLabel, 'Hidden gem');
  values.results[0].select();
  const detail = c.renderVals();
  assert(detail.detailRows.some(row => row.k === 'Hidden-gem score' && /94\/100/.test(row.v)));
  assert(detail.detailRows.some(row => row.k === 'Quality rank' && /Q02/.test(row.v)));
  assert(detail.detailRows.some(row => row.k === 'Discovery lane' && /orchestration/.test(row.v)));
  assert.match(detail.detailEvidenceText, /capability/);
  assert.equal(detail.sortExplanation, 'Hidden gems first');
});

test('a plugin-only imported store retains the embedded fork snapshot', () => {
  const c = instance();
  c.renderVals().goForks();
  connectedStore(c, { available: true, artifact_count: 9949, counts: { plugin: 9949, fork: 0, package: 0 } });

  const values = c.renderVals();
  assert.equal(c.usingCatalogStore(), false);
  assert.equal(values.results.length, 10);
  assert.equal(values.resultCount, '10 forks');
  assert.match(values.catalogSourceLabel, /small sample/);
});

test('store queries carry the active filters and load more appends by cursor', async () => {
  const c = instance();
  const requests = [];
  c.api = async url => {
    requests.push(new URLSearchParams(url.split('?')[1]));
    return {
      artifacts: [snapshot.supplemental_entries[requests.length - 1] || snapshot.supplemental_entries[0]],
      total: 40, next_cursor: '77.50', generation: 77
    };
  };
  c.renderVals().goPlugins();
  connectedStore(c);
  c.setState({ query: 'agent teams', catalogSort: 'stars', knownLicenseOnly: true });
  await c.refreshCatalog();

  const sent = requests.at(-1);
  assert.equal(sent.get('q'), 'agent teams');
  assert.equal(sent.get('type'), 'plugin');
  assert.equal(sent.get('sort'), 'stars');
  assert.equal(sent.get('featured'), null, 'the browser has no featured-only filter');
  assert.equal(sent.get('licensed'), '1');
  assert.equal(sent.get('cursor'), null);

  // Scrolling near the end of the feed is the only way to load the next page.
  const before = c.renderVals().results.length;
  c.renderVals().loadMoreOnScroll({ currentTarget: { scrollHeight: 1000, scrollTop: 600, clientHeight: 300 } });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(requests.at(-1).get('cursor'), '77.50');
  assert.equal(c.renderVals().results.length, before + 1, 'load more appends rather than replacing');
});

test('recommended sort asks for relevance only when there is a query', async () => {
  const c = instance();
  const requests = [];
  c.api = async url => {
    requests.push(new URLSearchParams(url.split('?')[1]));
    return { artifacts: [], total: 0, generation: 1 };
  };
  connectedStore(c);
  await c.refreshCatalog();
  assert.equal(requests.at(-1).get('sort'), 'rank');
  c.setState({ query: 'memory' });
  await c.refreshCatalog();
  assert.equal(requests.at(-1).get('sort'), 'relevance');
});

test('a slow reply for an abandoned query never overwrites the current results', async () => {
  const c = instance();
  const fork = snapshot.entries[0];
  let release;
  c.api = async url => {
    if (new URLSearchParams(url.split('?')[1]).get('q') === 'stale') {
      await new Promise(resolve => { release = resolve; });
      return { artifacts: [fork], total: 999, generation: 1 };
    }
    return { artifacts: [], total: 0, generation: 1 };
  };
  connectedStore(c);
  c.setState({ query: 'stale' });
  const slow = c.refreshCatalog();
  // The user retypes before the first reply lands.
  c.setState({ query: 'current' });
  await c.refreshCatalog();
  release();
  await slow;
  assert.equal(c.state.storeTotal, 0, 'the abandoned query must not win the race');
  assert.equal(c.state.storeArtifacts.length, 0);
});

test('a store failure is surfaced without falling back to a different corpus', async () => {
  const c = instance();
  c.api = async () => { throw new Error('The catalog was re-imported; restart the query from the first page'); };
  connectedStore(c);
  await c.refreshCatalog();
  const values = c.renderVals();
  assert.equal(values.hasStoreError, true);
  assert.match(values.storeError, /re-imported/);
  assert.equal(values.results.length, 0);
  assert.equal(c.usingCatalogStore(), true, 'an error must not silently swap corpora');
  assert.equal(values.noResults, true, 'a failed query is not presented as still loading');
});

test('typing schedules one coalesced store query instead of one per keystroke', () => {
  const c = instance();
  let calls = 0;
  c.api = async () => { calls += 1; return { artifacts: [], total: 0, generation: 1 }; };
  connectedStore(c);
  calls = 0;
  const values = c.renderVals();
  for (const value of ['a', 'ag', 'age', 'agen']) values.setQuery({ target: { value } });
  assert.equal(calls, 0, 'keystrokes must not each issue a request');
  assert(c._catalogTimer, 'a coalesced refresh should be pending');
  clearTimeout(c._catalogTimer);
});

test('package page selects a saved version and posts only stable local identities', async () => {
  const c = instance({}, '#packages/agent-teams-builder');
  const saved = {
    id: 'version_123456789abc', path: '~/dsh', state: 'ready', tree_ids: ['tree_123456789abc'],
    primary_tree: { id: 'tree_123456789abc', version: '0.1.2-rc.1' }
  };
  c.applyStatus({
    trees: [], cells: [], saved_versions: [saved], package_installations: [],
    trusted_package_recipes: [{ slug: 'agent-teams-builder', configured: true }],
    suggested_port: 3100, coverage_gaps: [], credentials: [], sandbox: { ready: true }
  });
  let request;
  c.api = async (url, options) => {
    request = { url, body: JSON.parse(options.body) };
    return { state: 'ready' };
  };
  c.refreshStatus = async () => {};
  const values = c.renderVals();
  assert.equal(values.installDisabled, false);
  assert.equal(values.packageVersions.length, 1);
  await values.installPackage();
  assert.deepEqual(request, {
    url: '/api/v1/packages/install',
    body: { package_slug: 'agent-teams-builder', version_id: saved.id, profile: 'web' }
  });
});

test('front page omits package promotion in V1', () => {
  const home = html.slice(html.indexOf('<sc-if value="{{ showLaunch }}"'), html.indexOf('<sc-if value="{{ showCatalog }}"'));
  assert(!/Certified packages|Verify, test & install/.test(home));
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

test('plugin browsing shows the complete available inventory without a featured filter', () => {
  const c = instance();
  c.renderVals().goPlugins();
  assert.equal(c.renderVals().results.length, 7);
  assert.equal(c.renderVals().catalogScopes, undefined);
  assert(!/All in snapshot/.test(html));
});

test('catalog page saves stable selections and signed package identity only when configured', async () => {
  const c = instance({}, '#packages/agent-teams-builder');
  const saved = {
    id: 'version_123456789abc', path: '~/dsh', state: 'ready', tree_ids: ['tree_123456789abc'],
    primary_tree: { id: 'tree_123456789abc', version: '0.1.2-rc.1' }
  };
  c.applyStatus({
    trees: [], cells: [], saved_versions: [saved], configurations: [], package_installations: [],
    trusted_package_recipes: [{ slug: 'agent-teams-builder', configured: true }],
    suggested_port: 3100, coverage_gaps: [], credentials: [], sandbox: { ready: true }
  });
  let request;
  c.api = async (url, options) => {
    request = { url, body: JSON.parse(options.body) };
    return { id: 'config_1234567890abcdef1234' };
  };
  c.refreshStatus = async () => {};
  await c.renderVals().saveConfiguration();
  assert.equal(request.url, '/api/v1/configurations');
  assert.equal(request.body.version_id, saved.id);
  assert.equal(request.body.package_slug, 'agent-teams-builder');
  assert.deepEqual(request.body.selections, [{ type: 'package', id: 'catalog-package:agent-teams-builder' }]);
  assert.equal(request.body.draft, false);
  assert(!('path' in request.body));
});

test('plugin page checks only an exact declared version list against local versions', () => {
  const saved = version => ({
    id: 'version_' + version.replace(/\W/g, ''), path: '~/' + version, state: 'ready', tree_ids: [],
    primary_tree: { id: 'tree_' + version, version, launchability: 'ready' }
  });
  const c = instance();
  c.applyStatus({
    trees: [], cells: [], saved_versions: [saved('0.1.2-rc.1'), saved('0.1.2-alpha.3')],
    suggested_port: 3100, coverage_gaps: [], credentials: []
  });
  const exact = snapshot.supplemental_entries.find(entry => entry.compatibility.declared_dsh_range === '0.1.2-rc.1 || 0.1.2-alpha.5 || 0.1.2-alpha.2');
  c.selectCatalogArtifact({ id: exact.artifact_id, type: 'plugin' });
  assert.deepEqual(c.renderVals().localCompatibility.map(item => [item.version, item.listed]),
    [['0.1.2-rc.1', true], ['0.1.2-alpha.3', false]]);
  // A real range with a prose qualifier is shown, never evaluated.
  const ranged = snapshot.supplemental_entries.find(entry => /^>=/.test(entry.compatibility.declared_dsh_range || ''));
  c.selectCatalogArtifact({ id: ranged.artifact_id, type: 'plugin' });
  const values = c.renderVals();
  assert.equal(values.detailDeclaredRange, ranged.compatibility.declared_dsh_range);
  assert.deepEqual(values.localCompatibility, []);
});

test('favorites filter lists only saved artifacts of the open browser', () => {
  stored.clear();
  const c = instance();
  c.renderVals().goPlugins();
  const plugin = c.renderVals().results[2];
  plugin.select();
  c.renderVals().toggleFavorite();
  c.renderVals().backToCatalog();
  c.renderVals().toggleFavoritesOnly();
  assert.deepEqual(c.renderVals().results.map(r => r.id), [plugin.id]);
  assert.equal(c.renderVals().resultCount, '1 saved plugins');
  // A page opened by its route (no record loaded yet) is found by id, so the filter
  // never blanks a page that isn't a favorite.
  const other = CATALOG.find(item => item.type === 'plugin' && item.id !== plugin.id);
  c.setState({ detailOpen: true, artifactId: other.id, detailArtifact: null });
  assert.equal(c.renderVals().detail.id, other.id);
  c.renderVals().backToCatalog();
  c.renderVals().goForks();
  assert.equal(c.renderVals().results.length, 0);
  assert.equal(c.renderVals().emptyTitle, 'No saved forks yet');
  c.renderVals().resetCatalogFilters();
  assert.equal(c.renderVals().results.length, 10);
  stored.clear();
});

test('running sessions sit under the version that started them', () => {
  const c = instance();
  const tree = { id: 'tree_a', trust: 'personal', launchability: 'ready', version: '1.0.0', name: 'DSH', git: { sha: 'abcdef123456', branch: 'main' } };
  const cell = (id, treeId) => ({ id, name: id, treeId, port: 3101, started: Date.now(), process: 'alive', state: 'running', agent_state: 'idle' });
  c.applyStatus({
    trees: [tree], cells: [cell('mine', 'tree_a'), cell('orphan', 'tree_gone')], profiles: [],
    sandbox: { ready: true }, credentials: [], coverage_gaps: [],
    saved_versions: [{ id: 'version_a', state: 'ready', source: 'auto', tree_ids: ['tree_a'], primary_tree: tree }]
  });
  const values = c.renderVals();
  assert.deepEqual(values.versionGroups.map(group => [group.isVersion, group.cells.map(item => item.id)]),
    [[true, ['mine']], [false, ['orphan']]]);
  assert.equal(values.versions[0].gitLine, 'main @ abcdef1');
  assert.equal(values.versions[0].runningLabel, '1 running');
  // Logs open inline for one session at a time and close again.
  c.inspectCell = async target => c.setState({ logCell: target.id });
  values.versions[0].cells[0].toggleLogs();
  assert.equal(c.renderVals().versions[0].cells[0].expanded, true);
  c.renderVals().versions[0].cells[0].toggleLogs();
  assert.equal(c.state.logCell, null);
});

test('a plugin page whose policy cannot load fails closed and says why', async () => {
  const c = instance();
  const plugin = CATALOG.find(item => item.type === 'plugin');
  c.api = async () => { throw new Error('Unknown catalog artifact'); };
  c.setState({ sidecarConnected: true });
  c.selectCatalogArtifact(plugin);
  await c.loadCatalogArtifact(plugin.id);
  const values = c.renderVals();
  assert.equal(values.installAndRunDisabled, true);
  assert.equal(values.installAndRunReason, 'No signed recipe could be checked: Unknown catalog artifact');
  assert.equal(values.hasStoreError, false, 'an artifact lookup is not a feed error');
});

test('a tab switch never renders the previous tab store records', () => {
  const c = instance();
  connectedStore(c, { available: true, counts: { plugin: 10, fork: 10, package: 0 } });
  c.setState({ storeArtifacts: CATALOG.filter(item => item.type === 'fork'), catalogType: 'plugin' });
  const values = c.renderVals();
  assert.equal(values.results.length, 0);
  clearTimeout(c._catalogTimer);
});

test('Assistant tab starts a saved Harness through its dedicated endpoint', async () => {
  const c = instance({}, '#assistant');
  const saved = {
    id: 'version_123456789abc', path: '~/dsh', state: 'ready', tree_ids: ['tree_123456789abc'],
    primary_tree: { id: 'tree_123456789abc', version: '0.1.2-rc.1' }
  };
  c.applyStatus({
    trees: [], cells: [], saved_versions: [saved], configurations: [],
    suggested_port: 3100, coverage_gaps: [], credentials: [],
    sandbox: { ready: true, reason: 'ready' }
  });
  c.refreshStatus = async () => {};
  let request;
  c.api = async (url, options) => {
    request = { url, body: JSON.parse(options.body) };
    return { id: 'cell_assistant' };
  };
  const values = c.renderVals();
  assert(values.showAssistant);
  assert.equal(values.assistantStartDisabled, false);
  await values.startAssistant();
  assert.deepEqual(request, {
    url: '/api/v1/assistant/start', body: { version_id: saved.id }
  });
  assert.match(html, /Isolated DeepSeek Harness Forge Assistant/);
});

test('thumbnails are deterministic generated art with allowlisted GitHub layers', () => {
  const c = instance({}, '#forks');
  const first = c.renderVals().results;
  const again = instance({}, '#forks').renderVals().results;
  assert.equal(first.length, 10);
  assert.deepEqual(first.map(item => item.coverStyle), again.map(item => item.coverStyle));
  assert.equal(new Set(first.map(item => item.coverStyle)).size, first.length);
  for (const item of first) {
    assert.match(item.coverStyle, /^background: url\("data:image\/svg\+xml,/);
    assert.match(item.thumbStyle, /data:image\/svg\+xml/);
    assert.match(item.avatarStyle, /--avatar: url\("https:\/\/avatars\.githubusercontent\.com\/[A-Za-z0-9-]+\?s=96"\)/);
    assert.equal(item.hasPreview, false);
  }
  const Thumb = (record) => {
    const view = instance({}, '#forks');
    view.setState({ storeArtifacts: [], favoriteArtifacts: [record], favoritesOnly: true });
    return view.renderVals().results[0];
  };
  const preview = 'https://repository-images.githubusercontent.com/42/3f2a9c1e-1b2c-4d5e-8f90-a1b2c3d4e5f6';
  const safe = Thumb({ id: 'github:42', type: 'fork', name: 'x', owner: 'octo', url: 'https://github.com/octo/x', social_preview_url: preview });
  assert.equal(safe.hasPreview, true);
  assert(safe.coverStyle.startsWith('background: url("' + preview + '") center / cover no-repeat, url("data:'));
  const hostile = Thumb({
    id: 'github:43', type: 'fork', name: 'x', owner: 'o"); background: url(https://evil.example/',
    url: 'https://github.com/o/x', social_preview_url: 'https://evil.example/p.png', owner_avatar_url: 'https://evil.example/a.png'
  });
  assert.equal(hostile.hasPreview, false);
  assert.equal(hostile.hasAvatar, false);
  assert(!/evil\.example/.test(hostile.coverStyle + hostile.avatarStyle));
});

test('thumbnail template has no inline handlers or eagerly loaded images', () => {
  const template = html.slice(html.indexOf('<x-dc>'), html.indexOf('</x-dc>'));
  assert(!/<img\b/i.test(template));
  assert(!/\sonError=/i.test(template));
  assert(!/<path d="\{\{/.test(template));
  assert.match(template, /class="cover" style="\{\{ r\.coverStyle \}\}"/);
  assert.match(template, /class="banner" style="\{\{ detailThumb\.bannerStyle \}\}"/);
  for (const policy of [vercel.headers[0].headers[0].value, rootVercel.headers[0].headers[0].value]) {
    assert.match(policy, /img-src 'self' data: https:\/\/avatars\.githubusercontent\.com https:\/\/repository-images\.githubusercontent\.com;/);
  }
});

test('card and list layouts are remembered per catalog type', () => {
  stored.delete('dsh-forge:catalog-layout:v1');
  const c = instance({}, '#forks');
  assert.equal(c.renderVals().showCardGrid, true);
  c.renderVals().useListLayout();
  assert.equal(c.renderVals().showForkList, true);
  assert.equal(c.renderVals().showCardGrid, false);
  assert.deepEqual(JSON.parse(stored.get('dsh-forge:catalog-layout:v1')), { plugin: 'grid', fork: 'list' });
  c.setState({ catalogType: 'plugin' });
  assert.equal(c.renderVals().showCardGrid, true);
  stored.delete('dsh-forge:catalog-layout:v1');
});

const FORK_ID = 'github:1333146268';
function forkDetail(status = {}) {
  const c = instance({}, '#forks/' + encodeURIComponent(FORK_ID));
  c.refreshStatus = async () => {};
  c.applyStatus({
    trees: [], cells: [], saved_versions: [], suggested_port: 3100, coverage_gaps: [], credentials: [],
    sandbox: { ready: true, reason: 'ready' }, ...status
  });
  return c;
}

test('fork pages review the pinned commit before installing', async () => {
  const offline = instance({}, '#forks/' + encodeURIComponent(FORK_ID)).renderVals();
  assert.equal(offline.isForkDetail, true);
  assert.equal(offline.forkInstallLabel, 'Start DSH Forge to install');
  assert.equal(offline.forkInstallDisabled, true);

  const c = forkDetail();
  const requests = [];
  c.api = async (url, options) => {
    requests.push({ url, body: JSON.parse(options.body) });
    if (url === '/api/v1/forks/plan') {
      return {
        artifact_id: FORK_ID, full_name: 'salathleizhang/deepseek-harness-desktop', commit: 'fe8e3f8d5e190e756c29c46036b4d879cf7bc754',
        commit_source: 'catalog', destination: '~/dsh-versions/forks/x', steps: ['fetch', 'build', 'register']
      };
    }
    return { id: 'fork_0123456789abcdef', state: 'queued' };
  };
  let values = c.renderVals();
  assert.equal(values.forkInstallLabel, 'Install…');
  await values.forkInstallAction();
  values = c.renderVals();
  assert.equal(values.forkPlanOpen, true);
  assert.equal(values.forkPlanCommit, 'fe8e3f8d5e190e756c29c46036b4d879cf7bc754');
  assert.equal(values.forkInstallConfirmDisabled, true);
  await values.confirmForkInstall();
  assert.equal(requests.length, 1, 'no install without acknowledgement');
  values.toggleForkRisk({ target: { checked: true } });
  await c.renderVals().confirmForkInstall();
  assert.deepEqual(requests[1], {
    url: '/api/v1/forks/install',
    body: { artifact_id: FORK_ID, commit: 'fe8e3f8d5e190e756c29c46036b4d879cf7bc754', acknowledge_risk: true }
  });
  assert.equal(c.renderVals().forkPlanOpen, false);
});

test('installed forks launch only through the sandbox acknowledgement', async () => {
  const tree = {
    id: 'tree_fork', version: '0.1.0-fork', path: '~/dsh-versions/forks/x', trust: 'community', launchability: 'ready',
    community: { install_id: 'fork_0123456789abcdef', full_name: 'salathleizhang/deepseek-harness-desktop', commit: 'fe8e3f8d5e190e756c29c46036b4d879cf7bc754' }
  };
  const personal = { id: 'tree_mine', version: '0.1.0', path: '~/dsh', trust: 'personal', launchability: 'ready' };
  const c = forkDetail({
    trees: [tree, personal],
    saved_versions: [
      { id: 'version_aaaaaaaaaaaa', path: tree.path, source: 'auto', state: 'ready', tree_ids: [tree.id], primary_tree: tree },
      { id: 'version_bbbbbbbbbbbb', path: personal.path, source: 'manual', state: 'ready', tree_ids: [personal.id], primary_tree: personal }
    ],
    fork_installations: [{ id: 'fork_0123456789abcdef', artifact_id: FORK_ID, state: 'ready', tree_id: tree.id, commit: tree.community.commit, path: tree.path }]
  });
  let values = c.renderVals();
  assert.equal(values.forkInstallLabel, 'Launch…');
  assert.equal(values.forkInstallPill, 'Installed');
  assert.deepEqual(values.packageVersions.map(item => item.id), ['version_bbbbbbbbbbbb']);
  assert.equal(c.defaultHostVersionId(), 'version_bbbbbbbbbbbb');

  const local = values.versions.find(item => item.treeId === tree.id);
  assert.equal(local.isCommunity, true);
  assert.equal(local.buttonLabel, 'Launch…');
  let launched;
  c.api = async (url, options) => { launched = { url, body: JSON.parse(options.body) }; return { id: 'cell_x', port: 3200 }; };
  c.inspectCell = async () => {};
  local.launch();
  values = c.renderVals();
  assert.equal(values.communityLaunchOpen, true);
  assert.equal(values.communityLaunchDisabled, true);
  values.toggleCommunityRisk({ target: { checked: true } });
  await c.renderVals().confirmCommunityLaunch();
  assert.equal(launched.url, '/api/v1/cells');
  assert.equal(launched.body.tree_id, tree.id);
  assert.equal(launched.body.acknowledge_risk, true);
  assert.equal(launched.body.home_mode, 'fresh');

  const forks = instance({}, '#forks');
  forks.setState({ forkInstallations: [{ artifact_id: FORK_ID, state: 'building' }] });
  assert.equal(forks.renderVals().results.find(item => item.id === FORK_ID).installedLabel, 'Installing');
});

test('failed fork installs explain the failure and can be retried or removed', () => {
  const c = forkDetail({
    fork_installations: [{ id: 'fork_0123456789abcdef', artifact_id: FORK_ID, state: 'failed', detail: 'Build step exited with 1', path: '~/x' }]
  });
  const values = c.renderVals();
  assert.equal(values.forkInstallPill, 'Failed');
  assert.equal(values.forkInstallText, 'Build step exited with 1');
  assert.equal(values.forkInstallLabel, 'Try again…');
  assert.equal(values.forkRemovable, true);
});

test('signed-in favorites merge with this browser and sync on change', async () => {
  const c = instance({}, '#plugins');
  const requests = [];
  const remote = [{ id: 'github:1', type: 'plugin', name: 'remote' }];
  c.setState({ favoriteArtifacts: [{ id: 'github:2', type: 'fork', name: 'local' }, { id: 'github:1', type: 'plugin', name: 'stale' }] });
  c.api = async (url, options = {}) => {
    requests.push({ url, method: options.method || 'GET', body: options.body ? JSON.parse(options.body) : null });
    if (url === '/api/auth/session') return { configured: true, sync: true, user: { id: 'github:9', login: 'octo', name: 'Octo', avatar_url: '' } };
    if (url === '/api/favorites' && !options.method) return { favorites: remote, updated_at: 1 };
    return { favorites: [], updated_at: 2 };
  };
  await c.loadAuth();
  assert.deepEqual(c.state.favoriteArtifacts.map(item => [item.id, item.name]), [['github:1', 'remote'], ['github:2', 'local']]);
  assert.deepEqual(requests.map(item => [item.url, item.method]), [
    ['/api/auth/session', 'GET'], ['/api/favorites', 'GET'], ['/api/favorites', 'PUT']
  ]);
  assert.equal(c.state.favoritesSync, 'synced');
  const values = c.renderVals();
  assert.equal(values.signedIn, true);
  assert.equal(values.accountLogin, '@octo');
  assert.match(values.accountSyncLabel, /synced/);
  c.setState({ favoritesOnly: true });
  assert.equal(c.renderVals().catalogFeedStatus, 'Saved items sync to @octo');

  c.scheduleFavoriteSync = () => { c.syncScheduled = true; };
  c.toggleFavorite({ id: 'github:3', type: 'plugin', name: 'new' });
  assert.equal(c.syncScheduled, true);
  await c.signOut();
  assert.equal(c.renderVals().signedOut, true);
  assert.equal(c.state.favoriteArtifacts.length, 3, 'signing out keeps local favorites');
});

test('sign-in stays hidden when the deployment has no auth configured', async () => {
  const c = instance({}, '#plugins');
  c.api = async () => ({ configured: false, sync: false, user: null });
  await c.loadAuth();
  const values = c.renderVals();
  assert.equal(values.showAccount, false);
  c.api = async () => { throw new Error('Unknown API endpoint'); };
  await c.loadAuth();
  assert.equal(c.renderVals().showAccount, false);
});

// ---- Discover, packs, likes, and plain-language pages

function onWebsite(run) {
  const previous = { ...windowStub.location };
  Object.assign(windowStub.location, { href: 'https://dsh-forge.vercel.app/', protocol: 'https:', hostname: 'dsh-forge.vercel.app' });
  return Promise.resolve().then(run).finally(() => Object.assign(windowStub.location, previous));
}

function discoverPayload() {
  const plugins = snapshot.supplemental_entries.slice(0, 4).map((entry, index) => ({
    ...entry,
    hidden_gem: {
      policy: 'dsh-forge.hidden-gems/v3', artifact_id: entry.artifact_id, score: 90 - index, rank: index + 1, candidate: true,
      reasons: index < 3
        ? ['Has a test suite and runs CI on every change.', (10 + index) + ' commits in the last 90 days.']
        : ['Has a test suite and runs CI on every change.'],
      built_percentile: 95 - index
    }
  }));
  const fork = { ...snapshot.entries[0], hidden_gem: { policy: 'dsh-forge.hidden-gems/v3', artifact_id: snapshot.entries[0].artifact_id, rank: 1, candidate: true, reasons: ['Adds 12 commits on top of DeepSeek Harness.'] } };
  return {
    gems: { plugins, forks: [fork] },
    packs: [{
      id: 'memory-and-context', title: 'Memory & context', summary: 'Remember across sessions.',
      members: plugins.slice(0, 3).map((artifact, index) => ({ role: ['Memory', 'Code navigation', 'Search'][index], why: 'Why ' + index, artifact }))
    }],
    policy: 'dsh-forge.hidden-gems/v3',
    catalog_store: { available: true, public: true, artifact_count: 40275, counts: { plugin: 11656, fork: 28619, package: 0 } }
  };
}

test('the website leads with Discover: gems, packs, and forks with plain reasons', () => onWebsite(async () => {
  const c = instance({}, '#discover');
  const requests = [];
  c.api = async url => { requests.push(url); return discoverPayload(); };
  await c.loadDiscover();
  const values = c.renderVals();
  assert.equal(requests[0], '/api/catalog?view=discover');
  assert.equal(values.showDiscover, true);
  assert.equal(values.showCatalogFeed, false);
  assert.equal(values.discoverTabCurrent, 'page');
  assert.equal(values.pluginsTabCurrent, 'false');
  // Desktop-only tabs and the connection pill are not part of the website.
  assert.equal(values.showDesktopTabs, false);
  assert.equal(values.showStatusPill, false);
  assert.equal(values.discoverPlugins.length, 4);
  assert.match(values.discoverScope, /40,275 plugins and forks/);
  // A reason already on two cards gives way to the card's next one.
  assert.deepEqual(values.discoverPlugins.map(card => card.topReason), [
    'Has a test suite and runs CI on every change.',
    'Has a test suite and runs CI on every change.',
    '12 commits in the last 90 days.',
    'Has a test suite and runs CI on every change.'
  ]);
  // Cards in a shelf of gems don't repeat "Hidden gem" on every cover.
  assert(values.discoverPlugins.every(card => !card.featured));
  assert.equal(values.discoverForks[0].topReason, 'Adds 12 commits on top of DeepSeek Harness.');
  assert.equal(values.discoverForks[0].aheadText, '');
  assert.equal(values.discoverPacks[0].count, '3 plugins');
  assert.equal(values.discoverPacks[0].roles, 'Memory · Code navigation · Search');
  assert.match(html, /How picks work/);
  assert.match(html, /No AI guessing/);
}));

test('packs open their own page and a plugin opened from a pack returns to it', () => onWebsite(async () => {
  const c = instance({}, '#discover');
  c.api = async () => discoverPayload();
  c.componentDidMount();
  try {
    await c.loadDiscover();
    c.renderVals().discoverPacks[0].open();
    assert.equal(windowStub.location.hash, 'packs/memory-and-context');
    windowStub.location.hash = '#packs/memory-and-context';
    listeners.get('hashchange')();
    let values = c.renderVals();
    assert.equal(values.showPackPage, true);
    assert.equal(values.showDiscover, false);
    assert.equal(values.pack.title, 'Memory & context');
    assert.deepEqual(values.pack.members.map(member => member.role), ['Memory', 'Code navigation', 'Search']);
    values.pack.members[0].select();
    windowStub.location.hash = '#' + windowStub.location.hash;
    listeners.get('hashchange')();
    values = c.renderVals();
    assert.equal(values.showArtifactPage, true);
    assert.equal(values.backLabel, 'Memory & context');
    assert.equal(values.discoverTabCurrent, 'page');
    values.backToCatalog();
    assert.equal(windowStub.location.hash, 'packs/memory-and-context');
    windowStub.location.hash = '#packs/unknown';
    listeners.get('hashchange')();
    assert.equal(c.renderVals().noPack, true);
    // History navigation to a page opened elsewhere doesn't inherit the pack as its origin.
    const plugin = snapshot.supplemental_entries[5];
    windowStub.location.hash = '#plugins/' + encodeURIComponent(plugin.artifact_id);
    listeners.get('hashchange')();
    values = c.renderVals();
    assert.equal(values.showArtifactPage, true);
    assert.equal(values.backLabel, 'Plugins');
    assert.equal(values.pluginsTabCurrent, 'page');
  } finally {
    c.componentWillUnmount();
    windowStub.location.hash = '';
  }
}));

test('likes respond at once, keep the server count, and roll back on failure', async () => {
  stored.clear();
  const c = instance({}, '#plugins');
  c.setState({ likes: { enabled: true, counts: { 'github:1': 4 }, liked: {} } });
  let release;
  const requests = [];
  c.api = (url, options) => {
    requests.push({ url, headers: options.headers, body: JSON.parse(options.body) });
    return new Promise(resolve => { release = resolve; });
  };
  const view = c.likeView('github:1');
  assert.equal(view.likeLabel, '4');
  assert.equal(view.likePressed, 'false');
  let stopped = false;
  view.toggleLike({ stopPropagation: () => { stopped = true; }, preventDefault() {} });
  // Liking from a card never opens the card.
  assert.equal(stopped, true);
  assert.equal(c.likeView('github:1').likeLabel, '5');
  assert.equal(c.likeView('github:1').likeClass, 'like like-on');
  assert.deepEqual(requests[0].body, { id: 'github:1', liked: true });
  assert.match(requests[0].headers['X-Forge-Visitor'], /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  release({ id: 'github:1', liked: true, count: 7 });
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(c.likeView('github:1').likeLabel, '7');

  // A failure undoes only that item, not likes that changed meanwhile.
  c.api = async () => {
    c.setState({ likes: { ...c.state.likes, counts: { ...c.state.likes.counts, 'github:2': 3 } } });
    throw new Error('Too many likes for now; try again later');
  };
  await c.toggleLike('github:1');
  assert.equal(c.likeView('github:2').likeLabel, '3');
  assert.equal(c.likeView('github:1').likeLabel, '7');
  assert.equal(c.likeView('github:1').likePressed, 'true');
  assert.equal(c.lastMessage, 'Too many likes for now; try again later');
  // Records the server can't hold likes for (packages) get no heart.
  assert.equal(c.likeView('catalog-package:memory-kit').showLike, false);
  // Without a store there is no heart at all.
  c.setState({ likes: { enabled: false, counts: {}, liked: {} } });
  assert.equal(c.likeView('github:1').showLike, false);
});

test('detail pages open GitHub directly and keep internals in a collapsed section', () => {
  const c = instance();
  c.renderVals().goForks();
  const fork = c.renderVals().results[0];
  fork.select();
  const values = c.renderVals();
  assert.equal(values.detailGitHubUrl, values.detail.url);
  assert.match(values.detailGitHubUrl, /^https:\/\/github\.com\//);
  assert.match(html, /Open on GitHub<\/a>/);
  assert(!/Copy commit link|Risk and evidence|Source and provenance|Sandbox recipe required/.test(html));
  assert.match(html, /<details class="card tech">\s*<summary class="h2">Technical details<\/summary>/);
  // Developer-only actions appear only with the desktop app connected.
  assert.equal(values.showDeveloperActions, false);
});
