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
  "supplemental_snapshot": {
    "snapshot_id": "manual-plugin-review-2026-09-05",
    "reviewed_at": "2026-09-05T20:00:00Z",
    "selection": "Evidence-ranked candidates surfaced through the official Show Your Plugins category, repository manifests, and package-registry metadata.",
    "ranking": "Capability evidence, compatibility, maintenance, license, then security risk. GitHub stars are display metadata only.",
    "bounded_sources": [
      "https://github.com/deepseek-ai/deepseek-harness/discussions/categories/show-your-plugins",
      "https://github.com/topics/dsh-plugin",
      "https://api.deepseek1024.com/v1/plugins/search",
      "https://registry.npmjs.org"
    ],
    "verification_status": "metadata_only_unexecuted"
  },
  "supplemental_entries": [
    {
      "artifact_id": "github:1350484605",
      "github_id": 1350484605,
      "node_id": "R_kgDOUH7CfQ",
      "full_name": "rogerdigital/dsh-vet",
      "owner": "rogerdigital",
      "name": "dsh-vet",
      "artifact_type": "plugin",
      "source": "github",
      "repository_url": "https://github.com/rogerdigital/dsh-vet",
      "description": "Static permission and supply-chain review for DeepSeek Harness plugins, emitting a versioned dsh-vet/v1 report.",
      "description_origin": "repository_and_discussion_summary",
      "topics": [
        "deepseek-harness",
        "plugin-security",
        "static-analysis",
        "supply-chain"
      ],
      "language": "TypeScript",
      "github_stars": 1,
      "seed_rank": null,
      "forks_count": 0,
      "pushed_at": "2026-09-04T02:51:31Z",
      "archived": false,
      "default_branch": "main",
      "head_sha": "01857c72998c7ac7ad5a7241d13a8847c024558e",
      "parent_repository": null,
      "source_repository": "rogerdigital/dsh-vet",
      "license": {
        "spdx": "MIT",
        "status": "repository_and_package_reported"
      },
      "compatibility": {
        "declared_dsh_range": null,
        "observed_base": null,
        "summary": "Node >=20; manifest declares fs, shell, and web audit seams, but no exact Harness range."
      },
      "package": {
        "registry": "npm",
        "name": "dsh-vet",
        "version": "0.3.0",
        "published_at": "2026-09-02T08:15:36.999Z",
        "release_commit": "3005968cc708d12b7e1f98f1a312239b5312ce7f",
        "integrity": "sha512-HdQoj+ZxoYJRp3/PUK7fIIc/bj6FhyF86SDxyKapRQB1X23GY9hPM7PNoarzAvSa7k4isv6nrnXR8S7IqfQ0Ig==",
        "url": "https://www.npmjs.com/package/dsh-vet/v/0.3.0"
      },
      "discussion_url": "https://github.com/deepseek-ai/deepseek-harness/discussions/5423",
      "curation": {
        "rank": 1,
        "taxonomy": [
          "ecosystem governance",
          "static package audit",
          "supply-chain review"
        ],
        "scores": {
          "capability_evidence": 4,
          "compatibility": 3,
          "maintenance": 5,
          "license": 5
        },
        "security_risk": "medium",
        "evidence": "Manifest, test tree, workflow, and package metadata observed; published test results were not reproduced."
      },
      "analysis_status": "manifest_reviewed",
      "verification": {
        "metadata_only": true,
        "executed": false,
        "security_verified": false
      }
    },
    {
      "artifact_id": "github:1341363840",
      "github_id": 1341363840,
      "node_id": "R_kgDOT_OWgA",
      "full_name": "lemonxiny55/dsh-code-index",
      "owner": "lemonxiny55",
      "name": "dsh-code-index",
      "artifact_type": "plugin",
      "source": "github",
      "repository_url": "https://github.com/lemonxiny55/dsh-code-index",
      "description": "Tree-sitter-backed symbol index, code search, and bounded repository maps for Harness agent context.",
      "description_origin": "package_manifest",
      "topics": [
        "code-index",
        "deepseek-harness",
        "tree-sitter",
        "code-search"
      ],
      "language": "TypeScript",
      "github_stars": 3,
      "seed_rank": null,
      "forks_count": 0,
      "pushed_at": "2026-09-05T04:39:34Z",
      "archived": false,
      "default_branch": "main",
      "head_sha": "de81accbc5104fa2a872d692de7205b59d1e6130",
      "parent_repository": null,
      "source_repository": "lemonxiny55/dsh-code-index",
      "license": {
        "spdx": "MIT",
        "status": "repository_and_package_reported"
      },
      "compatibility": {
        "declared_dsh_range": ">=0.1.0-rc.1 \u003c0.2.0-0 for @deepseek-ai/dsh-tools",
        "observed_base": null,
        "summary": "Node >=22; Cordis ^4.0.1; release 0.3.1 updates web-tree-sitter to >=0.25 compatibility."
      },
      "package": {
        "registry": "npm",
        "name": "dsh-code-index",
        "version": "0.3.1",
        "published_at": "2026-09-05T04:18:31.854Z",
        "release_commit": null,
        "integrity": "sha512-rTCRRKrw/qJa7BQSE/CRV+I95KQnlgv35CDg1QHHu9cFEO6xH5ugLL4NDdcKoZH4x8fPxrITVIsXbe8rgUpWxg==",
        "url": "https://www.npmjs.com/package/dsh-code-index/v/0.3.1"
      },
      "discussion_url": "https://github.com/deepseek-ai/deepseek-harness/discussions/5623",
      "curation": {
        "rank": 2,
        "taxonomy": [
          "agent intelligence",
          "code navigation",
          "context retrieval"
        ],
        "scores": {
          "capability_evidence": 4,
          "compatibility": 4,
          "maintenance": 5,
          "license": 5
        },
        "security_risk": "medium-high",
        "evidence": "DSH bundle manifest, test tree, CI, and package metadata observed; published test totals were not reproduced."
      },
      "analysis_status": "manifest_reviewed",
      "verification": {
        "metadata_only": true,
        "executed": false,
        "security_verified": false
      }
    },
    {
      "artifact_id": "github:1295914860",
      "github_id": 1295914860,
      "node_id": "R_kgDOTT4XbA",
      "full_name": "Liyuan1992/rawmem",
      "owner": "Liyuan1992",
      "name": "rawmem",
      "artifact_type": "plugin",
      "source": "github",
      "repository_url": "https://github.com/Liyuan1992/rawmem",
      "description": "Local-first, append-only evidence ledger with bounded read-only MCP access to agent session history.",
      "description_origin": "mcp_manifest_and_discussion_summary",
      "topics": [
        "agent-memory",
        "evidence-ledger",
        "local-first",
        "mcp",
        "python"
      ],
      "language": "Python",
      "github_stars": 1,
      "seed_rank": null,
      "forks_count": 0,
      "pushed_at": "2026-09-02T23:16:10Z",
      "archived": false,
      "default_branch": "main",
      "head_sha": "dd0cf91726b903835a1517652e92ec95b4134e68",
      "parent_repository": null,
      "source_repository": "Liyuan1992/rawmem",
      "license": {
        "spdx": "MIT",
        "status": "repository_and_manifest_reported"
      },
      "compatibility": {
        "declared_dsh_range": null,
        "observed_base": null,
        "summary": "Python >=3.10 MCP sidecar with a DSH example configuration; not a native npm/Cordis bundle."
      },
      "package": {
        "registry": "mcpb",
        "name": "rawmem",
        "version": "0.7.1",
        "published_at": "2026-09-02T23:12:49Z",
        "release_commit": "dd0cf91726b903835a1517652e92ec95b4134e68",
        "integrity": "sha256-184b88f682bf27b7f06b4061f25972e572fbd3b22b147171a6c41dc9e6379266",
        "url": "https://github.com/Liyuan1992/rawmem/releases/tag/v0.7.1"
      },
      "discussion_url": "https://github.com/deepseek-ai/deepseek-harness/discussions/5597",
      "curation": {
        "rank": 3,
        "taxonomy": [
          "memory",
          "session evidence",
          "history retrieval"
        ],
        "scores": {
          "capability_evidence": 4,
          "compatibility": 3,
          "maintenance": 4,
          "license": 5
        },
        "security_risk": "medium",
        "evidence": "MCP manifest, checksummed artifact, DSH adapter tests, and privacy tests observed; tests were not reproduced."
      },
      "analysis_status": "manifest_reviewed",
      "verification": {
        "metadata_only": true,
        "executed": false,
        "security_verified": false
      }
    },
    {
      "artifact_id": "github:1289127532",
      "github_id": 1289127532,
      "node_id": "R_kgDOTNaGbA",
      "full_name": "Liyuan1992/memdsl",
      "owner": "Liyuan1992",
      "name": "memdsl",
      "artifact_type": "plugin",
      "source": "github",
      "repository_url": "https://github.com/Liyuan1992/memdsl",
      "description": "Declarative long-term agent memory with linting, queries, and a propose-review-approve workflow.",
      "description_origin": "mcp_manifest_and_discussion_summary",
      "topics": [
        "agent-memory",
        "declarative-language",
        "local-first",
        "mcp"
      ],
      "language": "Python",
      "github_stars": 1,
      "seed_rank": null,
      "forks_count": 0,
      "pushed_at": "2026-09-02T23:17:34Z",
      "archived": false,
      "default_branch": "main",
      "head_sha": "a061bc4efb9a0dacab04c2fa847bcf4b236146b4",
      "parent_repository": null,
      "source_repository": "Liyuan1992/memdsl",
      "license": {
        "spdx": "MIT",
        "status": "license_file_and_manifest_reported"
      },
      "compatibility": {
        "declared_dsh_range": null,
        "observed_base": null,
        "summary": "Python >=3.9; MCP extra requires Python >=3.10; DSH example configuration is present."
      },
      "package": {
        "registry": "mcpb",
        "name": "memdsl",
        "version": "0.9.2",
        "published_at": "2026-09-02T23:12:49Z",
        "release_commit": "a061bc4efb9a0dacab04c2fa847bcf4b236146b4",
        "integrity": "sha256-244f04d530917ff3fee35e419bf49f9b88d8395ddacfd24b1fdcda365298dd67",
        "url": "https://github.com/Liyuan1992/memdsl/releases/tag/v0.9.2"
      },
      "discussion_url": "https://github.com/deepseek-ai/deepseek-harness/discussions/5597",
      "curation": {
        "rank": 4,
        "taxonomy": [
          "memory",
          "long-term policy",
          "human approval"
        ],
        "scores": {
          "capability_evidence": 4,
          "compatibility": 3,
          "maintenance": 4,
          "license": 5
        },
        "security_risk": "medium-high",
        "evidence": "MCP manifest, checksummed artifact, policy/review tests, and DSH compatibility tests observed; tests were not reproduced."
      },
      "analysis_status": "manifest_reviewed",
      "verification": {
        "metadata_only": true,
        "executed": false,
        "security_verified": false
      }
    },
    {
      "artifact_id": "github:1357180789",
      "github_id": 1357180789,
      "node_id": "R_kgDOUOTvdQ",
      "full_name": "argszero/cordis-plugin-schedule-cron",
      "owner": "argszero",
      "name": "cordis-plugin-schedule-cron",
      "artifact_type": "plugin",
      "source": "github",
      "repository_url": "https://github.com/argszero/cordis-plugin-schedule-cron",
      "description": "Cron-driven autonomous task creation for Harness agents with monotonic scheduling cursors.",
      "description_origin": "repository_and_discussion_summary",
      "topics": [
        "deepseek-harness",
        "scheduling",
        "cron",
        "autonomous-agents"
      ],
      "language": "TypeScript",
      "github_stars": 0,
      "seed_rank": null,
      "forks_count": 0,
      "pushed_at": "2026-09-04T13:37:36Z",
      "archived": false,
      "default_branch": "main",
      "head_sha": "43a5dd072bef069d7a17e9a41d9f933571176573",
      "parent_repository": null,
      "source_repository": "argszero/cordis-plugin-schedule-cron",
      "license": {
        "spdx": "MIT",
        "status": "repository_and_package_reported"
      },
      "compatibility": {
        "declared_dsh_range": ">=0.1.0 for six DSH peers",
        "observed_base": null,
        "summary": "Node ^22.19 or >=24; Cordis >=4 \u003c5; broad DSH peers have no upper bounds and no DSH bundle manifest."
      },
      "package": {
        "registry": "npm",
        "name": "@argszero/cordis-plugin-schedule-cron",
        "version": "0.1.0",
        "published_at": "2026-09-04T13:37:17.972Z",
        "release_commit": "444974a39f2dabf2dd18e0920c8524307502b40c",
        "integrity": "sha512-aYtCRyKFFmLSVuS3XIeD8hvUa8uPMGAneIevm3k0ZpTv899j2Qq0xTiTSzXX0ZPq3GlxEkGP/ZOs7aAaAeYw3w==",
        "url": "https://www.npmjs.com/package/@argszero/cordis-plugin-schedule-cron/v/0.1.0"
      },
      "discussion_url": "https://github.com/deepseek-ai/deepseek-harness/discussions/5641",
      "curation": {
        "rank": 5,
        "taxonomy": [
          "orchestration",
          "scheduling",
          "autonomous task creation"
        ],
        "scores": {
          "capability_evidence": 3,
          "compatibility": 3,
          "maintenance": 5,
          "license": 5
        },
        "security_risk": "high",
        "evidence": "Package manifest, logic-test script, and repository source observed; published test results were not reproduced."
      },
      "analysis_status": "manifest_reviewed",
      "verification": {
        "metadata_only": true,
        "executed": false,
        "security_verified": false
      }
    },
    {
      "artifact_id": "github:1333974533",
      "github_id": 1333974533,
      "node_id": "R_kgDOT4LWBQ",
      "full_name": "Noob-stupid/dsh-plugin-hub",
      "owner": "Noob-stupid",
      "name": "dsh-plugin-hub",
      "artifact_type": "plugin",
      "source": "github",
      "repository_url": "https://github.com/Noob-stupid/dsh-plugin-hub",
      "description": "Plugin marketplace and profile manager with compatibility gates, enable/disable controls, and framework upgrade rollback.",
      "description_origin": "package_manifest_and_discussion_summary",
      "topics": [
        "deepseek-harness",
        "plugin-manager",
        "marketplace",
        "compatibility-gate"
      ],
      "language": "JavaScript",
      "github_stars": 78,
      "seed_rank": null,
      "forks_count": 8,
      "pushed_at": "2026-09-05T19:37:55Z",
      "archived": false,
      "default_branch": "main",
      "head_sha": "54dcbc18af52043f005a9760655a277154cfc810",
      "parent_repository": null,
      "source_repository": "Noob-stupid/dsh-plugin-hub",
      "license": {
        "spdx": "MIT",
        "status": "repository_and_package_reported"
      },
      "compatibility": {
        "declared_dsh_range": null,
        "observed_base": "author reports a compatibility gate for current DSH release-candidate layouts",
        "summary": "Native web bundle injects DSH client runtime, locale, and UI-settings packages; no Node engine is declared."
      },
      "package": {
        "registry": "npm",
        "name": "@noob-stupid/dsh-plugin-console",
        "version": "0.3.27",
        "published_at": "2026-09-04T10:17:16.288Z",
        "release_commit": "15bb4112f32edb496fef95daf3a7750c05607869",
        "integrity": "sha512-ZOv/rdQdGOiLrqCjyjIHhb/F74f+aM7TTZgY9MZPE9EN7Sv36Notvp2gzfCqx+YFurQGGc7A4G4u8TfDEb1G0Q==",
        "url": "https://www.npmjs.com/package/@noob-stupid/dsh-plugin-console/v/0.3.27"
      },
      "discussion_url": "https://github.com/deepseek-ai/deepseek-harness/discussions/5564",
      "curation": {
        "rank": 6,
        "taxonomy": [
          "discovery",
          "plugin lifecycle",
          "compatibility gating"
        ],
        "scores": {
          "capability_evidence": 4,
          "compatibility": 3,
          "maintenance": 5,
          "license": 5
        },
        "security_risk": "critical",
        "evidence": "DSH bundle/client manifest and standalone test files observed; package has no test script and no tests were reproduced."
      },
      "analysis_status": "manifest_reviewed",
      "verification": {
        "metadata_only": true,
        "executed": false,
        "security_verified": false
      }
    }
  ],
  "package_entries": [],
  "package_browser": {
    "status": "schema_pending",
    "upload_enabled": false,
    "download_enabled": false,
    "execution_enabled": false,
    "note": "This collection is reserved for user-published multi-plugin bundles. No sample packages are fabricated."
  }
};
// CATALOG_SNAPSHOT_END

