"use strict";

window.__dcPrecompiledLogicFactories = window.__dcPrecompiledLogicFactories || {};
window.__dcPrecompiledLogicFactories.$root = function precompileRootLogic(DCLogic) {
const OK = 'oklch(0.74 0.15 155)';
const WARN = 'oklch(0.8 0.14 85)';
const BAD = 'oklch(0.7 0.16 25)';
const BLUE = 'oklch(0.74 0.12 235)';
const MUTED = 'oklch(0.62 0.01 255)';
const TXT = 'oklch(0.86 0.01 255)';
const BORDER = 'oklch(0.31 0.012 255)';
const SELB = 'oklch(0.58 0.11 235)';

const PINNED_RELEASES = [
  { id: 'official-alpha-3', name: 'Harness alpha.3', version: '0.1.2-alpha.3', tag: 'dsh-v0.1.2-alpha.3', commit: 'dd6322d',
    releaseUrl: 'https://github.com/deepseek-ai/deepseek-harness/releases/tag/dsh-v0.1.2-alpha.3' },
  { id: 'official-alpha-2', name: 'Harness alpha.2', version: '0.1.2-alpha.2', tag: 'dsh-v0.1.2-alpha.2', commit: '0a53fb5',
    releaseUrl: 'https://github.com/deepseek-ai/deepseek-harness/releases/tag/dsh-v0.1.2-alpha.2' }
];

const PREVIEW_TREES = PINNED_RELEASES.map(pin => ({
  id: pin.id, name: pin.name, kind: 'official release', version: pin.version, path: 'Install this exact official release to enable Launch',
  git: { branch: pin.tag, sha: pin.commit, dirty: false }, trust: 'readonly', launchability: 'preview-only', short: pin.id,
  exe: 'not detected', node: 'not detected'
}));

// CATALOG_SNAPSHOT_START
const CATALOG_SNAPSHOT = {
  "schema_version": 1,
  "snapshot_id": "manual-top10-2026-08-31T201428Z",
  "fetched_at": "2026-08-31T20:14:28Z",
  "completed_at": "2026-08-31T20:15:24+00:00",
  "upstream": "deepseek-ai/deepseek-harness",
  "source_url": "https://api.github.com/repos/deepseek-ai/deepseek-harness/forks?sort=stargazers&per_page=10&page=1",
  "selection": {
    "method": "github_forks_endpoint",
    "sort": "stargazers",
    "limit": 10,
    "ties": "GitHub response order",
    "archived_included": true
  },
  "provenance": {
    "method": "one_shot_github_rest",
    "response_headers": {
      "ETag": "W/\"0235732631804188bd89dd385796240575b6177edbb9160880030f427e9116db\"",
      "Date": "Mon, 31 Aug 2026 20:14:40 GMT",
      "Link": "\u003chttps://api.github.com/repositories/1333065091/forks?sort=stargazers&per_page=10&page=2>; rel=\"next\", \u003chttps://api.github.com/repositories/1333065091/forks?sort=stargazers&per_page=10&page=2389>; rel=\"last\""
    },
    "signature_status": "unsigned_development_seed",
    "note": "Metadata calls are sequential snapshots, not one atomic view of GitHub."
  },
  "entries": [
    {
      "artifact_id": "github:1333146268",
      "github_id": 1333146268,
      "node_id": "R_kgDOT3YynA",
      "full_name": "salathleizhang/deepseek-harness-desktop",
      "owner": "salathleizhang",
      "name": "deepseek-harness-desktop",
      "artifact_type": "fork",
      "source": "github",
      "repository_url": "https://github.com/salathleizhang/deepseek-harness-desktop",
      "description": "Native desktop app for DeepSeek Harness — an Electron shell that runs the harness locally and hosts the official Web GUI unchanged.",
      "description_origin": "author_declared",
      "topics": [
        "deepseek",
        "deepseek-harness",
        "dsh-plugin"
      ],
      "language": "TypeScript",
      "github_stars": 142,
      "seed_rank": 1,
      "forks_count": 7,
      "pushed_at": "2026-08-29T13:06:16Z",
      "archived": false,
      "default_branch": "master",
      "head_sha": "fe8e3f8d5e190e756c29c46036b4d879cf7bc754",
      "parent_repository": "deepseek-ai/deepseek-harness",
      "source_repository": "deepseek-ai/deepseek-harness",
      "license": {
        "spdx": "MIT",
        "status": "github_reported"
      },
      "compatibility": {
        "declared_dsh_range": null,
        "observed_base": null
      },
      "analysis_status": "not_analyzed",
      "verification": {
        "metadata_only": true,
        "executed": false,
        "security_verified": false
      }
    },
    {
      "artifact_id": "github:1333812618",
      "github_id": 1333812618,
      "node_id": "R_kgDOT4Bdig",
      "full_name": "flaqai/open-deepseek-harness-desktop",
      "owner": "flaqai",
      "name": "open-deepseek-harness-desktop",
      "artifact_type": "fork",
      "source": "github",
      "repository_url": "https://github.com/flaqai/open-deepseek-harness-desktop",
      "description": "An easy-to-use, reliable DeepSeek Harness desktop app with robust plugin management, process orchestration, dynamic tool discovery, and a selection of useful pre-installed plugins that can be removed at any time.",
      "description_origin": "author_declared",
      "topics": [
        "cordis",
        "cordis-plugin",
        "deepseek",
        "deepseek-harness",
        "deepseek-harness-desktop",
        "deepseek-harness-guide",
        "deepseek-harness-plugin",
        "desktop-app",
        "dsh",
        "dsh-plugin",
        "dsh-plugin-desktop",
        "electron",
        "flaq-skills",
        "flaqai"
      ],
      "language": "TypeScript",
      "github_stars": 106,
      "seed_rank": 2,
      "forks_count": 4,
      "pushed_at": "2026-08-31T11:22:17Z",
      "archived": false,
      "default_branch": "master",
      "head_sha": "75d44a09b7d2db3161f11352225d5443e2d841e1",
      "parent_repository": "deepseek-ai/deepseek-harness",
      "source_repository": "deepseek-ai/deepseek-harness",
      "license": {
        "spdx": "MIT",
        "status": "github_reported"
      },
      "compatibility": {
        "declared_dsh_range": null,
        "observed_base": null
      },
      "analysis_status": "not_analyzed",
      "verification": {
        "metadata_only": true,
        "executed": false,
        "security_verified": false
      }
    },
    {
      "artifact_id": "github:1338052790",
      "github_id": 1338052790,
      "node_id": "R_kgDOT8EQtg",
      "full_name": "Foreverlearners-cpu/deepseek-harness-multi-user",
      "owner": "Foreverlearners-cpu",
      "name": "deepseek-harness-multi-user",
      "artifact_type": "fork",
      "source": "github",
      "repository_url": "https://github.com/Foreverlearners-cpu/deepseek-harness-multi-user",
      "description": "Building a multi-user DeepSeek Harness with Kafka, MySQL, Redis, Elasticsearch and CDC infrastructure, authentication, authorization, and a web management UI.",
      "description_origin": "author_declared",
      "topics": [
        "deepseek-harness",
        "dsh",
        "dsh-plugin"
      ],
      "language": "TypeScript",
      "github_stars": 65,
      "seed_rank": 3,
      "forks_count": 9,
      "pushed_at": "2026-08-27T06:45:49Z",
      "archived": false,
      "default_branch": "master",
      "head_sha": "dd44278a10c80aed3003aa0b3e087da48e90c1b1",
      "parent_repository": "deepseek-ai/deepseek-harness",
      "source_repository": "deepseek-ai/deepseek-harness",
      "license": {
        "spdx": "MIT",
        "status": "github_reported"
      },
      "compatibility": {
        "declared_dsh_range": null,
        "observed_base": null
      },
      "analysis_status": "not_analyzed",
      "verification": {
        "metadata_only": true,
        "executed": false,
        "security_verified": false
      }
    },
    {
      "artifact_id": "github:1333142942",
      "github_id": 1333142942,
      "node_id": "R_kgDOT3Ylng",
      "full_name": "Sakana-yuyu/deepseek-harness-desktop",
      "owner": "Sakana-yuyu",
      "name": "deepseek-harness-desktop",
      "artifact_type": "fork",
      "source": "github",
      "repository_url": "https://github.com/Sakana-yuyu/deepseek-harness-desktop",
      "description": "Rust构建的客户端，体积更小，更方便，Mac，win，linux已完成。",
      "description_origin": "author_declared",
      "topics": [],
      "language": "TypeScript",
      "github_stars": 45,
      "seed_rank": 4,
      "forks_count": 3,
      "pushed_at": "2026-08-30T05:25:18Z",
      "archived": false,
      "default_branch": "master",
      "head_sha": "ceab3e266a92588c4430eedcfd45d93de03021a3",
      "parent_repository": "deepseek-ai/deepseek-harness",
      "source_repository": "deepseek-ai/deepseek-harness",
      "license": {
        "spdx": "MIT",
        "status": "github_reported"
      },
      "compatibility": {
        "declared_dsh_range": null,
        "observed_base": null
      },
      "analysis_status": "not_analyzed",
      "verification": {
        "metadata_only": true,
        "executed": false,
        "security_verified": false
      }
    },
    {
      "artifact_id": "github:1334769528",
      "github_id": 1334769528,
      "node_id": "R_kgDOT473eA",
      "full_name": "Ajwyunsx/deepseek-harness-mobile",
      "owner": "Ajwyunsx",
      "name": "deepseek-harness-mobile",
      "artifact_type": "fork",
      "source": "github",
      "repository_url": "https://github.com/Ajwyunsx/deepseek-harness-mobile",
      "description": "DeepSeek Harness 的 Android 手机版：proot 容器 + WebView 移动适配 | Android port of DeepSeek Harness — proot Ubuntu container running dsh web with a mobile-optimized WebView UI",
      "description_origin": "author_declared",
      "topics": [],
      "language": "TypeScript",
      "github_stars": 44,
      "seed_rank": 5,
      "forks_count": 3,
      "pushed_at": "2026-08-21T18:17:37Z",
      "archived": false,
      "default_branch": "master",
      "head_sha": "ba10e4f97647af3b3b539bae9d0ac286c8df7787",
      "parent_repository": "deepseek-ai/deepseek-harness",
      "source_repository": "deepseek-ai/deepseek-harness",
      "license": {
        "spdx": "MIT",
        "status": "github_reported"
      },
      "compatibility": {
        "declared_dsh_range": null,
        "observed_base": null
      },
      "analysis_status": "not_analyzed",
      "verification": {
        "metadata_only": true,
        "executed": false,
        "security_verified": false
      }
    },
    {
      "artifact_id": "github:1333692732",
      "github_id": 1333692732,
      "node_id": "R_kgDOT36JPA",
      "full_name": "sdkwork-ai/deepseek-harness-desktop",
      "owner": "sdkwork-ai",
      "name": "deepseek-harness-desktop",
      "artifact_type": "fork",
      "source": "github",
      "repository_url": "https://github.com/sdkwork-ai/deepseek-harness-desktop",
      "description": "DeepSeek Harness: Everything is a Plugin.",
      "description_origin": "author_declared",
      "topics": [],
      "language": "TypeScript",
      "github_stars": 28,
      "seed_rank": 6,
      "forks_count": 4,
      "pushed_at": "2026-08-21T17:06:57Z",
      "archived": false,
      "default_branch": "master",
      "head_sha": "312b82f5c92710097f608c951cfbb267c73cbc59",
      "parent_repository": "deepseek-ai/deepseek-harness",
      "source_repository": "deepseek-ai/deepseek-harness",
      "license": {
        "spdx": "MIT",
        "status": "github_reported"
      },
      "compatibility": {
        "declared_dsh_range": null,
        "observed_base": null
      },
      "analysis_status": "not_analyzed",
      "verification": {
        "metadata_only": true,
        "executed": false,
        "security_verified": false
      }
    },
    {
      "artifact_id": "github:1334653579",
      "github_id": 1334653579,
      "node_id": "R_kgDOT40yiw",
      "full_name": "rpmalouin/deepseek-harness",
      "owner": "rpmalouin",
      "name": "deepseek-harness",
      "artifact_type": "fork",
      "source": "github",
      "repository_url": "https://github.com/rpmalouin/deepseek-harness",
      "description": "DeepSeek Harness: Everything is a Plugin.",
      "description_origin": "author_declared",
      "topics": [],
      "language": "TypeScript",
      "github_stars": 20,
      "seed_rank": 7,
      "forks_count": 2,
      "pushed_at": "2026-08-29T21:58:09Z",
      "archived": false,
      "default_branch": "master",
      "head_sha": "b98d9a7c60f19084587b4358b1e30615bf3b0353",
      "parent_repository": "deepseek-ai/deepseek-harness",
      "source_repository": "deepseek-ai/deepseek-harness",
      "license": {
        "spdx": "MIT",
        "status": "github_reported"
      },
      "compatibility": {
        "declared_dsh_range": null,
        "observed_base": null
      },
      "analysis_status": "not_analyzed",
      "verification": {
        "metadata_only": true,
        "executed": false,
        "security_verified": false
      }
    },
    {
      "artifact_id": "github:1333729559",
      "github_id": 1333729559,
      "node_id": "R_kgDOT38ZFw",
      "full_name": "cipherTing/deepseek-harness-desktop-pure",
      "owner": "cipherTing",
      "name": "deepseek-harness-desktop-pure",
      "artifact_type": "fork",
      "source": "github",
      "repository_url": "https://github.com/cipherTing/deepseek-harness-desktop-pure",
      "description": "DeepSeek Harness桌面端",
      "description_origin": "author_declared",
      "topics": [],
      "language": "TypeScript",
      "github_stars": 20,
      "seed_rank": 8,
      "forks_count": 0,
      "pushed_at": "2026-08-31T10:35:38Z",
      "archived": false,
      "default_branch": "master",
      "head_sha": "384bd4d432308cb2a69bbc723905f7bca1186d7f",
      "parent_repository": "deepseek-ai/deepseek-harness",
      "source_repository": "deepseek-ai/deepseek-harness",
      "license": {
        "spdx": "MIT",
        "status": "github_reported"
      },
      "compatibility": {
        "declared_dsh_range": null,
        "observed_base": null
      },
      "analysis_status": "not_analyzed",
      "verification": {
        "metadata_only": true,
        "executed": false,
        "security_verified": false
      }
    },
    {
      "artifact_id": "github:1337824038",
      "github_id": 1337824038,
      "node_id": "R_kgDOT72TJg",
      "full_name": "Akunimal/free-code-deepseek-harness",
      "owner": "Akunimal",
      "name": "free-code-deepseek-harness",
      "artifact_type": "fork",
      "source": "github",
      "repository_url": "https://github.com/Akunimal/free-code-deepseek-harness",
      "description": "Portable cross-platform GUI fork of DeepSeek Harness for almost-free OpenCode vibecoding.",
      "description_origin": "author_declared",
      "topics": [],
      "language": "TypeScript",
      "github_stars": 16,
      "seed_rank": 9,
      "forks_count": 1,
      "pushed_at": "2026-08-30T14:40:10Z",
      "archived": false,
      "default_branch": "main",
      "head_sha": "69455269ed808aca95461056e1f53b559e742498",
      "parent_repository": "deepseek-ai/deepseek-harness",
      "source_repository": "deepseek-ai/deepseek-harness",
      "license": {
        "spdx": "MIT",
        "status": "github_reported"
      },
      "compatibility": {
        "declared_dsh_range": null,
        "observed_base": null
      },
      "analysis_status": "not_analyzed",
      "verification": {
        "metadata_only": true,
        "executed": false,
        "security_verified": false
      }
    },
    {
      "artifact_id": "github:1333909542",
      "github_id": 1333909542,
      "node_id": "R_kgDOT4HYJg",
      "full_name": "G36maid/deepseek-harness",
      "owner": "G36maid",
      "name": "deepseek-harness",
      "artifact_type": "fork",
      "source": "github",
      "repository_url": "https://github.com/G36maid/deepseek-harness",
      "description": "DeepSeek Harness 繁體中文版 (zh-TW) — Everything is a Plugin.",
      "description_origin": "author_declared",
      "topics": [
        "ai-agents",
        "chinese",
        "deepseek-harness",
        "dsh-plugin",
        "taiwan",
        "traditional-chinese",
        "translation",
        "zh-tw"
      ],
      "language": "TypeScript",
      "github_stars": 15,
      "seed_rank": 10,
      "forks_count": 0,
      "pushed_at": "2026-08-17T07:26:14Z",
      "archived": false,
      "default_branch": "master",
      "head_sha": "6cff104734bbcbe1cebb292fafaef83e0b39d090",
      "parent_repository": "deepseek-ai/deepseek-harness",
      "source_repository": "deepseek-ai/deepseek-harness",
      "license": {
        "spdx": "MIT",
        "status": "github_reported"
      },
      "compatibility": {
        "declared_dsh_range": null,
        "observed_base": null
      },
      "analysis_status": "not_analyzed",
      "verification": {
        "metadata_only": true,
        "executed": false,
        "security_verified": false
      }
    }
  ],
  "supplemental_entries": []
};
// CATALOG_SNAPSHOT_END

function catalogDate(value) {
  if (!value || !Number.isFinite(Date.parse(value))) return 'Unknown';
  return new Date(value).toISOString().slice(0, 10);
}

const CATALOG = [...CATALOG_SNAPSHOT.entries, ...(CATALOG_SNAPSHOT.supplemental_entries || [])].map(a => ({
  ...a,
  id: a.artifact_id, slug: a.full_name, type: a.artifact_type,
  url: a.repository_url, base: a.head_sha || 'Not captured',
  terms: (a.topics || []).join(' '), language: a.language || 'Not reported',
  licenseOk: !!a.license.spdx, licenseLabel: a.license.spdx || 'License unknown',
  starsLabel: Number.isInteger(a.github_stars) ? a.github_stars.toLocaleString('en-US') : '—',
  activity: 'Pushed ' + catalogDate(a.pushed_at),
  rankLabel: a.seed_rank ? '#' + String(a.seed_rank).padStart(2, '0') : '+',
  archivedLabel: a.archived ? 'Archived' : '',
  commitUrl: a.head_sha ? a.repository_url + '/tree/' + a.head_sha : a.repository_url,
}));

const COLUMNS = ['Cell / state', 'Tree', 'Surface', 'URL', 'Process identity', 'Uptime', 'Home / isolation', 'Workspace', 'Trust', 'Health', 'Actions'];

function pad(n) { return n < 10 ? '0' + n : '' + n; }

class Component extends DCLogic {
  constructor(props) {
    super(props);
    this.state = {
      view: typeof window !== 'undefined' && window.location.hash === '#public-repos' ? 'catalog' : 'launch',
      treeId: PREVIEW_TREES[0].id,
      trees: PREVIEW_TREES,
      surface: 'web',
      profile: 'tui-min',
      task: '',
      port: String(props.defaultPort ?? 3100),
      openBrowser: true,
      homeMode: 'fresh',
      cloneSource: '~/.dsh',
      excludeSessions: true,
      workspace: 'none',
      advancedOpen: false,
      preview: null,
      logCell: null,
      query: '',
      catalogType: 'all',
      catalogSort: 'stars',
      knownLicenseOnly: false,
      artifactId: CATALOG[0] ? CATALOG[0].id : null,
      toast: '',
      cells: [],
      sidecarConnected: false,
      statusLoaded: false,
      suggestedPort: Number(props.defaultPort ?? 3100),
      coverageGaps: [],
      credentials: [],
      previewData: null,
      logLines: [],
      selectedCell: null,
      inspectorTab: 'logs',
      artifacts: []
    };
  }

  componentDidMount() {
    this.timer = setInterval(() => this.forceUpdate(), 1000);
    this.statusTimer = setInterval(() => this.refreshStatus(true), 3000);
    this.inspectorTimer = setInterval(() => {
      const cell = this.state.view === 'launch' && this.state.cells.find(item => item.id === this.state.selectedCell);
      if (cell) this.inspectCell(cell, this.state.inspectorTab);
    }, 3000);
    this.hashListener = () => this.setState({ view: window.location.hash === '#public-repos' ? 'catalog' : 'launch' });
    window.addEventListener('hashchange', this.hashListener);
    this.refreshStatus(true);
  }
  componentWillUnmount() {
    clearInterval(this.timer);
    clearInterval(this.statusTimer);
    clearInterval(this.inspectorTimer);
    if (this.toastTimer) clearTimeout(this.toastTimer);
    if (this.hashListener) window.removeEventListener('hashchange', this.hashListener);
  }

  navigate(view) {
    this.setState({ view });
    if (typeof window !== 'undefined') window.location.hash = view === 'catalog' ? 'public-repos' : 'launch';
  }

  async copyRepositoryRef(detail) {
    const value = detail.url + (detail.head_sha ? '/tree/' + detail.head_sha : '');
    try {
      if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error('Clipboard API unavailable');
      await navigator.clipboard.writeText(value);
      this.flash('Copied repository reference');
    } catch {
      const field = document.createElement('textarea');
      field.value = value;
      field.setAttribute('readonly', '');
      field.style.position = 'fixed'; field.style.opacity = '0';
      const previousFocus = document.activeElement;
      document.body.appendChild(field); field.select();
      let copied = false;
      try { copied = document.execCommand('copy'); } catch {}
      field.remove();
      if (previousFocus && previousFocus.focus) previousFocus.focus();
      this.flash(copied ? 'Copied repository reference' : 'Clipboard unavailable. Use the captured commit link.');
    }
  }

  flash(msg) {
    this.setState({ toast: msg });
    if (this.toastTimer) clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => this.setState({ toast: '' }), 2600);
  }

  tree(id) {
    return this.state.trees.find(t => t.id === id) || this.state.trees[0] || {
      id: '', name: 'No DSH tree detected', short: 'dsh', kind: '—', version: '—', path: 'Configure a scan root to begin',
      exe: '—', node: '—', git: null, trust: 'readonly', launchability: 'not-detected'
    };
  }

  async api(path, options = {}) {
    const response = await fetch(path, {
      credentials: 'same-origin',
      ...options,
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) }
    });
    let payload = {};
    try { payload = await response.json(); } catch {}
    if (!response.ok) throw new Error(payload.error || ('Launcher request failed (' + response.status + ')'));
    return payload;
  }

  applyStatus(status) {
    const trees = Array.isArray(status.trees) ? status.trees : [];
    const current = trees.some(t => t.id === this.state.treeId) ? this.state.treeId : (trees[0] ? trees[0].id : '');
    const cells = Array.isArray(status.cells) ? status.cells : [];
    const selectedCell = cells.some(c => c.id === this.state.selectedCell) ? this.state.selectedCell : (cells[0] ? cells[0].id : null);
    this.setState({
      sidecarConnected: true, statusLoaded: true, trees, treeId: current,
      cells, selectedCell,
      suggestedPort: status.suggested_port || this.state.suggestedPort,
      coverageGaps: Array.isArray(status.coverage_gaps) ? status.coverage_gaps : [],
      credentials: Array.isArray(status.credentials) ? status.credentials : []
    });
  }

  async refreshStatus(silent = false) {
    if (typeof fetch === 'undefined' || typeof location === 'undefined' || !/^https?:$/.test(location.protocol)) {
      this.setState({ statusLoaded: true, sidecarConnected: false });
      return;
    }
    try {
      this.applyStatus(await this.api('/api/v1/status'));
    } catch (error) {
      this.setState({ statusLoaded: true, sidecarConnected: false, cells: [] });
      if (!silent) this.flash(error.message);
    }
  }

  launchSpec() {
    const s = this.state;
    return {
      tree_id: s.treeId,
      surface: s.surface,
      profile: s.profile || 'tui-min',
      task: s.task,
      port: s.surface === 'headless' ? null : Number(s.port),
      open_browser: s.openBrowser,
      home_mode: s.homeMode,
      clone_source: s.cloneSource,
      workspace: s.workspace,
      resources: { cpu: 'host shared', gpu: 'inherit allocation', ram: 'host shared' }
    };
  }

  async previewLaunch() {
    try {
      const previewData = await this.api('/api/v1/launches/preview', { method: 'POST', body: JSON.stringify(this.launchSpec()) });
      this.setState({ preview: 'launch', previewData });
    } catch (error) { this.flash(error.message); }
  }

  uptime(started) {
    const s = Math.max(0, Math.floor((Date.now() - started) / 1000));
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
    return h > 0 ? h + 'h ' + pad(m) + 'm ' + pad(s % 60) + 's' : m + 'm ' + pad(s % 60) + 's';
  }

  freePort() {
    const used = new Set(this.state.cells.map(c => c.port).filter(Boolean).concat([3080, 3090]));
    let p = Number(this.state.suggestedPort) || 3100;
    while (used.has(p)) p++;
    return p;
  }

  async startCell() {
    const pendingWindow = this.state.openBrowser && this.state.surface === 'web' ? window.open('about:blank', '_blank') : null;
    try {
      const cell = await this.api('/api/v1/cells', { method: 'POST', body: JSON.stringify(this.launchSpec()) });
      this.setState({ preview: null, previewData: null });
      await this.refreshStatus(true);
      this.setState({ port: String(this.freePort()) });
      this.flash('cell ' + cell.name + ' started in its own process group');
      if (pendingWindow) this.openCell(cell, pendingWindow);
    } catch (error) {
      if (pendingWindow) pendingWindow.close();
      this.flash(error.message);
    }
  }

  async quickLaunch(version) {
    if (!this.state.sidecarConnected) return this.flash('Start scripts/serve.py to launch a real cell');
    if (!version.treeId) return this.flash('That exact official release is not configured. Start Forge with its install path as a scan root.');
    try {
      const cell = await this.api('/api/v1/cells', { method: 'POST', body: JSON.stringify({
        tree_id: version.treeId, surface: 'web', port: 'auto', open_browser: false,
        home_mode: 'fresh', workspace: 'managed',
        resources: { cpu: 'host shared', gpu: 'inherit allocation', ram: 'host shared' }
      }) });
      await this.refreshStatus(true);
      this.setState({ selectedCell: cell.id, inspectorTab: 'logs' });
      await this.inspectCell(cell, 'logs');
      this.flash('launched ' + version.version + ' on automatic port ' + cell.port);
    } catch (error) { this.flash(error.message); }
  }

  async cellAction(cell, action) {
    try {
      const result = await this.api('/api/v1/cells/' + encodeURIComponent(cell.id) + '/' + action, { method: 'POST', body: '{}' });
      await this.refreshStatus(true);
      if (action === 'restart' || action === 'clone') this.setState({ selectedCell: result.id, inspectorTab: 'logs' });
      this.flash(action + ' complete · ' + cell.name);
    } catch (error) { this.flash(error.message); }
  }

  async copyCellUrl(cell) {
    try {
      const payload = await this.api('/api/v1/cells/' + encodeURIComponent(cell.id) + '/open-url');
      await navigator.clipboard.writeText(payload.url);
      this.flash('copied authenticated DSH Web URL');
    } catch (error) { this.flash(error.message || 'clipboard unavailable'); }
  }

  async openCell(cell, existingWindow = null) {
    const target = existingWindow || window.open('about:blank', '_blank');
    for (let attempt = 0; attempt < 30; attempt++) {
      try {
        const payload = await this.api('/api/v1/cells/' + encodeURIComponent(cell.id) + '/open-url');
        if (target) target.location.replace(payload.url);
        return;
      } catch {
        await new Promise(resolve => setTimeout(resolve, 500));
      }
    }
    if (target) target.close();
    this.flash('Authenticated DSH Web URL is not ready; open logs for startup details');
  }

  async openLogs(cell) {
    try {
      const payload = await this.api('/api/v1/cells/' + encodeURIComponent(cell.id) + '/logs');
      this.setState({ logCell: cell.id, selectedCell: cell.id, inspectorTab: 'logs', logLines: payload.lines || [] });
    } catch (error) { this.flash(error.message); }
  }

  async inspectCell(cell, tab = 'logs') {
    this.setState({ selectedCell: cell.id, inspectorTab: tab });
    try {
      const [logs, artifacts] = await Promise.all([
        this.api('/api/v1/cells/' + encodeURIComponent(cell.id) + '/logs'),
        this.api('/api/v1/cells/' + encodeURIComponent(cell.id) + '/artifacts')
      ]);
      this.setState({ logCell: cell.id, logLines: logs.lines || [], artifacts: artifacts.artifacts || [] });
    } catch (error) { this.flash(error.message); }
  }

  renderVals() {
    const s = this.state;
    const catalogEnabled = this.props.catalogEnabled ?? true;
    const t = this.tree(s.treeId);
    const runnable = s.sidecarConnected && !!t.id && t.trust !== 'foreign' && t.launchability === 'ready';
    const needsBuild = t.launchability === 'needs-build';
    const portNum = parseInt(s.port, 10);
    const occupyingCell = s.cells.find(c => c.port === portNum);
    const isSystem = portNum === 3080 || portNum === 3090;
    const leaseHeld = s.homeMode === 'exclusive' && s.cells.some(c => c.isolation === 'exclusive persistent' && c.state !== 'stopped');
    const confirm = this.props.confirmBeforeLaunch ?? true;
    const versions = PINNED_RELEASES.map(pin => {
      const detected = s.trees.find(tr => tr.version === pin.version || (tr.git && String(tr.git.sha || '').startsWith(pin.commit)));
      const runnablePin = !!detected && s.sidecarConnected && detected.trust !== 'foreign' && detected.launchability === 'ready';
      return {
        ...pin,
        treeId: detected && detected.id,
        installPath: detected ? detected.path : 'Exact installation not detected',
        status: runnablePin ? 'ready' : (s.sidecarConnected ? 'not installed' : 'preview pin'),
        statusColor: runnablePin ? OK : WARN,
        buttonLabel: runnablePin ? 'Launch cell' : (s.sidecarConnected ? 'Add installation' : 'Preview only'),
        disabled: !runnablePin,
        buttonCursor: runnablePin ? 'pointer' : 'not-allowed',
        buttonBg: runnablePin ? 'oklch(0.34 0.08 155)' : 'oklch(0.25 0.01 255)',
        buttonBorder: runnablePin ? 'oklch(0.52 0.13 155)' : BORDER,
        launch: () => this.quickLaunch({ ...pin, treeId: detected && detected.id })
      };
    });

    let portNote, portNoteFg = MUTED, portNoteBorder = BORDER, portNoteBg = 'transparent';
    if (s.surface === 'headless') { portNote = 'headless surface binds no HTTP port'; }
    else if (occupyingCell) { portNote = portNum + ' occupied by managed cell ' + occupyingCell.name + ' — stop it or use ' + this.freePort(); portNoteFg = WARN; portNoteBorder = 'oklch(0.42 0.09 85)'; portNoteBg = 'oklch(0.245 0.03 85)'; }
    else if (isSystem) { portNote = portNum + ' reserved (' + (portNum === 3080 ? 'operator DSH' : 'this sidecar') + ') — never replaced implicitly'; portNoteFg = BAD; portNoteBorder = 'oklch(0.42 0.1 25)'; portNoteBg = 'oklch(0.25 0.04 25)'; }
    else if (!s.sidecarConnected) { portNote = 'Portable preview only · start scripts/serve.py to validate and launch'; portNoteFg = WARN; }
    else { portNote = portNum + ' will be checked on loopback immediately before spawn'; portNoteFg = OK; }

    const homeModes = [
      { id: 'exclusive', label: 'Exclusive persistent home', tag: 'writer lease', detail: '~/.dsh — second launch is rejected or cloned' },
      { id: 'fresh', label: 'Fresh empty home', tag: 'managed', detail: 'minimum directory structure in a launcher-managed cell dir' },
      { id: 'clone', label: 'Cloned home', tag: 'snapshot', detail: 'copy a home template; locks, PIDs, sockets and caches excluded' }
    ].map(h => ({
      ...h,
      border: s.homeMode === h.id ? SELB : BORDER,
      bg: s.homeMode === h.id ? 'oklch(0.255 0.02 255)' : 'transparent',
      dot: s.homeMode === h.id ? SELB : 'transparent',
      dotBorder: s.homeMode === h.id ? SELB : 'oklch(0.4 0.012 255)',
      select: () => this.setState({ homeMode: h.id })
    }));

    const cells = s.cells.map(c => {
      const ct = this.tree(c.treeId);
      const running = c.process === 'alive';
      const stateColor = c.agent_state === 'working' ? OK : (c.agent_state === 'blocked' ? WARN : (c.agent_state === 'exited' ? BAD : BLUE));
      const processAlive = c.process === 'alive';
      const httpOk = /^[1-4]\d\d$/.test(String(c.http));
      const health = [
        { label: 'process ' + (c.process || c.state), color: processAlive ? OK : MUTED },
        { label: c.http === 'n/a' ? 'http n/a' : (httpOk ? 'http ' + c.http : 'http ' + (c.http || 'pending')), color: httpOk ? OK : (c.http === 'n/a' ? MUTED : WARN) },
        { label: 'loader ' + (c.loader || 'not observed'), color: c.loader === 'settled' ? OK : MUTED }
      ];
      const act = (label, on, enabled) => ({
        label, run: enabled ? on : (() => {}), disabled: !enabled,
        border: enabled ? 'oklch(0.36 0.012 255)' : 'oklch(0.28 0.012 255)',
        color: enabled ? TXT : 'oklch(0.48 0.01 255)', cursor: enabled ? 'pointer' : 'not-allowed'
      });
      return {
        ...c,
        treeName: ct.name,
        treeIdentity: (c.version || ct.version || 'unknown') + ' · ' + (c.commit || (ct.git && ct.git.sha) || 'package pin'),
        workspace_isolation: c.workspace_isolation || 'legacy/shared',
        surface: c.surface, url: c.port ? '127.0.0.1:' + c.port : '—',
        uptime: this.uptime(c.started), stateColor,
        stateAnim: c.agent_state === 'working' ? 'dshpulse 1.8s ease-in-out infinite' : 'none',
        rowBg: s.selectedCell === c.id ? 'oklch(0.235 0.018 255)' : 'oklch(0.205 0.009 255)',
        cardBorder: s.selectedCell === c.id ? SELB : BORDER,
        isolationColor: c.isolation === 'exclusive persistent' ? WARN : MUTED,
        trust: ct.trust, trustColor: ct.trust === 'personal' ? OK : (ct.trust === 'readonly' ? BLUE : BAD),
        trustBorder: ct.trust === 'personal' ? 'oklch(0.42 0.1 155)' : (ct.trust === 'readonly' ? 'oklch(0.42 0.08 235)' : 'oklch(0.42 0.1 25)'),
        health,
        resourcesList: [
          { label: 'CPU', value: (c.resources && c.resources.cpu) || 'host shared' },
          { label: 'GPU', value: (c.resources && c.resources.gpu) || 'inherit allocation' },
          { label: 'RAM', value: (c.resources && c.resources.ram) || 'host shared' }
        ],
        recentLogLines: (c.recent_logs || []).map(msg => ({ msg })),
        open: () => this.openCell(c),
        stop: () => this.cellAction(c, 'stop'),
        restart: () => this.cellAction(c, 'restart'),
        clone: () => this.cellAction(c, 'clone'),
        inspect: () => this.inspectCell(c),
        openDisabled: !c.port || !running,
        stopDisabled: !processAlive,
        lifecycleDisabled: false,
        actions: [
          act('stop', () => this.cellAction(c, 'stop'), processAlive),
          act('restart', () => this.cellAction(c, 'restart'), running || c.state === 'exited' || c.state === 'stopped'),
          act('open', () => this.openCell(c), !!c.port && running),
          act('copy', () => this.copyCellUrl(c), !!c.port),
          act('logs', () => this.openLogs(c), true)
        ]
      };
    });
    const activeCell = cells.find(c => c.id === s.selectedCell) || cells[0] || null;
    const inspectorTabs = [
      { id: 'logs', label: 'Live logs' }, { id: 'prompts', label: 'Prompts' }, { id: 'artifacts', label: 'Artifacts' }
    ].map(tab => ({
      ...tab,
      bg: s.inspectorTab === tab.id ? 'oklch(0.31 0.04 235)' : 'transparent',
      color: s.inspectorTab === tab.id ? TXT : MUTED,
      select: () => activeCell ? this.inspectCell(activeCell, tab.id) : undefined
    }));

    const queryTerms = s.query.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const filtered = CATALOG.filter(a => {
      const searchable = [a.slug, a.description, a.terms, a.type, a.language, a.licenseLabel].join(' ').toLowerCase();
      return queryTerms.every(term => searchable.includes(term)) &&
        (s.catalogType === 'all' || a.type === s.catalogType) &&
        (!s.knownLicenseOnly || a.licenseOk);
    }).sort((a, b) => {
      if (s.catalogSort === 'name') return a.slug.localeCompare(b.slug);
      if (s.catalogSort === 'recent') return (Date.parse(b.pushed_at) || 0) - (Date.parse(a.pushed_at) || 0) || (a.seed_rank || 999) - (b.seed_rank || 999);
      return (b.github_stars ?? -1) - (a.github_stars ?? -1) || (a.seed_rank || 999) - (b.seed_rank || 999);
    });
    // Never keep an unrelated detail open after search/filter removes it.
    const detail = filtered.find(a => a.id === s.artifactId) || filtered[0] || {};
    const results = filtered.map(a => ({
      ...a, selected: a.id === detail.id,
      accessibleLabel: 'Inspect ' + a.slug + ', ' + a.starsLabel + ' GitHub stars',
      border: a.id === detail.id ? SELB : BORDER,
      bg: a.id === detail.id ? 'oklch(0.245 0.022 255)' : 'oklch(0.21 0.01 255)',
      select: () => this.setState({ artifactId: a.id })
    }));
    const detailRows = !detail.id ? [] : [
      { k: 'GitHub identity', v: detail.id, color: TXT },
      { k: 'Default branch', v: detail.default_branch || 'Not reported', color: TXT },
      { k: 'Captured commit', v: detail.base, color: TXT },
      { k: 'Fork source', v: detail.source_repository || 'Not reported', color: MUTED },
      { k: 'Last push', v: detail.pushed_at || 'Not reported', color: MUTED },
      { k: 'License', v: detail.licenseLabel + ' · GitHub-reported', color: detail.licenseOk ? MUTED : WARN },
      { k: 'Compatibility', v: 'Not analyzed', color: MUTED },
      { k: 'Source record', v: 'GitHub REST · author description', color: MUTED },
      { k: 'Snapshot', v: CATALOG_SNAPSHOT.fetched_at, color: MUTED },
      { k: 'Trust', v: 'Unsigned development seed', color: WARN }
    ];

    const livePreview = s.previewData;
    const previewLines = livePreview ? [
      { k: 'tree', v: livePreview.tree.path + '  (' + livePreview.tree.trust + ', ' + livePreview.tree.launchability + ')', color: TXT },
      { k: 'cwd', v: livePreview.cwd, color: TXT },
      { k: 'argv', v: livePreview.argv.join(' '), color: 'oklch(0.86 0.11 155)' },
      { k: 'home', v: 'DSH_HOME=' + livePreview.home, color: TXT },
      { k: 'env', v: (livePreview.environment_keys || []).join(', ') + ' (keys only)', color: MUTED },
      { k: 'secrets', v: (livePreview.credential_keys || []).length ? livePreview.credential_keys.join(', ') + ' = <injected>' : 'no credential keys present', color: MUTED },
      { k: 'group', v: 'new process group + session; PID and start identity recorded', color: MUTED }
    ] : [];
    const previewNotes = livePreview ? livePreview.notes : [];

    return {
      catalogEnabled,
      showLaunch: s.view === 'launch',
      showCatalog: s.view === 'catalog' && catalogEnabled,
      goLaunch: () => this.navigate('launch'),
      goCatalog: () => this.navigate('catalog'),
      modeLabel: s.sidecarConnected ? 'fleet preview' : 'portable preview',
      sidecarTitle: s.sidecarConnected ? 'Live loopback sidecar connected; mutation requests require its session cookie.' : 'Static preview; no local process controller is connected.',
      sidecarDot: s.sidecarConnected ? OK : WARN,
      sidecarAddress: typeof window !== 'undefined' && window.location.host ? window.location.host : '127.0.0.1:3090',
      sidecarState: s.sidecarConnected ? 'connected' : 'offline',
      launchTabBg: s.view === 'launch' ? 'oklch(0.3 0.02 255)' : 'transparent',
      launchTabFg: s.view === 'launch' ? 'oklch(0.95 0.01 255)' : MUTED,
      launchTabBorder: s.view === 'launch' ? 'oklch(0.42 0.03 255)' : 'transparent',
      catalogTabBg: s.view === 'catalog' ? 'oklch(0.3 0.02 255)' : 'transparent',
      catalogTabFg: s.view === 'catalog' ? 'oklch(0.95 0.01 255)' : MUTED,
      catalogTabBorder: s.view === 'catalog' ? 'oklch(0.42 0.03 255)' : 'transparent',
      cellsSummary: s.cells.length + ' cells · ' + s.cells.filter(c => c.state === 'running').length + ' running',
      snapshotAt: CATALOG_SNAPSHOT.fetched_at.slice(0, 16).replace('T', ' '),
      versions,
      pinnedCount: PINNED_RELEASES.length + ' immutable official pins',

      trees: s.trees.map(tr => {
        const sel = tr.id === s.treeId;
        const ok = tr.trust !== 'foreign';
        return {
          ...tr,
          border: sel ? SELB : BORDER,
          bg: sel ? 'oklch(0.255 0.02 255)' : 'oklch(0.205 0.009 255)',
          cursor: ok ? 'pointer' : 'not-allowed',
          opacity: ok ? '1' : '0.55',
          gitLine: tr.git ? tr.git.branch + ' @ ' + tr.git.sha + (tr.git.dirty ? ' · dirty' : ' · clean') : 'no git identity',
          trustColor: tr.trust === 'personal' ? OK : (tr.trust === 'readonly' ? BLUE : BAD),
          trustBorder: tr.trust === 'personal' ? 'oklch(0.42 0.1 155)' : (tr.trust === 'readonly' ? 'oklch(0.42 0.08 235)' : 'oklch(0.42 0.1 25)'),
          launchColor: tr.launchability === 'ready' ? OK : (tr.launchability === 'needs-build' ? WARN : BAD),
          select: () => ok ? this.setState({ treeId: tr.id }) : this.flash('foreign trees are view-only until the container backend ships')
        };
      }),
      treeCountLabel: s.sidecarConnected ? s.trees.length + ' detected · evidence-based' : s.trees.length + ' neutral preview records',
      coverageGap: s.coverageGaps.length ? s.coverageGaps.length + ' coverage gap(s): ' + s.coverageGaps.join('; ') : (s.sidecarConnected ? 'Configured roots scanned; candidate code was not executed.' : 'Preview records are illustrative and cannot be launched.'),
      surfaces: [
        { id: 'web', label: 'web' }, { id: 'headless', label: 'headless' }
      ].map(x => ({
        ...x,
        bg: s.surface === x.id ? 'oklch(0.33 0.03 255)' : 'transparent',
        fg: s.surface === x.id ? 'oklch(0.95 0.01 255)' : MUTED,
        select: () => this.setState({ surface: x.id })
      })),
      isCustomSurface: s.surface === 'custom',
      isHeadlessSurface: s.surface === 'headless',
      profiles: ['tui-min', 'web-debug', 'agent-eval'],
      profile: s.profile,
      setProfile: e => this.setState({ profile: e.target.value }),
      task: s.task,
      setTask: e => this.setState({ task: e.target.value.slice(0, 20000) }),

      port: s.port,
      setPort: e => this.setState({ port: e.target.value.replace(/[^0-9]/g, '').slice(0, 5) }),
      suggested: this.freePort(),
      suggestPort: () => this.setState({ port: String(this.freePort()) }),
      openBrowser: s.openBrowser,
      toggleOpenBrowser: () => this.setState({ openBrowser: !s.openBrowser }),
      portNote, portNoteFg, portNoteBorder, portNoteBg,

      homeModes,
      showCloneOptions: s.homeMode === 'clone',
      homeTemplates: ['~/.dsh', '~/.dsh-forge/homes/eval-a', '~/.dsh-forge/cells/clone-02'],
      cloneSource: s.cloneSource,
      setCloneSource: e => this.setState({ cloneSource: e.target.value }),
      excludeSessions: s.excludeSessions,
      toggleExcludeSessions: () => this.setState({ excludeSessions: !s.excludeSessions }),
      leaseWarning: leaseHeld,
      leaseWarningText: 'A running cell already holds the writer lease on ~/.dsh. Launching exclusive will be rejected — clone the home instead.',

      workspace: s.workspace,
      setWorkspace: e => this.setState({ workspace: e.target.value }),
      clearWorkspace: () => this.setState({ workspace: 'none' }),

      advancedOpen: s.advancedOpen,
      advancedCaret: s.advancedOpen ? '▾' : '▸',
      toggleAdvanced: () => this.setState({ advancedOpen: !s.advancedOpen }),
      advancedRows: [
        { label: 'Discovery policy', value: 'configured roots · bounded · no code execution', color: OK },
        { label: 'Process identity', value: 'PID + OS process-start identity', color: BLUE },
        { label: 'Trusted hosts', value: 'localhost, 127.0.0.1', color: MUTED },
        { label: 'Loader readiness', value: 'not observed · adapter deferred', color: MUTED },
        { label: 'Telemetry', value: 'none in launcher sidecar', color: OK },
        { label: 'Executable', value: t.exe, color: TXT },
        { label: 'Node binary', value: t.node, color: TXT }
      ],
      credentials: s.credentials.map(item => ({
        label: item.name + ' · ' + (item.present ? 'present' : 'absent'),
        color: item.present ? OK : MUTED,
        border: item.present ? 'oklch(0.42 0.1 155)' : BORDER
      })),

      needsBuild,
      buildCommands: 'Build orchestration deferred · use the tree’s documented build steps',

      primaryLabel: !s.sidecarConnected ? 'Start local sidecar to launch' : (!t.id ? 'Add a DSH tree' : (t.trust === 'foreign' ? 'View only — foreign tree' : (needsBuild ? 'Build required' : (confirm ? 'Preview launch…' : 'Start cell')))),
      primaryAction: () => {
        if (!s.sidecarConnected) return this.flash('Run python3 scripts/serve.py to connect the launcher');
        if (!runnable) return this.flash(t.trust === 'foreign' ? 'foreign trees are view-only until the container backend ships' : 'select a launch-ready detected tree');
        if (needsBuild) return this.flash('build orchestration is deferred; build this tree using its own documentation, then restart Forge');
        if (confirm) return this.previewLaunch();
        this.startCell();
      },
      launchDisabled: !runnable,
      primaryBg: runnable ? 'oklch(0.34 0.08 155)' : 'oklch(0.24 0.01 255)',
      primaryFg: runnable ? 'oklch(0.95 0.05 155)' : 'oklch(0.55 0.01 255)',
      primaryBorder: runnable ? 'oklch(0.52 0.13 155)' : BORDER,
      primaryCursor: runnable ? 'pointer' : 'not-allowed',
      launchHint: s.sidecarConnected ? 'Live local launcher. Scans never execute candidate code; only an explicitly confirmed launch starts a process.' : 'Portable preview only. No sample process is presented as real; run scripts/serve.py for local controls.',

      cellColumns: COLUMNS,
      cells,
      noCells: cells.length === 0,
      hasActiveCell: !!activeCell,
      activeCell: activeCell || {},
      inspectorTabs,
      showInspectorLogs: s.inspectorTab === 'logs',
      showInspectorPrompts: s.inspectorTab === 'prompts',
      showInspectorArtifacts: s.inspectorTab === 'artifacts',
      inspectorLogLines: s.logLines,
      inspectorArtifacts: s.artifacts.map(item => ({ ...item, sizeLabel: item.bytes.toLocaleString('en-US') + ' B' })),
      noArtifacts: s.artifacts.length === 0,

      logsOpen: !!s.logCell,
      logTitle: 'logs · ' + (s.cells.find(c => c.id === s.logCell) || { name: '' }).name,
      logLines: s.logLines,
      closeLogs: () => this.setState({ logCell: null, logLines: [] }),

      query: s.query,
      setQuery: e => this.setState({ query: e.target.value }),
      catalogSort: s.catalogSort,
      setCatalogSort: e => this.setState({ catalogSort: e.target.value }),
      knownLicenseOnly: s.knownLicenseOnly,
      toggleKnownLicense: e => this.setState({ knownLicenseOnly: !!e.target.checked }),
      repoTypes: [{ id: 'all', label: 'All repos' }, { id: 'fork', label: 'Forks' }, { id: 'plugin', label: 'Plugins' }].map(f => ({
        ...f, count: CATALOG.filter(a => f.id === 'all' || a.type === f.id).length,
        selected: s.catalogType === f.id,
        border: s.catalogType === f.id ? 'oklch(0.43 0.05 235)' : 'transparent',
        bg: s.catalogType === f.id ? 'oklch(0.29 0.035 235)' : 'transparent',
        color: s.catalogType === f.id ? 'oklch(0.88 0.035 235)' : MUTED,
        select: () => this.setState({ catalogType: f.id })
      })),
      seedCount: CATALOG_SNAPSHOT.entries.length,
      resultCount: results.length + ' of ' + CATALOG.length + ' repositories',
      sortExplanation: s.catalogSort === 'stars' ? 'GitHub stars · snapshot order for ties' : s.catalogSort === 'recent' ? 'Most recent push in this snapshot' : 'Alphabetical by owner / repository',
      results,
      noResults: results.length === 0,
      hasDetail: !!detail.id,
      detail,
      detailRows,
      detailTopics: (detail.topics || []).slice(0, 8),
      emptyTitle: s.catalogType === 'plugin' ? 'No plugins imported yet' : 'No matching repositories',
      emptyDescription: s.catalogType === 'plugin' ? 'This first snapshot contains ten forks only. Plugin records will arrive through the ingester; no sample listings are shown.' : 'Try a repository name, owner, or topic, or clear the current filters.',
      resetCatalogFilters: () => this.setState({ query: '', catalogType: 'all', knownLicenseOnly: false }),
      copyRef: () => detail.id ? this.copyRepositoryRef(detail) : undefined,

      previewOpen: !!s.preview,
      previewTitle: 'Confirm launch — exact argv and environment keys',
      previewConfirmLabel: 'Start cell',
      idemKey: 'preview-' + (s.treeId || 'no-tree') + '-' + (s.port || 'headless'),
      previewLines,
      previewNotes,
      closePreview: () => this.setState({ preview: null, previewData: null }),
      confirmPreview: () => this.startCell(),

      toast: s.toast
    };
  }
}


Component.catalog = CATALOG;
Component.catalogSnapshot = CATALOG_SNAPSHOT;
return Component;
};
