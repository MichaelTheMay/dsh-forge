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
const vercel = JSON.parse(fs.readFileSync(path.join(root, 'web/vercel.json'), 'utf8'));
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
test('launcher remains default and Community opens individual plugins and forks', () => {
  const c = instance(); assert(c.renderVals().showLaunch); assert(!c.renderVals().showCatalog);
  assert.equal(c.state.cells.length, 0);
  assert.equal(c.renderVals().modeLabel, 'Preview');
  assert.match(c.renderVals().launchHint, /No sample process is presented as real/);
  c.renderVals().goCatalog(); assert(c.renderVals().showCatalog); assert(!c.renderVals().showLaunch);
  assert.equal(windowStub.location.hash, 'plugins');
  c.renderVals().results[0].select();
  assert.equal(windowStub.location.hash, 'plugins');
  c.renderVals().repoTypes.find(f => f.id === 'fork').select();
  assert.equal(windowStub.location.hash, 'forks');
  assert.deepEqual(c.renderVals().repoTypes.map(f => f.id), ['plugin', 'fork']);
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
    saved_versions: [{ id: 'version_123456789abc', path: '~/dsh', state: 'ready', tree_ids: ['real'], primary_tree: { id: 'real', name: 'detected', kind: 'source', version: '1', path: '~/dsh', git: null, trust: 'personal', launchability: 'ready' } }],
    cells: [], suggested_port: 3210, coverage_gaps: [], credentials: []
  });
  assert.equal(c.state.trees.length, 1);
  assert.equal(c.state.trees[0].id, 'real');
  assert.equal(c.state.savedVersions.length, 1);
  assert.equal(c.renderVals().modeLabel, 'Local');
  assert.equal(c.renderVals().suggested, 3210);
});
test('portable preview shows no versions or cells that are not locally detected', () => {
  const c = instance(); const values = c.renderVals();
  assert.equal(values.versions.length, 0);
  assert(values.noVersions);
  assert.equal(values.trees.length, 0);
  assert.equal(values.cells.length, 0);
  assert.match(script, /Isolation ready/);
  assert(!/Fail-closed cell fleet/.test(html));
  assert(!/quota unenforced/.test(html));
  assert.match(script, /sandbox test .*network none .*no launcher secrets/);
});
test('launcher auto-detects its versions directory and keeps manual add compact', async () => {
  assert.match(html, />\s*\{\{ addVersionLabel \}\}\s*</i);
  assert.match(html, /Versions in.*versionsDirectory.*appear automatically/s);
  assert.match(html, />Add version</);
  assert(!/Rescan saved versions/.test(html));
  assert(!/>\s*Scan roots\s*</i.test(html));
  assert(!/>\s*Add folder(?:…|\.\.\.)?\s*</i.test(html));
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
  c.setState({ sidecarConnected: true, versionPath: '/tmp/dsh' });
  await c.saveLocalVersion();
  assert.deepEqual(request, {
    url: '/api/v1/scan', method: 'POST', body: { roots: ['/tmp/dsh'] }
  });
  assert.equal(c.state.savedVersions.length, 1);
  assert.equal(c.state.versionFormOpen, false);
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
test('community browser exposes plugins and forks without provisional package promotion', () => {
  const c = instance();
  c.renderVals().goCatalog();
  assert.equal(c.renderVals().results.length, 7);
  assert.deepEqual(c.renderVals().repoTypes.map(f => [f.id, f.count]), [['plugin', 7], ['fork', 10]]);
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
test('repository actions stay disabled while signed package install is locally gated', () => {
  const section = html.slice(html.indexOf('<main class="public-browser"'), html.indexOf('<sc-if value="{{ previewOpen }}"'));
  // Composition and upload remain the only disabled affordance: one-click install stays
  // package-only, while plugins and forks now hand over an explicit command instead.
  const disabled = section.match(/<button disabled(?: title="([^"]*)")?/g) || [];
  assert.equal(disabled.length, 1);
  assert.match(disabled[0], /Package composition and upload are a separate boundary\./);
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

test('plugin detail hands over an exact-version command targeting a detected profile', async () => {
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
  let values = c.renderVals();
  assert.equal(values.isPluginDetail, true);
  // The default target is the detected web profile, and the version is pinned exactly.
  assert.equal(values.pluginInstallCommand,
    'dsh plugin --profile web add ' + plugin.package.name + '@' + plugin.package.version);
  assert.match(values.pluginInstallCommand, /@\d+\.\d+\.\d+/);
  values.setCatalogProfile({ target: { value: 'profile_' + 'b'.repeat(16) } });
  values = c.renderVals();
  assert.match(values.pluginInstallCommand, /--profile coding /);
  // Copying is the only action: the browser never runs the plugin manager itself.
  await values.copyPluginInstall();
  assert.equal(clipboard.at(-1), values.pluginInstallCommand);
  assert(!/\/api\/v1\/plugins\/install/.test(script));
});

test('non-npm plugins get no invented command and forks download a pinned archive', () => {
  const c = instance();
  const mcpb = snapshot.supplemental_entries.find(entry => entry.package.registry !== 'npm');
  c.selectCatalogArtifact({ id: mcpb.artifact_id, type: 'plugin' });
  let values = c.renderVals();
  assert.equal(values.pluginInstallable, false);
  assert.equal(values.pluginCommandUnavailable, true);
  assert.equal(values.pluginInstallCommand, '');

  const fork = snapshot.entries[0];
  c.selectCatalogArtifact({ id: fork.artifact_id, type: 'fork' });
  values = c.renderVals();
  assert.equal(values.isForkDetail, true);
  assert.equal(values.forkDownloadUrl,
    'https://codeload.github.com/' + fork.full_name + '/tar.gz/' + fork.head_sha);
  assert.match(values.forkDownloadCommand, /^curl --fail --location --output /);
  assert(values.forkDownloadCommand.includes(fork.head_sha));
});

test('community browser does not publish provisional curated packages or featured strips', () => {
  const c = instance();
  const values = c.renderVals();
  assert.deepEqual(values.repoTypes.map(item => item.id), ['plugin', 'fork']);
  assert(!/Forge picks/.test(html));
  assert(!/Administrator curated hidden gems/.test(html));
});

function connectedStore(c, store = { available: true, artifact_count: 24000 }) {
  c.applyStatus({
    trees: [], cells: [], saved_versions: [], package_installations: [],
    trusted_package_recipes: [], configurations: [], profiles: [],
    suggested_port: 3100, coverage_gaps: [], credentials: [], sandbox: { ready: true },
    catalog_store: store
  });
}

test('without an imported store the browser still reads the embedded snapshot', () => {
  const c = instance();
  c.renderVals().goCatalog();
  let values = c.renderVals();
  assert.equal(values.storeActive, false);
  assert.equal(values.catalogSourceLabel, 'Embedded snapshot');
  assert.equal(values.canLoadMore, false);
  assert(values.results.length > 0);

  // A connected sidecar with nothing imported keeps using the embedded corpus.
  c.api = async () => ({ artifacts: [], total: 0 });
  connectedStore(c, { available: false, reason: 'No catalog store is imported yet' });
  values = c.renderVals();
  assert.equal(values.storeActive, false);
  assert.match(values.catalogSourceLabel, /no store imported/);
});

test('an imported store replaces the embedded inventory and maps records identically', async () => {
  const c = instance();
  const fork = snapshot.entries[0];
  const requests = [];
  c.api = async url => {
    requests.push(url);
    return { artifacts: [fork], total: 23890, next_cursor: '77.50', generation: 77 };
  };
  c.renderVals().repoTypes.find(f => f.id === 'fork').select();
  connectedStore(c, { available: true, artifact_count: 33839, counts: { plugin: 9949, fork: 23890, package: 0 } });
  await c.refreshCatalog();

  const values = c.renderVals();
  assert.equal(values.storeActive, true);
  assert.equal(values.catalogSourceLabel, 'Imported catalog store');
  assert.equal(values.catalogCountLabel, '9,949 plugins · 23,890 forks');
  assert.equal(values.repoTypes.find(type => type.id === 'plugin').count, 9949);
  assert.match(values.sortExplanation, /metadata only, not a security verdict/);
  assert.equal(values.results.length, 1);
  // The store hands back snapshot records; the browser applies its one mapping.
  const embedded = CATALOG.find(item => item.id === fork.artifact_id);
  assert.equal(values.results[0].slug, embedded.slug);
  assert.equal(values.results[0].rankLabel, embedded.rankLabel);
  assert.equal(values.results[0].commitUrl, embedded.commitUrl);
  // The count reports the corpus size, not just the page.
  assert.match(values.resultCount, /1 of 23,890 forks/);
  assert.equal(values.canLoadMore, true);
  assert(requests.at(-1).startsWith('/api/v1/catalog/search?'));
});

test('fork coverage is disclosed beside imported results', () => {
  const c = instance();
  c.renderVals().repoTypes.find(f => f.id === 'fork').select();
  connectedStore(c, {
    available: true,
    counts: { plugin: 9949, fork: 100, package: 0 },
    coverage: [{
      source: 'github-rest/fork-network', status: 'incomplete',
      discovered_count: 100, reported_count_after: 26095
    }]
  });
  assert.match(c.renderVals().catalogSourceLabel, /incomplete network \(100 of 26,095\)/);
});

test('recursive fork coverage does not compare descendants to a direct-root count', () => {
  const c = instance();
  c.renderVals().repoTypes.find(f => f.id === 'fork').select();
  connectedStore(c, {
    available: true,
    counts: { plugin: 9949, fork: 26137, package: 0 },
    coverage: [{
      source: 'github-rest/fork-network', status: 'incomplete',
      discovered_count: 26137, descendant_count: 112, reported_count_after: 26099
    }]
  });
  assert.match(c.renderVals().catalogSourceLabel, /26,137 visible · root reports 26,099 direct/);
});

test('permanent static deployment preserves the launcher security headers', () => {
  const headers = Object.fromEntries(vercel.headers[0].headers.map(item => [item.key, item.value]));
  assert.match(headers['Content-Security-Policy'], /script-src 'self'/);
  assert.match(headers['Content-Security-Policy'], /frame-ancestors 'none'/);
  assert.equal(headers['X-Content-Type-Options'], 'nosniff');
  assert.equal(headers['X-Frame-Options'], 'DENY');
  assert.equal(headers['Referrer-Policy'], 'no-referrer');
});

test('imported research evidence marks only bounded hidden-gem candidates', async () => {
  const c = instance();
  const plugin = snapshot.supplemental_entries[0];
  const report = {
    policy: 'dsh-forge.hidden-gems/v1', artifact_id: plugin.artifact_id,
    score: 94, rank: 7, visibility: 'hidden', confidence: 'metadata-only',
    candidate: true, capabilities: ['orchestration'],
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
  assert.match(detail.detailEvidenceText, /capability/);
  assert.match(detail.sortExplanation, /metadata only, not a security verdict/);
});

test('a plugin-only imported store retains the embedded fork snapshot', () => {
  const c = instance();
  c.renderVals().repoTypes.find(type => type.id === 'fork').select();
  connectedStore(c, { available: true, artifact_count: 9949, counts: { plugin: 9949, fork: 0, package: 0 } });

  const values = c.renderVals();
  assert.equal(values.storeActive, false);
  assert.equal(values.results.length, 10);
  assert.equal(values.catalogCountLabel, '9,949 plugins · 10 forks');
  assert.match(values.catalogSourceLabel, /no imported fork records/);
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
  c.renderVals().repoTypes.find(f => f.id === 'plugin').select();
  connectedStore(c);
  c.setState({ query: 'agent teams', catalogSort: 'stars', catalogScope: 'featured', knownLicenseOnly: true });
  await c.refreshCatalog();

  const sent = requests.at(-1);
  assert.equal(sent.get('q'), 'agent teams');
  assert.equal(sent.get('type'), 'plugin');
  assert.equal(sent.get('sort'), 'stars');
  assert.equal(sent.get('featured'), '1');
  assert.equal(sent.get('licensed'), '1');
  assert.equal(sent.get('cursor'), null);

  const before = c.renderVals().results.length;
  await c.renderVals().loadMore();
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
  assert.equal(values.storeActive, true, 'an error must not silently swap corpora');
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

test('front page installs only curator-certified recipes through the sandbox transaction', async () => {
  const c = instance();
  const saved = {
    id: 'version_123456789abc', path: '~/dsh', state: 'ready', tree_ids: ['tree_123456789abc'],
    primary_tree: { id: 'tree_123456789abc', version: '0.1.2-rc.1' }
  };
  c.applyStatus({
    trees: [], cells: [], saved_versions: [saved], package_installations: [],
    trusted_package_recipes: [{
      slug: 'memory-lab', name: 'Memory Lab', version: '1.0.0', component_count: 2,
      configured: true, certified: true, reviewer: 'Release curator'
    }],
    suggested_port: 3100, coverage_gaps: [], credentials: [], sandbox: { ready: true }
  });
  let request;
  c.api = async (url, options) => {
    request = { url, body: JSON.parse(options.body) };
    return { state: 'ready' };
  };
  c.refreshStatus = async () => {};

  const values = c.renderVals();
  assert.equal(values.certifiedPackages.length, 1);
  assert.equal(values.certifiedPackages[0].disabled, false);
  assert.equal(values.certifiedPackages[0].reviewLabel, 'Reviewed by Release curator');
  await values.certifiedPackages[0].install();
  assert.deepEqual(request, {
    url: '/api/v1/packages/install',
    body: { package_slug: 'memory-lab', version_id: saved.id, profile: 'web' }
  });
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
  c.renderVals().goCatalog();
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