function catalogDate(value) {
  if (!value || !Number.isFinite(Date.parse(value))) return 'Unknown';
  return new Date(value).toISOString().slice(0, 10);
}

const CATALOG = [
  ...CATALOG_SNAPSHOT.entries,
  ...(CATALOG_SNAPSHOT.supplemental_entries || []),
  ...(CATALOG_SNAPSHOT.package_entries || [])
].map(a => ({
  ...a,
  id: a.artifact_id, slug: a.full_name, type: a.artifact_type,
  url: a.repository_url, base: a.head_sha || 'Not captured',
  terms: [
    ...(a.topics || []),
    ...((a.curation && a.curation.taxonomy) || []),
    a.package && a.package.name,
    a.package && a.package.version
  ].filter(Boolean).join(' '),
  language: a.language || 'Not reported',
  licenseOk: !!a.license.spdx, licenseLabel: a.license.spdx || 'License unknown',
  starsLabel: Number.isInteger(a.github_stars) ? a.github_stars.toLocaleString('en-US') : '—',
  activity: 'Pushed ' + catalogDate(a.pushed_at),
  rankLabel: a.seed_rank
    ? 'F' + String(a.seed_rank).padStart(2, '0')
    : (a.curation && a.curation.rank ? 'P' + String(a.curation.rank).padStart(2, '0') : 'B'),
  versionLabel: a.package ? a.package.registry + ' · ' + a.package.version : '',
  riskLabel: a.curation ? a.curation.security_risk + ' risk' : '',
  archivedLabel: a.archived ? 'Archived' : '',
  commitUrl: a.head_sha ? a.repository_url + '/tree/' + a.head_sha : a.repository_url,
}));

function catalogRoute(hash) {
  if (hash === '#forks' || hash === '#public-repos') return { view: 'catalog', type: 'fork' };
  if (hash === '#packages') return { view: 'catalog', type: 'package' };
  if (hash === '#plugins' || hash === '#community') return { view: 'catalog', type: 'plugin' };
  return { view: 'launch', type: 'plugin' };
}

const COLUMNS = ['Cell / state', 'Tree', 'Surface', 'URL', 'Process identity', 'Uptime', 'Home / isolation', 'Workspace', 'Trust', 'Health', 'Actions'];

function pad(n) { return n < 10 ? '0' + n : '' + n; }

class Component extends DCLogic {
  constructor(props) {
    super(props);
    const initialRoute = catalogRoute(typeof window !== 'undefined' ? window.location.hash : '');
    this.state = {
      view: initialRoute.view,
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
      workspace: 'managed',
      advancedOpen: false,
      preview: null,
      logCell: null,
      query: '',
      catalogType: initialRoute.type,
      catalogSort: 'recommended',
      knownLicenseOnly: false,
      artifactId: CATALOG[0] ? CATALOG[0].id : null,
      toast: '',
      cells: [],
      sidecarConnected: false,
      statusLoaded: false,
      suggestedPort: Number(props.defaultPort ?? 3100),
      coverageGaps: [],
      credentials: [],
      sandbox: {
        mode: 'unavailable', ready: false, hostile_code_isolation: false,
        reason: 'Start the sidecar with a pinned Apptainer image to enable complete cells.'
      },
      sandboxTesting: null,
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
    this.hashListener = () => {
      const route = catalogRoute(window.location.hash);
      this.setState({ view: route.view, catalogType: route.type });
    };
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

  navigate(view, type = 'plugin') {
    this.setState({ view, catalogType: type });
    if (typeof window !== 'undefined') {
      window.location.hash = view === 'catalog'
        ? (type === 'fork' ? 'forks' : (type === 'package' ? 'packages' : 'plugins'))
        : 'launch';
    }
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
      credentials: Array.isArray(status.credentials) ? status.credentials : [],
      sandbox: status.sandbox || this.state.sandbox
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
      network: s.surface === 'web' ? 'host' : 'none',
      resources: { gpu: 'none' }
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
      this.flash('cell ' + cell.name + ' started inside Apptainer');
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
        home_mode: 'fresh', workspace: 'managed', network: 'host',
        resources: { gpu: 'none' }
      }) });
      await this.refreshStatus(true);
      this.setState({ selectedCell: cell.id, inspectorTab: 'logs' });
      await this.inspectCell(cell, 'logs');
      this.flash('launched ' + version.version + ' on automatic port ' + cell.port);
    } catch (error) { this.flash(error.message); }
  }

  async sandboxTest(tree) {
    if (!this.state.sidecarConnected || !this.state.sandbox.ready) {
      return this.flash(this.state.sandbox.reason || 'Configure the Apptainer sandbox first');
    }
    this.setState({ sandboxTesting: tree.id });
    try {
      const result = await this.api('/api/v1/trees/' + encodeURIComponent(tree.id) + '/sandbox-test', {
        method: 'POST', body: '{}'
      });
      await this.refreshStatus(true);
      this.flash('sandbox test ' + result.status + ' · network none · no launcher secrets');
    } catch (error) {
      this.flash(error.message);
    } finally {
      this.setState({ sandboxTesting: null });
    }
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
    const runnable = s.sidecarConnected && !!(s.sandbox && s.sandbox.ready) && !!t.id && t.trust !== 'foreign' && t.launchability === 'ready';
    const needsBuild = t.launchability === 'needs-build';
    const portNum = parseInt(s.port, 10);
    const occupyingCell = s.cells.find(c => c.port === portNum);
    const isSystem = portNum === 3080 || portNum === 3090;
    const confirm = this.props.confirmBeforeLaunch ?? true;
    const sandbox = s.sandbox || {};
    const versions = PINNED_RELEASES.map(pin => {
      const detected = s.trees.find(tr => tr.version === pin.version || (tr.git && String(tr.git.sha || '').startsWith(pin.commit)));
      const runnablePin = !!detected && s.sidecarConnected && !!sandbox.ready && detected.trust !== 'foreign' && detected.launchability === 'ready';
      return {
        ...pin,
        treeId: detected && detected.id,
        installPath: detected ? detected.path : 'Exact installation not detected',
        status: runnablePin ? 'sandbox ready' : (s.sidecarConnected && detected && !sandbox.ready ? 'runner unavailable' : (s.sidecarConnected ? 'not installed' : 'preview pin')),
        statusColor: runnablePin ? OK : WARN,
        buttonLabel: runnablePin ? 'Launch cell' : (s.sidecarConnected && detected && !sandbox.ready ? 'Configure runner' : (s.sidecarConnected ? 'Add installation' : 'Preview only')),
        disabled: !runnablePin,
        buttonCursor: runnablePin ? 'pointer' : 'not-allowed',
        buttonBg: runnablePin ? 'oklch(0.34 0.08 155)' : 'oklch(0.25 0.01 255)',
        buttonBorder: runnablePin ? 'oklch(0.52 0.13 155)' : BORDER,
        launch: () => this.quickLaunch({ ...pin, treeId: detected && detected.id })
      };
    });
    const communityTrees = s.trees.filter(tr => tr.trust === 'foreign').map(tr => {
      const result = tr.sandbox_test || {};
      const canTest = s.sidecarConnected && !!sandbox.ready && !['needs-build', 'not-executable'].includes(tr.launchability);
      const testing = s.sandboxTesting === tr.id;
      const passed = result.status === 'passed';
      const failed = ['failed', 'timeout'].includes(result.status);
      return {
        ...tr,
        revision: tr.git && tr.git.sha ? tr.git.sha : 'unknown revision',
        testState: passed ? 'passed capability probe' : (failed ? result.status : tr.launchability),
        stateColor: passed ? OK : (failed ? BAD : WARN),
        buttonLabel: testing ? 'Testing…' : (result.status ? 'Retest' : 'Test'),
        disabled: !canTest || testing,
        buttonCursor: canTest && !testing ? 'pointer' : 'not-allowed',
        buttonBg: canTest ? 'oklch(0.30 0.055 235)' : 'oklch(0.25 0.01 255)',
        buttonBorder: canTest ? 'oklch(0.48 0.09 235)' : BORDER,
        run: () => this.sandboxTest(tr)
      };
    });

    let portNote, portNoteFg = MUTED, portNoteBorder = BORDER, portNoteBg = 'transparent';
    if (s.surface === 'headless') { portNote = 'headless surface binds no HTTP port'; }
    else if (occupyingCell) { portNote = portNum + ' occupied by managed cell ' + occupyingCell.name + ' — stop it or use ' + this.freePort(); portNoteFg = WARN; portNoteBorder = 'oklch(0.42 0.09 85)'; portNoteBg = 'oklch(0.245 0.03 85)'; }
    else if (isSystem) { portNote = portNum + ' reserved (' + (portNum === 3080 ? 'operator DSH' : 'this sidecar') + ') — never replaced implicitly'; portNoteFg = BAD; portNoteBorder = 'oklch(0.42 0.1 25)'; portNoteBg = 'oklch(0.25 0.04 25)'; }
    else if (!s.sidecarConnected) { portNote = 'Portable preview only · start scripts/serve.py to validate and launch'; portNoteFg = WARN; }
    else { portNote = portNum + ' will be checked on loopback immediately before spawn'; portNoteFg = OK; }

    const homeModes = [
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
        isolationColor: MUTED,
        trust: ct.trust, trustColor: ct.trust === 'personal' ? OK : (ct.trust === 'readonly' ? BLUE : BAD),
        trustBorder: ct.trust === 'personal' ? 'oklch(0.42 0.1 155)' : (ct.trust === 'readonly' ? 'oklch(0.42 0.08 235)' : 'oklch(0.42 0.1 25)'),
        health,
        resourcesList: [
          { label: 'CPU', value: (c.resources && c.resources.cpu) || 'unknown' },
          { label: 'GPU', value: (c.resources && c.resources.gpu) || 'none' },
          { label: 'RAM', value: (c.resources && c.resources.ram) || 'unknown' }
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
        a.type === s.catalogType &&
        (!s.knownLicenseOnly || a.licenseOk);
    }).sort((a, b) => {
      if (s.catalogSort === 'name') return a.slug.localeCompare(b.slug);
      if (s.catalogSort === 'recent') return (Date.parse(b.pushed_at) || 0) - (Date.parse(a.pushed_at) || 0) || (a.seed_rank || 999) - (b.seed_rank || 999);
      if (s.catalogSort === 'recommended') {
        const aRank = (a.curation && a.curation.rank) || a.seed_rank || 999;
        const bRank = (b.curation && b.curation.rank) || b.seed_rank || 999;
        return aRank - bRank;
      }
      return (b.github_stars ?? -1) - (a.github_stars ?? -1) || (a.seed_rank || 999) - (b.seed_rank || 999);
    });
    // Never keep an unrelated detail open after search/filter removes it.
    const detail = filtered.find(a => a.id === s.artifactId) || filtered[0] || {};
    const results = filtered.map(a => ({
      ...a, selected: a.id === detail.id,
      accessibleLabel: 'Inspect ' + a.type + ' ' + a.slug + ', ' + a.starsLabel + ' GitHub stars',
      border: a.id === detail.id ? SELB : BORDER,
      bg: a.id === detail.id ? 'oklch(0.245 0.022 255)' : 'oklch(0.21 0.01 255)',
      select: () => this.setState({ artifactId: a.id })
    }));
    const detailRows = !detail.id ? [] : [
      { k: 'Artifact type', v: detail.type, color: TXT },
      { k: 'GitHub identity', v: detail.id, color: TXT },
      { k: 'Default branch', v: detail.default_branch || 'Not reported', color: TXT },
      { k: 'Captured commit', v: detail.base, color: TXT },
      { k: detail.type === 'fork' ? 'Fork source' : 'Source repository', v: detail.source_repository || 'Not reported', color: MUTED },
      ...(detail.package ? [
        { k: 'Package', v: detail.package.name + '@' + detail.package.version, color: BLUE },
        { k: 'Registry', v: detail.package.registry + ' · exact version', color: MUTED },
        { k: 'Integrity', v: detail.package.integrity, color: MUTED }
      ] : []),
      { k: 'Last push', v: detail.pushed_at || 'Not reported', color: MUTED },
      { k: 'License', v: detail.licenseLabel + ' · reported metadata', color: detail.licenseOk ? MUTED : WARN },
      { k: 'Trust', v: 'Metadata only · not executed', color: WARN }
    ];
    const detailCompatibilityText = detail.id
      ? ((detail.compatibility && detail.compatibility.summary) || 'No fork differences or runtime compatibility tests have been computed.')
      : '';
    const detailEvidenceText = detail.curation
      ? detail.curation.evidence
      : 'No source analysis has been computed. Repository descriptions and GitHub metadata are shown as claims, not verification.';
    const detailTaxonomy = detail.curation ? detail.curation.taxonomy.join(' / ') : 'Unclassified';
    const packageCount = CATALOG.filter(a => a.type === 'package').length;
    const pluginCount = CATALOG.filter(a => a.type === 'plugin').length;
    const forkCount = CATALOG.filter(a => a.type === 'fork').length;
    const emptyCopy = s.catalogType === 'package'
      ? {
          title: 'No community packages published yet',
          description: 'This browser is ready for signed, versioned multi-plugin bundles, but the package schema and upload endpoint are not connected. No samples are fabricated.',
          action: 'Browse plugins',
          run: () => this.navigate('catalog', 'plugin')
        }
      : {
          title: 'No matching ' + (s.catalogType === 'plugin' ? 'plugins' : 'forks'),
          description: 'Try a name, author, capability, taxonomy term, or clear the current filters.',
          action: 'Clear filters',
          run: () => this.setState({ query: '', knownLicenseOnly: false })
        };

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
      goCatalog: () => this.navigate('catalog', 'plugin'),
      modeLabel: s.sidecarConnected ? 'sandbox fleet' : 'portable preview',
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
      communityTrees,
      hasCommunityTrees: communityTrees.length > 0,
      sandboxTitle: sandbox.ready ? 'Apptainer cell runner ready' : 'Apptainer cell runner unavailable',
      sandboxReason: sandbox.reason || 'No capability result is available.',
      sandboxColor: sandbox.ready ? OK : WARN,
      sandboxBorder: sandbox.ready ? 'oklch(0.42 0.08 155)' : 'oklch(0.42 0.07 85)',
      sandboxBg: sandbox.ready ? 'oklch(0.235 0.025 155)' : 'oklch(0.245 0.025 85)',
      sandboxPolicy: sandbox.ready
        ? 'Pinned SIF · source read-only · unique writable state · secrets excluded · ' + ((sandbox.resource_limits || {}).cpus || '—') + ' CPU · ' + ((sandbox.resource_limits || {}).memory || '—') + ' RAM'
        : 'All cell launches fail closed. Configure a pinned SIF and pass the runtime capability probe.',

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
          select: () => ok ? this.setState({ treeId: tr.id }) : this.flash('foreign trees can be capability-tested only; complete-cell promotion is not implemented')
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

      advancedOpen: s.advancedOpen,
      advancedCaret: s.advancedOpen ? '▾' : '▸',
      toggleAdvanced: () => this.setState({ advancedOpen: !s.advancedOpen }),
      advancedRows: [
        { label: 'Discovery policy', value: 'configured roots · bounded · no code execution', color: OK },
        { label: 'Process identity', value: 'timeout supervisor PID + OS process-start identity', color: BLUE },
        { label: 'Execution backend', value: 'Apptainer required · no host fallback', color: OK },
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

      primaryLabel: !s.sidecarConnected ? 'Start local sidecar to launch' : (!t.id ? 'Add a DSH tree' : (t.trust === 'foreign' ? 'Sandbox test only' : (needsBuild ? 'Build required' : (confirm ? 'Preview launch…' : 'Start cell')))),
      primaryAction: () => {
        if (!s.sidecarConnected) return this.flash('Run python3 scripts/serve.py to connect the launcher');
        if (!runnable) return this.flash(t.trust === 'foreign' ? 'foreign trees require the separate promotion policy' : (!sandbox.ready ? (sandbox.reason || 'configure the Apptainer cell runner') : 'select a launch-ready detected tree'));
        if (needsBuild) return this.flash('build orchestration is deferred; build this tree using its own documentation, then restart Forge');
        if (confirm) return this.previewLaunch();
        this.startCell();
      },
      launchDisabled: !runnable,
      primaryBg: runnable ? 'oklch(0.34 0.08 155)' : 'oklch(0.24 0.01 255)',
      primaryFg: runnable ? 'oklch(0.95 0.05 155)' : 'oklch(0.55 0.01 255)',
      primaryBorder: runnable ? 'oklch(0.52 0.13 155)' : BORDER,
      primaryCursor: runnable ? 'pointer' : 'not-allowed',
      launchHint: s.sidecarConnected ? 'Every launch requires the pinned Apptainer runner. There is no host-process fallback.' : 'Portable preview only. No sample process is presented as real; run scripts/serve.py for local controls.',

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
      repoTypes: [{ id: 'plugin', label: 'Plugins' }, { id: 'fork', label: 'Forks' }, { id: 'package', label: 'Packages' }].map(f => ({
        ...f, count: CATALOG.filter(a => a.type === f.id).length,
        selected: s.catalogType === f.id,
        border: s.catalogType === f.id ? 'oklch(0.43 0.05 235)' : 'transparent',
        bg: s.catalogType === f.id ? 'oklch(0.29 0.035 235)' : 'transparent',
        color: s.catalogType === f.id ? 'oklch(0.88 0.035 235)' : MUTED,
        select: () => this.navigate('catalog', f.id)
      })),
      seedCount: CATALOG_SNAPSHOT.entries.length,
      pluginCount,
      forkCount,
      packageCount,
      catalogCountLabel: pluginCount + ' plugins · ' + forkCount + ' forks · ' + packageCount + ' packages',
      resultCount: results.length + ' ' + (s.catalogType === 'plugin' ? 'plugins' : (s.catalogType === 'fork' ? 'forks' : 'packages')),
      sortExplanation: s.catalogSort === 'recommended'
        ? (s.catalogType === 'plugin' ? 'Evidence-ranked · not a security verdict' : 'Captured snapshot order')
        : (s.catalogSort === 'stars' ? 'GitHub stars · not a quality score' : (s.catalogSort === 'recent' ? 'Most recent repository push' : 'Alphabetical by owner / repository')),
      results,
      noResults: results.length === 0,
      hasDetail: !!detail.id,
      detail,
      detailRows,
      detailTopics: (detail.topics || []).slice(0, 8),
      detailCompatibilityText,
      detailEvidenceText,
      detailTaxonomy,
      detailRisk: detail.curation ? detail.curation.security_risk + ' risk · static-review priority P' + String(detail.curation.rank).padStart(2, '0') : 'Unassessed',
      hasPackageLink: !!(detail.package && detail.package.url),
      detailPackageUrl: detail.package ? detail.package.url : '',
      detailPackageLabel: detail.package ? 'View ' + detail.package.registry + ' package ↗' : '',
      hasDiscussionLink: !!detail.discussion_url,
      detailDiscussionUrl: detail.discussion_url || '',
      emptyTitle: emptyCopy.title,
      emptyDescription: emptyCopy.description,
      emptyActionLabel: emptyCopy.action,
      resetCatalogFilters: emptyCopy.run,
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
