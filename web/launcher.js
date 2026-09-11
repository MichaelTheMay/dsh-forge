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
      "artifact_id": "github:1332073142",
      "github_id": 1332073142,
      "node_id": "R_kgDOT2XStg",
      "full_name": "NanmiCoder/dsh-agent-teams",
      "owner": "NanmiCoder",
      "name": "dsh-agent-teams",
      "artifact_type": "plugin",
      "source": "github",
      "repository_url": "https://github.com/NanmiCoder/dsh-agent-teams",
      "description": "Captain-led, persistent multi-agent teams with dependency-aware tasks, direct messaging, quality gates, recovery, and a live Web activity panel.",
      "description_origin": "package_manifest_and_repository_summary",
      "topics": [
        "agentteams",
        "deepseek-harness",
        "dsh-plugin",
        "multi-agent",
        "task-dag"
      ],
      "language": "JavaScript",
      "github_stars": 1388,
      "seed_rank": null,
      "forks_count": 120,
      "pushed_at": "2026-09-05T18:08:52Z",
      "archived": false,
      "default_branch": "main",
      "head_sha": "1caff61f4c0909711b515ebc56187055556186cd",
      "parent_repository": null,
      "source_repository": "NanmiCoder/dsh-agent-teams",
      "license": {
        "spdx": "MIT",
        "status": "repository_and_package_reported"
      },
      "compatibility": {
        "declared_dsh_range": "0.1.2-rc.1 || 0.1.2-alpha.5 || 0.1.2-alpha.2",
        "observed_base": "package manifest pins its development matrix to DeepSeek Harness 0.1.2-rc.1",
        "summary": "Node ^22.19 or >=24; Web and headless support are declared. The existing 0.1.2-alpha.3 Delta tree is not in the plugin's supported host list."
      },
      "package": {
        "registry": "npm",
        "name": "@nanmicoder/dsh-agent-teams",
        "version": "0.1.16-rc.1",
        "published_at": "2026-09-05T17:42:57.391Z",
        "release_commit": null,
        "integrity": "sha512-gHrlUXuFnqz4wBw55v3ury/0PhNNCZ8/1eYycXUWGUgz97sxMzOMOLGGtpBijQ2/TzOqgRkv43+i/zKFU5GIZQ==",
        "url": "https://www.npmjs.com/package/@nanmicoder/dsh-agent-teams/v/0.1.16-rc.1"
      },
      "discussion_url": "https://github.com/deepseek-ai/deepseek-harness/discussions/1785",
      "curation": {
        "rank": 1,
        "taxonomy": [
          "multi-agent orchestration",
          "persistent teams",
          "task dependency graph",
          "quality gates"
        ],
        "scores": {
          "capability_evidence": 5,
          "compatibility": 4,
          "maintenance": 5,
          "license": 5
        },
        "security_risk": "high",
        "evidence": "Native DSH bundle/client metadata, an explicit compatibility matrix, verification scripts, CI, recovery logic, and documentation were observed; no test was reproduced by Forge yet."
      },
      "analysis_status": "manifest_reviewed",
      "verification": {
        "metadata_only": true,
        "executed": false,
        "security_verified": false
      }
    },
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
        "rank": 2,
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
        "rank": 3,
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
        "rank": 4,
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
        "rank": 5,
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
        "rank": 6,
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
        "rank": 7,
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
  "package_entries": [
    {
      "schema": "dsh-forge.catalog-package/v1",
      "id": "catalog-package:agent-teams-builder",
      "slug": "agent-teams-builder",
      "name": "AgentTeams Builder",
      "summary": "A pinned AgentTeams package candidate for using persistent, dependency-aware DeepSeek Harness teams to help build and review DSH Forge.",
      "kind": "single_plugin",
      "rank": 1,
      "featured": true,
      "publisher": {
        "id": "dsh-forge-curation",
        "name": "DSH Forge curation",
        "kind": "curator"
      },
      "components": [
        {
          "artifact_id": "github:1332073142",
          "role": "Captain-led persistent agent teams, task DAGs, direct messaging, quality gates, and live Web inspection.",
          "package": {
            "registry": "npm",
            "name": "@nanmicoder/dsh-agent-teams",
            "version": "0.1.16-rc.1",
            "integrity": "sha512-gHrlUXuFnqz4wBw55v3ury/0PhNNCZ8/1eYycXUWGUgz97sxMzOMOLGGtpBijQ2/TzOqgRkv43+i/zKFU5GIZQ==",
            "url": "https://www.npmjs.com/package/@nanmicoder/dsh-agent-teams/v/0.1.16-rc.1"
          },
          "repository": {
            "full_name": "NanmiCoder/dsh-agent-teams",
            "url": "https://github.com/NanmiCoder/dsh-agent-teams",
            "commit": "1caff61f4c0909711b515ebc56187055556186cd"
          },
          "compatibility": "Node ^22.19 or >=24; Web and headless support are declared. The existing 0.1.2-alpha.3 Delta tree is not in the plugin's supported host list."
        }
      ],
      "taxonomy": [
        "multi-agent orchestration",
        "collaboration",
        "persistent tasks",
        "quality gates"
      ],
      "compatibility": {
        "status": "declared",
        "harness_versions": [
          "0.1.2-rc.1",
          "0.1.2-alpha.5",
          "0.1.2-alpha.2"
        ],
        "node": "^22.19.0 || >=24",
        "surfaces": [
          "web",
          "headless"
        ],
        "summary": "The publisher declares these exact host versions. Forge has not yet reproduced the matrix; alpha.3 is deliberately excluded."
      },
      "license": {
        "status": "reported",
        "expressions": [
          "MIT"
        ]
      },
      "risk": {
        "level": "high",
        "permissions": [
          "subagent creation",
          "workspace writes",
          "persistent state",
          "model calls"
        ],
        "notes": "Parallel delegated agents amplify filesystem, model-cost, and prompt-injection risk. Test only in a disposable Apptainer profile before promotion."
      },
      "provenance": {
        "directory_ids": [
          "dsh-get",
          "awesome-dsh",
          "npm",
          "github"
        ],
        "authoritative_sources": [
          "https://github.com/NanmiCoder/dsh-agent-teams/tree/1caff61f4c0909711b515ebc56187055556186cd",
          "https://github.com/deepseek-ai/deepseek-harness/discussions/1785",
          "https://www.npmjs.com/package/@nanmicoder/dsh-agent-teams/v/0.1.16-rc.1"
        ],
        "claims_verified": false
      },
      "verification": {
        "metadata_reviewed": true,
        "artifacts_acquired": false,
        "installed": false,
        "executed": false,
        "sandbox_verified": false
      },
      "acquisition": {
        "enabled": false,
        "label": "Acquire verified bytes",
        "status": "requires_signed_dsse",
        "reason": "No trusted DSSE envelope is published for this catalog recipe; installation and execution are not authorized."
      },
      "page": {
        "route": "#packages/agent-teams-builder"
      },
      "updated_at": "2026-09-05T21:30:00Z"
    },
    {
      "schema": "dsh-forge.catalog-package/v1",
      "id": "catalog-package:code-review-lab",
      "slug": "code-review-lab",
      "name": "Code Review Lab",
      "summary": "A static-review candidate combining pre-install plugin auditing with a repository symbol index and bounded code maps.",
      "kind": "plugin_stack",
      "rank": 2,
      "featured": true,
      "publisher": {
        "id": "dsh-forge-curation",
        "name": "DSH Forge curation",
        "kind": "curator"
      },
      "components": [
        {
          "artifact_id": "github:1350484605",
          "role": "Audit plugin metadata and supply-chain indicators before any install boundary.",
          "package": {
            "registry": "npm",
            "name": "dsh-vet",
            "version": "0.3.0",
            "integrity": "sha512-HdQoj+ZxoYJRp3/PUK7fIIc/bj6FhyF86SDxyKapRQB1X23GY9hPM7PNoarzAvSa7k4isv6nrnXR8S7IqfQ0Ig==",
            "url": "https://www.npmjs.com/package/dsh-vet/v/0.3.0"
          },
          "repository": {
            "full_name": "rogerdigital/dsh-vet",
            "url": "https://github.com/rogerdigital/dsh-vet",
            "commit": "01857c72998c7ac7ad5a7241d13a8847c024558e"
          },
          "compatibility": "Node >=20; manifest declares fs, shell, and web audit seams, but no exact Harness range."
        },
        {
          "artifact_id": "github:1341363840",
          "role": "Build a symbol index and bounded repository map for code review context.",
          "package": {
            "registry": "npm",
            "name": "dsh-code-index",
            "version": "0.3.1",
            "integrity": "sha512-rTCRRKrw/qJa7BQSE/CRV+I95KQnlgv35CDg1QHHu9cFEO6xH5ugLL4NDdcKoZH4x8fPxrITVIsXbe8rgUpWxg==",
            "url": "https://www.npmjs.com/package/dsh-code-index/v/0.3.1"
          },
          "repository": {
            "full_name": "lemonxiny55/dsh-code-index",
            "url": "https://github.com/lemonxiny55/dsh-code-index",
            "commit": "de81accbc5104fa2a872d692de7205b59d1e6130"
          },
          "compatibility": "Node >=22; Cordis ^4.0.1; release 0.3.1 updates web-tree-sitter to >=0.25 compatibility."
        }
      ],
      "taxonomy": [
        "code intelligence",
        "static audit",
        "supply-chain review",
        "repository mapping"
      ],
      "compatibility": {
        "status": "unknown",
        "harness_versions": [],
        "node": ">=22",
        "surfaces": [
          "web",
          "headless"
        ],
        "summary": "The components have not been tested together. dsh-code-index declares a broad pre-0.2 tools range; dsh-vet declares no exact Harness range."
      },
      "license": {
        "status": "reported",
        "expressions": [
          "MIT"
        ]
      },
      "risk": {
        "level": "medium-high",
        "permissions": [
          "repository reads",
          "recursive indexing",
          "archive parsing"
        ],
        "notes": "Review path confinement, symlink handling, malicious archive behavior, prompt injection through source text, and resource exhaustion."
      },
      "provenance": {
        "directory_ids": [
          "awesome-dsh",
          "show-your-plugins",
          "npm",
          "github"
        ],
        "authoritative_sources": [
          "https://github.com/deepseek-ai/deepseek-harness/discussions/5423",
          "https://github.com/deepseek-ai/deepseek-harness/discussions/5623",
          "https://github.com/lemonxiny55/dsh-code-index/tree/de81accbc5104fa2a872d692de7205b59d1e6130",
          "https://github.com/rogerdigital/dsh-vet/tree/01857c72998c7ac7ad5a7241d13a8847c024558e",
          "https://www.npmjs.com/package/dsh-code-index/v/0.3.1",
          "https://www.npmjs.com/package/dsh-vet/v/0.3.0"
        ],
        "claims_verified": false
      },
      "verification": {
        "metadata_reviewed": true,
        "artifacts_acquired": false,
        "installed": false,
        "executed": false,
        "sandbox_verified": false
      },
      "acquisition": {
        "enabled": false,
        "label": "Acquire verified bytes",
        "status": "requires_signed_dsse",
        "reason": "No trusted DSSE envelope is published for this catalog recipe; installation and execution are not authorized."
      },
      "page": {
        "route": "#packages/code-review-lab"
      },
      "updated_at": "2026-09-05T21:30:00Z"
    },
    {
      "schema": "dsh-forge.catalog-package/v1",
      "id": "catalog-package:auditable-memory-lab",
      "slug": "auditable-memory-lab",
      "name": "Auditable Memory Lab",
      "summary": "A local-first memory candidate pairing an append-only session evidence ledger with reviewed long-term rules and preferences.",
      "kind": "plugin_stack",
      "rank": 3,
      "featured": false,
      "publisher": {
        "id": "dsh-forge-curation",
        "name": "DSH Forge curation",
        "kind": "curator"
      },
      "components": [
        {
          "artifact_id": "github:1295914860",
          "role": "Retain immutable, queryable evidence from prior sessions.",
          "package": {
            "registry": "mcpb",
            "name": "rawmem",
            "version": "0.7.1",
            "integrity": "sha256-184b88f682bf27b7f06b4061f25972e572fbd3b22b147171a6c41dc9e6379266",
            "url": "https://github.com/Liyuan1992/rawmem/releases/tag/v0.7.1"
          },
          "repository": {
            "full_name": "Liyuan1992/rawmem",
            "url": "https://github.com/Liyuan1992/rawmem",
            "commit": "dd0cf91726b903835a1517652e92ec95b4134e68"
          },
          "compatibility": "Python >=3.10 MCP sidecar with a DSH example configuration; not a native npm/Cordis bundle."
        },
        {
          "artifact_id": "github:1289127532",
          "role": "Propose, review, and approve durable memory policy entries.",
          "package": {
            "registry": "mcpb",
            "name": "memdsl",
            "version": "0.9.2",
            "integrity": "sha256-244f04d530917ff3fee35e419bf49f9b88d8395ddacfd24b1fdcda365298dd67",
            "url": "https://github.com/Liyuan1992/memdsl/releases/tag/v0.9.2"
          },
          "repository": {
            "full_name": "Liyuan1992/memdsl",
            "url": "https://github.com/Liyuan1992/memdsl",
            "commit": "a061bc4efb9a0dacab04c2fa847bcf4b236146b4"
          },
          "compatibility": "Python >=3.9; MCP extra requires Python >=3.10; DSH example configuration is present."
        }
      ],
      "taxonomy": [
        "memory",
        "session evidence",
        "human approval",
        "local-first"
      ],
      "compatibility": {
        "status": "unknown",
        "harness_versions": [],
        "node": null,
        "surfaces": [
          "mcp"
        ],
        "summary": "Both are Python MCP sidecars with DSH examples, not native Cordis bundles. Their combined lifecycle has not been reproduced."
      },
      "license": {
        "status": "reported",
        "expressions": [
          "MIT"
        ]
      },
      "risk": {
        "level": "medium-high",
        "permissions": [
          "session-log reads",
          "persistent memory writes",
          "local filesystem"
        ],
        "notes": "Review path confinement, retention, redaction, untrusted-record rendering, memory poisoning, and approval bypass before any session data is exposed."
      },
      "provenance": {
        "directory_ids": [
          "show-your-plugins",
          "github"
        ],
        "authoritative_sources": [
          "https://github.com/Liyuan1992/memdsl/releases/tag/v0.9.2",
          "https://github.com/Liyuan1992/memdsl/tree/a061bc4efb9a0dacab04c2fa847bcf4b236146b4",
          "https://github.com/Liyuan1992/rawmem/releases/tag/v0.7.1",
          "https://github.com/Liyuan1992/rawmem/tree/dd0cf91726b903835a1517652e92ec95b4134e68",
          "https://github.com/deepseek-ai/deepseek-harness/discussions/5597"
        ],
        "claims_verified": false
      },
      "verification": {
        "metadata_reviewed": true,
        "artifacts_acquired": false,
        "installed": false,
        "executed": false,
        "sandbox_verified": false
      },
      "acquisition": {
        "enabled": false,
        "label": "Acquire verified bytes",
        "status": "requires_signed_dsse",
        "reason": "No trusted DSSE envelope is published for this catalog recipe; installation and execution are not authorized."
      },
      "page": {
        "route": "#packages/auditable-memory-lab"
      },
      "updated_at": "2026-09-05T21:30:00Z"
    }
  ],
  "package_browser": {
    "status": "metadata_catalog_preview",
    "schema": "dsh-forge.catalog-package/v1",
    "signature_envelope": "dsse/v1-ed25519",
    "composition_enabled": true,
    "upload_enabled": false,
    "download_enabled": false,
    "execution_enabled": false,
    "note": "Schema-valid metadata packages and dedicated routes are available. Each recipe still requires a trusted DSSE envelope before acquisition; upload, installation, and execution remain disconnected."
  },
  "package_catalog_digest": "sha256:859db6e98ac43f2700d8efc66c0205ec5a9cfdb579f70b8f9641cc089a702c1c"
};
// CATALOG_SNAPSHOT_END

function catalogDate(value) {
  if (!value || !Number.isFinite(Date.parse(value))) return 'Unknown';
  return new Date(value).toISOString().slice(0, 10);
}

// One mapping serves both corpora: the embedded snapshot and the records the
// catalog store hands back verbatim.
function mapRepositoryArtifact(a) {
  const hiddenGem = a.hidden_gem && a.hidden_gem.policy ? a.hidden_gem : null;
  return ({
  ...a,
  id: a.artifact_id, slug: a.full_name, type: a.artifact_type,
  url: a.repository_url, base: a.head_sha || 'Not captured',
  terms: [
    ...(a.topics || []),
    ...((a.curation && a.curation.taxonomy) || []),
    ...((a.divergence && a.divergence.changed_paths) || []).slice(0, 64),
    ...((a.compatibility && a.compatibility.changed_surfaces) || []),
    a.package && a.package.name,
    a.package && a.package.version
  ].filter(Boolean).join(' '),
  language: a.language || 'Not reported',
  licenseOk: !!a.license.spdx, licenseLabel: a.license.spdx || 'License unknown',
  starsLabel: Number.isInteger(a.github_stars) ? a.github_stars.toLocaleString('en-US') : '—',
  activity: 'Pushed ' + catalogDate(a.pushed_at),
  hiddenGem,
  rankLabel: hiddenGem && hiddenGem.rank
    ? 'H' + String(hiddenGem.rank).padStart(2, '0')
    : (a.seed_rank
    ? 'F' + String(a.seed_rank).padStart(2, '0')
    : (a.curation && a.curation.rank ? 'P' + String(a.curation.rank).padStart(2, '0') : 'B')),
  versionLabel: a.package ? a.package.registry + ' · ' + a.package.version : '',
  riskLabel: a.curation
    ? a.curation.security_risk + ' risk'
    : ((a.risk_signals || []).length ? (a.risk_signals || []).length + ' risk signal(s)' : ''),
  archivedLabel: a.archived ? 'Archived' : '',
  commitUrl: a.head_sha ? a.repository_url + '/tree/' + a.head_sha : a.repository_url,
  featured: hiddenGem ? hiddenGem.candidate : (a.artifact_type === 'plugin'
    ? !!(a.curation && a.curation.rank <= 3)
    : Number(a.seed_rank || 999) <= 3),
  });
}

function mapPackageArtifact(a) {
  return ({
  ...a,
  verification: {
    ...a.verification,
    metadata_only: true,
    security_verified: false
  },
  id: a.id,
  slug: a.slug,
  full_name: a.publisher.id + '/' + a.slug,
  owner: a.publisher.name,
  type: 'package',
  url: a.page.route,
  description: a.summary,
  topics: a.taxonomy,
  terms: [
    ...a.taxonomy,
    ...a.components.flatMap(component => [
      component.repository.full_name,
      component.package.name,
      component.package.version,
      component.role
    ]),
    ...a.compatibility.surfaces
  ].join(' '),
  language: a.kind === 'plugin_stack' ? 'Plugin stack' : 'Single plugin',
  licenseOk: a.license.status !== 'unknown',
  licenseLabel: a.license.expressions.join(' + '),
  starsLabel: '—',
  github_stars: null,
  pushed_at: a.updated_at,
  activity: 'Updated ' + catalogDate(a.updated_at),
  rankLabel: 'B' + String(a.rank).padStart(2, '0'),
  versionLabel: a.components.length + (a.components.length === 1 ? ' component' : ' components'),
  riskLabel: a.risk.level + ' risk',
  archivedLabel: '',
  base: a.components.length + ' immutable component pin' + (a.components.length === 1 ? '' : 's'),
  commitUrl: a.provenance.authoritative_sources[0],
  pageRoute: a.page.route,
  catalogPackage: true
  });
}

// A store record keeps its snapshot shape, so its type decides the mapping.
function mapCatalogRecord(record) {
  return record && record.artifact_type ? mapRepositoryArtifact(record) : mapPackageArtifact(record);
}

const REPOSITORY_CATALOG = [
  ...CATALOG_SNAPSHOT.entries,
  ...(CATALOG_SNAPSHOT.supplemental_entries || [])
].map(mapRepositoryArtifact);
const PACKAGE_CATALOG = (CATALOG_SNAPSHOT.package_entries || []).map(mapPackageArtifact);
const CATALOG = [...PACKAGE_CATALOG, ...REPOSITORY_CATALOG];

function catalogRoute(hash) {
  if (hash === '#assistant') return { view: 'assistant', type: 'plugin' };
  if (hash === '#forks' || hash === '#public-repos') return { view: 'catalog', type: 'fork' };
  if (hash === '#packages') return { view: 'catalog', type: 'package', packageSlug: null };
  if (hash === '#community') return { view: 'catalog', type: 'plugin' };
  const packageMatch = /^#packages\/([a-z0-9][a-z0-9-]{1,63})$/.exec(hash);
  if (packageMatch) return { view: 'catalog', type: 'package', packageSlug: packageMatch[1] };
  if (hash === '#plugins') return { view: 'catalog', type: 'plugin' };
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
      treeId: null,
      trees: [],
      savedVersions: [],
      trustedPackageRecipes: [],
      packageInstallations: [],
      configurations: [],
      profiles: [],
      profileTask: '',
      profileBusy: false,
      pendingProfile: null,
      catalogProfileId: '',
      packageVersionId: '',
      packageInstallBusy: false,
      configurationBusy: false,
      catalogScope: 'all',
      catalogStore: { available: false },
      storeArtifacts: [],
      storeTotal: 0,
      storeCursor: '',
      storeLoading: false,
      storeError: '',
      storeGeneration: 0,
      assistantVersionId: '',
      assistantBusy: false,
      assistantCellId: null,
      assistantUrl: '',
      versionsDirectory: { path: '~/dsh-versions', available: false, auto_scan: true },
      versionFormOpen: false,
      versionPath: '',
      versionBusy: false,
      versionSettingsId: null,
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
      artifactId: initialRoute.packageSlug
        ? ((PACKAGE_CATALOG.find(item => item.slug === initialRoute.packageSlug) || {}).id || null)
        : (CATALOG.find(item => item.type === initialRoute.type) || CATALOG[0] || {}).id,
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
    this.scanTimer = setInterval(() => {
      if (this.state.sidecarConnected && !this.state.versionBusy) this.rescanVersions(true);
    }, 30000);
    this.inspectorTimer = setInterval(() => {
      const cell = this.state.view === 'launch' && this.state.cells.find(item => item.id === this.state.selectedCell);
      if (cell) this.inspectCell(cell, this.state.inspectorTab);
    }, 3000);
    this.hashListener = () => {
      const route = catalogRoute(window.location.hash);
      const packageArtifact = route.packageSlug
        ? PACKAGE_CATALOG.find(item => item.slug === route.packageSlug)
        : null;
      this.setState({
        view: route.view,
        catalogType: route.type,
        artifactId: packageArtifact ? packageArtifact.id : this.state.artifactId
      });
    };
    window.addEventListener('hashchange', this.hashListener);
    this.refreshStatus(true);
  }
  componentWillUnmount() {
    clearInterval(this.timer);
    clearInterval(this.statusTimer);
    clearInterval(this.scanTimer);
    clearInterval(this.inspectorTimer);
    if (this.toastTimer) clearTimeout(this.toastTimer);
    if (this.hashListener) window.removeEventListener('hashchange', this.hashListener);
  }

  navigate(view, type = 'package') {
    this.setState({ view, catalogType: type });
    if (typeof window !== 'undefined') {
      window.location.hash = view === 'catalog'
        ? (type === 'fork' ? 'forks' : (type === 'package' ? 'packages' : 'plugins'))
        : (view === 'assistant' ? 'assistant' : 'launch');
    }
  }

  selectCatalogArtifact(artifact) {
    this.setState({ artifactId: artifact.id, catalogType: artifact.type, catalogScope: 'all' });
    if (typeof window !== 'undefined') {
      window.location.hash = artifact.type === 'package'
        ? artifact.pageRoute.slice(1)
        : (artifact.type === 'fork' ? 'forks' : 'plugins');
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

  async copyPackagePage(detail) {
    const base = typeof window !== 'undefined' && window.location && window.location.href
      ? window.location.href.split('#')[0]
      : '';
    const value = base + detail.page.route;
    try {
      if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error('Clipboard API unavailable');
      await navigator.clipboard.writeText(value);
      this.flash('Copied package page');
    } catch {
      this.flash('Clipboard unavailable. Use ' + detail.page.route);
    }
  }

  async installPackage(detail) {
    const versionId = this.state.packageVersionId || (this.state.savedVersions.find(item => item.state === 'ready') || {}).id;
    if (!this.state.sidecarConnected) return this.flash('Start the local launcher first');
    if (!versionId) return this.flash('Save a launch-ready Harness version first');
    if (!this.state.trustedPackageRecipes.some(item => item.slug === detail.slug && item.configured)) {
      return this.flash('Add a signed envelope and trust root for this package first');
    }
    this.setState({ packageInstallBusy: true, packageVersionId: versionId });
    try {
      await this.api('/api/v1/packages/install', {
        method: 'POST',
        body: JSON.stringify({ package_slug: detail.slug, version_id: versionId, profile: 'web' })
      });
      await this.refreshStatus(true);
      this.flash('Package verified, tested, and saved');
    } catch (error) {
      await this.refreshStatus(true);
      this.flash(error.message);
    } finally {
      this.setState({ packageInstallBusy: false });
    }
  }

  async installCertifiedPackage(recipe) {
    const versionId = (this.state.savedVersions.find(item => item.state === 'ready') || {}).id;
    if (!versionId) return this.flash('Save a launch-ready Harness version first');
    if (!this.state.sandbox.ready) return this.flash(this.state.sandbox.reason || 'Apptainer isolation is required');
    this.setState({ packageInstallBusy: true });
    try {
      await this.api('/api/v1/packages/install', {
        method: 'POST',
        body: JSON.stringify({ package_slug: recipe.slug, version_id: versionId, profile: 'web' })
      });
      await this.refreshStatus(true);
      this.flash('Certified package tested and installed');
    } catch (error) {
      await this.refreshStatus(true);
      this.flash(error.message);
    } finally {
      this.setState({ packageInstallBusy: false });
    }
  }

  async saveCatalogConfiguration(detail) {
    const versionId = this.state.packageVersionId || (this.state.savedVersions.find(item => item.state === 'ready') || {}).id;
    if (!this.state.sidecarConnected) return this.flash('Start the local launcher first');
    if (!versionId) return this.flash('Save a launch-ready Harness version first');
    const recipeConfigured = !!detail.catalogPackage && this.state.trustedPackageRecipes.some(
      item => item.slug === detail.slug && item.configured
    );
    this.setState({ configurationBusy: true, packageVersionId: versionId });
    try {
      const payload = {
        name: detail.name + ' configuration',
        description: 'Saved from the bounded DSH Forge catalog snapshot.',
        version_id: versionId,
        package_slug: recipeConfigured ? detail.slug : null,
        selections: [{ type: detail.type, id: detail.id }],
        launch: {
          surface: 'web', profile: 'web', task: '', port: 'auto', open_browser: false,
          network: 'host', resources: { gpu: 'none' }
        },
        draft: !recipeConfigured
      };
      await this.api('/api/v1/configurations', { method: 'POST', body: JSON.stringify(payload) });
      await this.refreshStatus(true);
      this.flash(recipeConfigured ? 'Configuration saved' : 'Draft saved; compose and sign it before run');
    } catch (error) {
      this.flash(error.message);
    } finally {
      this.setState({ configurationBusy: false });
    }
  }

  async runConfiguration(configuration) {
    if (!configuration.runtime || !configuration.runtime.runnable) {
      return this.flash((configuration.runtime && configuration.runtime.reason) || 'Configuration is not ready');
    }
    this.setState({ configurationBusy: true });
    try {
      const cell = await this.api('/api/v1/configurations/run', {
        method: 'POST', body: JSON.stringify({ id: configuration.id })
      });
      await this.refreshStatus(true);
      this.setState({ view: 'launch', selectedCell: cell.id, inspectorTab: 'logs' });
      if (typeof window !== 'undefined') window.location.hash = 'launch';
      this.flash('Configuration started inside Apptainer');
    } catch (error) {
      this.flash(error.message);
    } finally {
      this.setState({ configurationBusy: false });
    }
  }

  async copyText(value, success = 'Copied command') {
    try {
      if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error('Clipboard API unavailable');
      await navigator.clipboard.writeText(value);
      this.flash(success);
    } catch {
      this.flash('Clipboard unavailable. Copy the displayed command manually.');
    }
  }

  async previewLocalProfile(profile) {
    if (!this.state.sidecarConnected) return this.flash('Start the local launcher first');
    const tree = this.tree(this.state.treeId);
    if (!tree.id || tree.trust === 'foreign' || tree.launchability !== 'ready') {
      return this.flash('Select a launch-ready local DSH version');
    }
    const spec = {
      profile_id: profile.id,
      tree_id: tree.id,
      task: profile.surface === 'headless' ? this.state.profileTask : '',
      port: 'auto',
      open_browser: profile.surface === 'web'
    };
    this.setState({ profileBusy: true });
    try {
      const previewData = await this.api('/api/v1/profiles/preview', {
        method: 'POST', body: JSON.stringify(spec)
      });
      this.setState({ preview: 'profile', previewData, pendingProfile: spec });
    } catch (error) {
      this.flash(error.message);
    } finally {
      this.setState({ profileBusy: false });
    }
  }

  async startLocalProfile() {
    const spec = this.state.pendingProfile;
    if (!spec) return this.flash('Choose a detected profile first');
    const pendingWindow = spec.open_browser ? window.open('about:blank', '_blank') : null;
    this.setState({ profileBusy: true });
    try {
      const cell = await this.api('/api/v1/profiles/run', {
        method: 'POST', body: JSON.stringify(spec)
      });
      this.setState({ preview: null, previewData: null, pendingProfile: null, selectedCell: cell.id });
      await this.refreshStatus(true);
      this.flash('Started local profile ' + cell.profile + ' on the host');
      if (pendingWindow) this.openCell(cell, pendingWindow);
    } catch (error) {
      if (pendingWindow) pendingWindow.close();
      this.flash(error.message);
    } finally {
      this.setState({ profileBusy: false });
    }
  }

  async refreshAssistantUrl(cells = this.state.cells) {
    const assistant = [...cells].reverse().find(cell => cell.purpose === 'forge-assistant' && cell.open_ready);
    if (!assistant || assistant.id === this.state.assistantCellId && this.state.assistantUrl) return;
    try {
      const payload = await this.api('/api/v1/cells/' + encodeURIComponent(assistant.id) + '/open-url');
      this.setState({ assistantCellId: assistant.id, assistantUrl: payload.url });
    } catch {}
  }

  async startAssistant() {
    const versionId = this.state.assistantVersionId || (this.state.savedVersions.find(item => item.state === 'ready') || {}).id;
    if (!this.state.sidecarConnected) return this.flash('Start the local launcher first');
    if (!versionId) return this.flash('Save a launch-ready Harness version first');
    if (!this.state.sandbox.ready) return this.flash(this.state.sandbox.reason || 'Apptainer isolation is required');
    this.setState({ assistantBusy: true, assistantVersionId: versionId, assistantUrl: '' });
    try {
      const cell = await this.api('/api/v1/assistant/start', {
        method: 'POST', body: JSON.stringify({ version_id: versionId })
      });
      this.setState({ assistantCellId: cell.id });
      await this.refreshStatus(true);
      this.flash('Forge Assistant is starting in an isolated Harness');
    } catch (error) {
      this.flash(error.message);
    } finally {
      this.setState({ assistantBusy: false });
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

  usingCatalogStore(state = this.state) {
    if (!(state.sidecarConnected && state.catalogStore && state.catalogStore.available)) return false;
    const counts = state.catalogStore.counts;
    return !counts || Number(counts[state.catalogType] || 0) > 0;
  }

  catalogQueryKey(state = this.state) {
    return JSON.stringify([
      state.query.trim(), state.catalogType, state.catalogScope,
      state.catalogSort, !!state.knownLicenseOnly
    ]);
  }

  /** Fetch one page from the imported catalog store. */
  async refreshCatalog({ append = false } = {}) {
    if (!this.usingCatalogStore()) return;
    const s = this.state;
    const key = this.catalogQueryKey(s);
    const sortMap = { recommended: s.query.trim() ? 'relevance' : 'rank', stars: 'stars', recent: 'recent', name: 'name' };
    const parameters = new URLSearchParams();
    if (s.query.trim()) parameters.set('q', s.query.trim());
    parameters.set('type', s.catalogType);
    parameters.set('sort', sortMap[s.catalogSort] || 'relevance');
    parameters.set('limit', '50');
    if (s.catalogScope === 'featured') parameters.set('featured', '1');
    if (s.knownLicenseOnly) parameters.set('licensed', '1');
    if (append && s.storeCursor) parameters.set('cursor', s.storeCursor);
    this.setState({ storeLoading: true, storeError: '' });
    try {
      const page = await this.api('/api/v1/catalog/search?' + parameters.toString());
      // A slower reply for an older query must not overwrite the current one.
      if (this.catalogQueryKey() !== key) return;
      const research = page.research || {};
      const mapped = (page.artifacts || []).map(record => mapCatalogRecord({
        ...record,
        hidden_gem: research[record.artifact_id] || null
      }));
      this.setState({
        storeArtifacts: append ? [...this.state.storeArtifacts, ...mapped] : mapped,
        storeTotal: page.total || 0,
        storeCursor: page.next_cursor || '',
        storeGeneration: page.generation || 0,
        storeLoading: false
      });
    } catch (error) {
      if (this.catalogQueryKey() !== key) return;
      this.setState({ storeLoading: false, storeError: error.message, storeArtifacts: append ? this.state.storeArtifacts : [] });
    }
  }

  /** Coalesce typing into one request. */
  scheduleCatalogRefresh() {
    if (!this.usingCatalogStore()) return;
    if (this._catalogTimer) clearTimeout(this._catalogTimer);
    this._catalogTimer = setTimeout(() => {
      this._catalogTimer = null;
      this.setState({ storeCursor: '' });
      this.refreshCatalog();
    }, 180);
  }

  applyStatus(status) {
    const trees = Array.isArray(status.trees) ? status.trees : [];
    const profiles = Array.isArray(status.profiles) ? status.profiles : [];
    const current = trees.some(t => t.id === this.state.treeId) ? this.state.treeId : (trees[0] ? trees[0].id : '');
    const cells = Array.isArray(status.cells) ? status.cells : [];
    const selectedCell = cells.some(c => c.id === this.state.selectedCell) ? this.state.selectedCell : (cells[0] ? cells[0].id : null);
    this.setState({
      sidecarConnected: true, statusLoaded: true, trees, treeId: current,
      cells, selectedCell,
      savedVersions: Array.isArray(status.saved_versions) ? status.saved_versions : [],
      trustedPackageRecipes: Array.isArray(status.trusted_package_recipes) ? status.trusted_package_recipes : [],
      packageInstallations: Array.isArray(status.package_installations) ? status.package_installations : [],
      configurations: Array.isArray(status.configurations) ? status.configurations : [],
      profiles,
      catalogProfileId: profiles.some(profile => profile.id === this.state.catalogProfileId)
        ? this.state.catalogProfileId
        : ((profiles.find(profile => profile.name === 'web') || profiles[0] || {}).id || ''),
      versionsDirectory: status.versions_directory || this.state.versionsDirectory,
      suggestedPort: status.suggested_port || this.state.suggestedPort,
      coverageGaps: Array.isArray(status.coverage_gaps) ? status.coverage_gaps : [],
      credentials: Array.isArray(status.credentials) ? status.credentials : [],
      sandbox: status.sandbox || this.state.sandbox,
      catalogStore: status.catalog_store || { available: false }
    });
    // An imported corpus replaces the embedded inventory for artifact types it
    // contains. Missing types keep their small offline snapshot.
    if (this.usingCatalogStore() && !this.state.storeArtifacts.length && !this.state.storeLoading) {
      this.refreshCatalog();
    }
  }

  async refreshStatus(silent = false) {
    if (typeof fetch === 'undefined' || typeof location === 'undefined' || !/^https?:$/.test(location.protocol)) {
      this.setState({ statusLoaded: true, sidecarConnected: false });
      return;
    }
    try {
      const status = await this.api('/api/v1/status');
      this.applyStatus(status);
      await this.refreshAssistantUrl(Array.isArray(status.cells) ? status.cells : []);
    } catch (error) {
      this.setState({ statusLoaded: true, sidecarConnected: false, cells: [] });
      if (!silent) this.flash(error.message);
    }
  }

  async saveLocalVersion() {
    const path = this.state.versionPath.trim();
    if (!path) return this.flash('Enter the directory containing a local Harness checkout');
    this.setState({ versionBusy: true });
    try {
      const status = await this.api('/api/v1/scan', {
        method: 'POST', body: JSON.stringify({ roots: [path] })
      });
      this.applyStatus(status);
      this.setState({ versionPath: '', versionFormOpen: false });
      this.flash('Local version saved; review its detection status');
    } catch (error) {
      this.flash(error.message);
    } finally {
      this.setState({ versionBusy: false });
    }
  }

  async rescanVersions(silent = false) {
    this.setState({ versionBusy: true });
    try {
      this.applyStatus(await this.api('/api/v1/scan', { method: 'POST', body: '{}' }));
      if (!silent) this.flash('Local versions refreshed');
    } catch (error) {
      if (!silent) this.flash(error.message);
    } finally {
      this.setState({ versionBusy: false });
    }
  }

  async forgetLocalVersion(version) {
    this.setState({ versionBusy: true });
    try {
      const status = await this.api('/api/v1/versions/remove', {
        method: 'POST', body: JSON.stringify({ id: version.id })
      });
      this.applyStatus(status);
      this.flash('Version forgotten; source files were not changed');
    } catch (error) {
      this.flash(error.message);
    } finally {
      this.setState({ versionBusy: false });
    }
  }

  async saveVersionSettings(version, launch) {
    this.setState({ versionBusy: true });
    try {
      const status = await this.api('/api/v1/versions/settings', {
        method: 'POST',
        body: JSON.stringify({
          id: version.id,
          launch: {
            open_browser: !!launch.open_browser,
            gpu: launch.resources && launch.resources.gpu === 'allocated' ? 'allocated' : 'none'
          }
        })
      });
      this.applyStatus(status);
      this.setState({ versionSettingsId: null });
      this.flash('Launch preferences saved');
    } catch (error) {
      this.flash(error.message);
    } finally {
      this.setState({ versionBusy: false });
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
    if (!version.treeId) return this.flash('That version is not available on this machine');
    const launch = version.launchSettings || {
      surface: 'web', profile: 'tui-min', port: 'auto', open_browser: false,
      home_mode: 'fresh', workspace: 'managed', network: 'host', resources: { gpu: 'none' }
    };
    const pendingWindow = launch.open_browser ? window.open('about:blank', '_blank') : null;
    try {
      const cell = await this.api('/api/v1/cells', { method: 'POST', body: JSON.stringify({
        tree_id: version.treeId,
        surface: 'web',
        profile: launch.profile || 'tui-min',
        port: 'auto',
        open_browser: !!launch.open_browser,
        home_mode: 'fresh',
        workspace: 'managed',
        network: 'host',
        resources: { gpu: launch.resources && launch.resources.gpu === 'allocated' ? 'allocated' : 'none' }
      }) });
      await this.refreshStatus(true);
      this.setState({ selectedCell: cell.id, inspectorTab: 'logs' });
      await this.inspectCell(cell, 'logs');
      this.flash('Launched ' + version.version + ' on port ' + cell.port);
      if (pendingWindow) this.openCell(cell, pendingWindow);
    } catch (error) {
      if (pendingWindow) pendingWindow.close();
      this.flash(error.message);
    }
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
    const savedTreeIds = new Set(s.savedVersions.flatMap(item => item.tree_ids || []));
    const localVersionCard = (tree, saved = null) => {
      const canLaunch = !!tree && !!sandbox.ready && tree.trust !== 'foreign' && tree.launchability === 'ready';
      const launchSettings = (saved && saved.launch) || {
        surface: 'web', profile: 'tui-min', port: 'auto', open_browser: false,
        home_mode: 'fresh', workspace: 'managed', network: 'host', resources: { gpu: 'none' }
      };
      const gpuMode = launchSettings.resources && launchSettings.resources.gpu === 'allocated' ? 'allocated' : 'none';
      const status = !tree
        ? (saved.state === 'missing' ? 'Folder missing' : 'Harness not found')
        : (canLaunch ? 'Ready' : (!sandbox.ready ? 'Setup required' : 'Unavailable'));
      return {
        id: saved ? saved.id : tree.id,
        name: tree ? tree.name : 'Saved directory',
        version: tree ? tree.version : 'No version detected',
        tag: tree && tree.git ? tree.git.branch : (tree ? tree.kind : 'saved path'),
        commit: tree && tree.git ? tree.git.sha : '—',
        treeId: tree && tree.id,
        installPath: saved ? saved.path : tree.path,
        originLabel: saved && saved.source === 'auto' ? 'found automatically' : (saved ? 'added manually' : 'found for this session'),
        launchSettings,
        launchSummary: 'Auto port · new session' + (gpuMode === 'allocated' ? ' · GPU' : ''),
        status,
        statusColor: canLaunch ? OK : WARN,
        buttonLabel: canLaunch ? 'Launch' : (!tree ? 'Unavailable' : (!sandbox.ready ? 'Setup required' : 'Unavailable')),
        disabled: !canLaunch,
        buttonCursor: canLaunch ? 'pointer' : 'not-allowed',
        buttonBg: canLaunch ? 'oklch(0.34 0.08 155)' : 'oklch(0.25 0.01 255)',
        buttonBorder: canLaunch ? 'oklch(0.52 0.13 155)' : BORDER,
        showSettings: !!saved,
        settingsOpen: !!saved && s.versionSettingsId === saved.id,
        showForget: !!saved && (saved.source !== 'auto' || saved.state === 'missing'),
        openBrowser: !!launchSettings.open_browser,
        gpuMode,
        launch: () => this.quickLaunch({
          version: tree && tree.version,
          treeId: tree && tree.id,
          launchSettings
        }),
        toggleSettings: () => saved && this.setState({
          versionSettingsId: s.versionSettingsId === saved.id ? null : saved.id
        }),
        toggleOpenBrowserSetting: () => saved && this.saveVersionSettings(saved, {
          ...launchSettings,
          open_browser: !launchSettings.open_browser
        }),
        setGpuMode: event => saved && this.saveVersionSettings(saved, {
          ...launchSettings,
          resources: { gpu: event.target.value }
        }),
        forget: () => saved && this.forgetLocalVersion(saved)
      };
    };
    const savedCards = s.savedVersions.map(saved => localVersionCard(saved.primary_tree, saved));
    const sessionCards = s.trees
      .filter(tree => tree.trust !== 'foreign' && !savedTreeIds.has(tree.id))
      .map(tree => localVersionCard(tree));
    const versions = [...savedCards, ...sessionCards];
    const installVersion = s.savedVersions.find(item => item.state === 'ready');
    const certifiedPackages = s.trustedPackageRecipes.map(recipe => ({
      ...recipe,
      displayName: recipe.name || recipe.slug,
      versionLabel: recipe.version ? 'v' + recipe.version : 'signed manifest',
      componentLabel: recipe.component_count + (recipe.component_count === 1 ? ' component' : ' components'),
      reviewLabel: recipe.reviewer ? 'Reviewed by ' + recipe.reviewer : 'Curator reviewed',
      disabled: !s.sidecarConnected || !sandbox.ready || !installVersion || s.packageInstallBusy,
      buttonLabel: s.packageInstallBusy ? 'Testing…' : 'Verify, test & install',
      install: () => this.installCertifiedPackage(recipe)
    }));
    const selectedProfileTree = this.tree(s.treeId);
    const profileTreeReady = !!selectedProfileTree.id && selectedProfileTree.trust !== 'foreign' && selectedProfileTree.launchability === 'ready';
    const localProfiles = s.profiles.map(profile => {
      const oneClick = profile.launchability === 'one-click';
      const runnable = s.sidecarConnected && profileTreeReady && !s.profileBusy;
      const headless = profile.surface === 'headless';
      return {
        ...profile,
        oneClick,
        headless,
        dependencyLabel: profile.dependencies.length
          ? profile.dependencies.length + (profile.dependencies.length === 1 ? ' plugin' : ' plugins')
          : 'base bundles only',
        bundleLabel: profile.bundles.length + (profile.bundles.length === 1 ? ' bundle' : ' bundles'),
        task: s.profileTask,
        setTask: event => this.setState({ profileTask: event.target.value.slice(0, 20000) }),
        disabled: oneClick ? !runnable || (headless && !s.profileTask.trim()) : false,
        buttonLabel: oneClick ? (s.profileBusy ? 'Preparing…' : (headless ? 'Review task run' : 'Review & run')) : 'Copy terminal command',
        buttonBorder: oneClick ? 'oklch(0.52 0.13 155)' : 'oklch(0.42 0.07 235)',
        buttonBg: oneClick ? 'oklch(0.32 0.07 155)' : 'oklch(0.27 0.035 235)',
        run: () => oneClick ? this.previewLocalProfile(profile) : this.copyText(profile.command, 'Copied profile command')
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
        cloneDisabled: !!c.profile_id,
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

    const storeActive = this.usingCatalogStore(s);
    const queryTerms = s.query.trim().toLowerCase().split(/\s+/).filter(Boolean);
    // The store already applied the query, filters, and sort, so its page is
    // used as-is. Without a store the embedded snapshot is filtered here.
    const embeddedFiltered = CATALOG.filter(a => {
      const searchable = [a.slug, a.description, a.terms, a.type, a.language, a.licenseLabel].join(' ').toLowerCase();
      return queryTerms.every(term => searchable.includes(term)) &&
        a.type === s.catalogType &&
        (s.catalogScope === 'all' || a.featured) &&
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
    const filtered = storeActive ? s.storeArtifacts : embeddedFiltered;
    // Never keep an unrelated detail open after search/filter removes it.
    const detail = filtered.find(a => a.id === s.artifactId) || filtered[0] || {};
    const packageVersions = s.savedVersions.filter(item => item.state === 'ready').map(item => ({
      id: item.id,
      label: ((item.primary_tree || {}).version || 'Detected Harness') + ' · ' + item.path,
      selected: item.id === (s.packageVersionId || ((s.savedVersions.find(candidate => candidate.state === 'ready') || {}).id)),
    }));
    const selectedPackageVersion = s.packageVersionId || ((s.savedVersions.find(item => item.state === 'ready') || {}).id || '');
    const selectedCatalogProfile = s.profiles.find(profile => profile.id === s.catalogProfileId) || s.profiles[0] || null;
    const pluginInstallable = detail.type === 'plugin' && detail.package && detail.package.registry === 'npm';
    const pluginInstallCommand = pluginInstallable
      ? 'dsh plugin --profile ' + (selectedCatalogProfile ? selectedCatalogProfile.name : '<profile>') +
        ' add ' + detail.package.name + '@' + detail.package.version
      : '';
    const forkDownloadUrl = detail.type === 'fork' && detail.head_sha
      ? 'https://codeload.github.com/' + detail.slug + '/tar.gz/' + detail.head_sha
      : '';
    const forkDownloadCommand = forkDownloadUrl
      ? 'curl --fail --location --output ' + detail.name + '-' + detail.head_sha.slice(0, 12) + '.tar.gz ' + forkDownloadUrl
      : '';
    const recipeConfigured = !!detail.catalogPackage && s.trustedPackageRecipes.some(
      item => item.slug === detail.slug && item.configured
    );
    const latestPackageInstall = detail.catalogPackage
      ? [...s.packageInstallations].reverse().find(item => item.package && item.package.id === detail.slug)
      : null;
    const results = filtered.map(a => ({
      ...a, selected: a.id === detail.id,
      featuredLabel: a.hiddenGem && a.hiddenGem.candidate ? 'Hidden gem' : (a.featured ? 'Featured' : ''),
      accessibleLabel: 'Inspect ' + a.type + ' ' + a.slug + ', ' + a.starsLabel + ' GitHub stars',
      border: a.id === detail.id ? SELB : BORDER,
      bg: a.id === detail.id ? 'oklch(0.245 0.022 255)' : 'oklch(0.21 0.01 255)',
      select: () => this.selectCatalogArtifact(a)
    }));
    const detailRows = !detail.id ? [] : (detail.catalogPackage ? [
      { k: 'Package ID', v: detail.id, color: TXT },
      { k: 'Publisher', v: detail.publisher.name + ' · ' + detail.publisher.kind, color: TXT },
      { k: 'Composition', v: detail.kind + ' · ' + detail.components.length + ' pinned component(s)', color: BLUE },
      { k: 'Dedicated route', v: detail.page.route, color: MUTED },
      { k: 'Catalog digest', v: CATALOG_SNAPSHOT.package_catalog_digest, color: MUTED },
      { k: 'License', v: detail.licenseLabel + ' · component metadata', color: detail.licenseOk ? MUTED : WARN },
      { k: 'Trust', v: 'Metadata reviewed · not acquired or executed', color: WARN }
    ] : [
      { k: 'Artifact type', v: detail.type, color: TXT },
      { k: 'GitHub identity', v: detail.id, color: TXT },
      { k: 'Default branch', v: detail.default_branch || 'Not reported', color: TXT },
      { k: 'Captured commit', v: detail.base, color: TXT },
      { k: detail.type === 'fork' ? 'Fork source' : 'Source repository', v: detail.source_repository || 'Not reported', color: MUTED },
      ...(detail.divergence ? [
        {
          k: 'Source difference',
          v: detail.divergence.ahead_by + ' fork-only commit(s) · ' + detail.divergence.behind_by + ' behind · ' + detail.divergence.status,
          color: detail.divergence.ahead_by > 0 ? BLUE : WARN
        },
        {
          k: 'Changed files',
          v: detail.divergence.listed_file_count + ' listed' + (detail.divergence.files_truncated ? ' · provider limit reached' : ''),
          color: detail.divergence.files_truncated ? WARN : MUTED
        }
      ] : []),
      ...((detail.compatibility && detail.compatibility.changed_surfaces && detail.compatibility.changed_surfaces.length) ? [{
        k: 'Changed surfaces', v: detail.compatibility.changed_surfaces.join(' · '), color: MUTED
      }] : []),
      ...(detail.package ? [
        { k: 'Package', v: detail.package.name + '@' + detail.package.version, color: BLUE },
        { k: 'Registry', v: detail.package.registry + ' · exact version', color: MUTED },
        ...(detail.package.integrity ? [{ k: 'Integrity', v: detail.package.integrity, color: MUTED }] : [])
      ] : []),
      ...(detail.external_validation ? [{
        k: 'Marketplace validation',
        v: detail.external_validation.status + (detail.external_validation.code ? ' · ' + detail.external_validation.code : ''),
        color: detail.external_validation.status === 'valid' ? MUTED : WARN
      }] : []),
      ...(detail.hiddenGem ? [
        { k: 'Hidden-gem score', v: detail.hiddenGem.score + '/100 · rank H' + String(detail.hiddenGem.rank).padStart(2, '0'), color: BLUE },
        ...(detail.hiddenGem.quality_rank ? [{ k: 'Quality rank', v: 'Q' + String(detail.hiddenGem.quality_rank).padStart(2, '0') + ' before diversity', color: MUTED }] : []),
        ...(detail.hiddenGem.selection ? [{ k: 'Discovery lane', v: detail.hiddenGem.selection.capability_lane + ' · owner exposure ' + detail.hiddenGem.selection.owner_exposure_before, color: MUTED }] : []),
        { k: 'Visibility', v: detail.hiddenGem.visibility + ' · ' + detail.hiddenGem.confidence + ' confidence', color: MUTED }
      ] : []),
      ...(detail.installability ? [{ k: 'Installability', v: detail.installability + ' · external catalog claim', color: WARN }] : []),
      ...(detail.analysis_evidence ? [{ k: 'Evidence', v: detail.analysis_evidence.digest + ' · ' + detail.analysis_evidence.analyzer, color: MUTED }] : []),
      { k: 'Last push', v: detail.pushed_at || 'Not reported', color: MUTED },
      { k: 'License', v: detail.licenseLabel + ' · reported metadata', color: detail.licenseOk ? MUTED : WARN },
      { k: 'Trust', v: detail.divergence ? 'Commit-pinned source-diff metadata · not executed or security-reviewed' : 'Metadata only · not executed', color: WARN }
    ]);
    const detailCompatibilityText = detail.id
      ? ((detail.compatibility && detail.compatibility.summary) || 'No fork differences or runtime compatibility tests have been computed.')
      : '';
    const detailEvidenceText = detail.catalogPackage
      ? 'Directory inclusion was used only for discovery. Exact registry versions, integrity values, repository commits, and component roles are shown separately; no component combination has been reproduced.'
      : (detail.divergence
        ? 'Forge compared the exact source and fork commits through GitHub, listed ' + detail.divergence.listed_file_count + ' changed file(s), and extracted static compatibility and risk signals. ' + (detail.divergence.files_truncated ? 'GitHub reached its 300-file response limit, so the path inventory is partial. ' : '') + 'The repository was not cloned or executed; curator and sandbox review are still required.'
        : (detail.hiddenGem
        ? 'Forge discovery score ' + detail.hiddenGem.score + '/100 from ' + detail.hiddenGem.signals.map(signal => signal.id).join(', ') + '. ' + (detail.hiddenGem.selection ? 'Within a ' + detail.hiddenGem.selection.score_window + '-point quality window, the queue selected its ' + detail.hiddenGem.selection.capability_lane + ' capability lane after ' + detail.hiddenGem.selection.owner_exposure_before + ' prior item(s) from this owner. ' : '') + 'The ranking uses imported metadata only; Forge has not executed or security-reviewed this entry.'
        : (detail.curation
        ? detail.curation.evidence
        : (detail.external_validation
          ? 'The external marketplace classified this entry as ' + detail.external_validation.status + (detail.external_validation.code ? ' (' + detail.external_validation.code + ')' : '') + '. Forge verified the catalog digest but has not executed or security-reviewed the plugin.'
          : 'No source analysis has been computed. Repository descriptions and GitHub metadata are shown as claims, not verification.'))));
    const detailTaxonomy = detail.catalogPackage
      ? detail.taxonomy.join(' / ')
      : (detail.curation ? detail.curation.taxonomy.join(' / ') : ((detail.topics || []).slice(0, 8).join(' / ') || 'Unclassified'));
    const pluginCount = CATALOG.filter(a => a.type === 'plugin').length;
    const forkCount = CATALOG.filter(a => a.type === 'fork').length;
    const storeCounts = s.sidecarConnected && s.catalogStore.available && s.catalogStore.counts
      ? s.catalogStore.counts
      : null;
    const displayedPluginCount = storeCounts && Number(storeCounts.plugin || 0) > 0
      ? Number(storeCounts.plugin)
      : pluginCount;
    const displayedForkCount = storeCounts && Number(storeCounts.fork || 0) > 0
      ? Number(storeCounts.fork)
      : forkCount;
    const forkCoverage = Array.isArray(s.catalogStore.coverage)
      ? s.catalogStore.coverage.find(item => item && item.source === 'github-rest/fork-network')
      : null;
    const coverageLabel = s.catalogType === 'fork' && forkCoverage
      ? (forkCoverage.status === 'complete'
        ? ' · complete network verified'
        : (Number(forkCoverage.descendant_count || 0) > 0
          ? ' · incomplete network (' + Number(forkCoverage.discovered_count || 0).toLocaleString('en-US')
            + ' visible · root reports ' + Number(forkCoverage.reported_count_after || 0).toLocaleString('en-US') + ' direct)'
          : ' · incomplete network (' + Number(forkCoverage.discovered_count || 0).toLocaleString('en-US')
            + ' of ' + Number(forkCoverage.reported_count_after || 0).toLocaleString('en-US') + ')'))
      : '';
    const emptyCopy = s.catalogType === 'package'
      ? {
          title: 'No community packages published yet',
          description: 'The versioned package schema and offline composer are available through the CLI. Publication, acquisition, installation, and execution are not connected, so no sample listings are fabricated.',
          action: 'Browse plugins',
          run: () => this.navigate('catalog', 'plugin')
        }
      : {
          title: 'No matching ' + (s.catalogType === 'plugin' ? 'plugins' : 'forks'),
          description: 'Try a name, author, capability, taxonomy term, or clear the current filters.',
          action: 'Clear filters',
          run: () => { this.setState({ query: '', knownLicenseOnly: false }); this.scheduleCatalogRefresh(); }
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
      showAssistant: s.view === 'assistant',
      goLaunch: () => this.navigate('launch'),
      goCatalog: () => this.navigate('catalog', 'plugin'),
      goAssistant: () => this.navigate('assistant'),
      modeLabel: s.sidecarConnected ? 'Local' : 'Preview',
      sidecarTitle: s.sidecarConnected ? 'Launcher connected' : 'Start the local launcher to manage versions',
      sidecarDot: s.sidecarConnected ? OK : WARN,
      sidecarAddress: typeof window !== 'undefined' && window.location.host ? window.location.host : '127.0.0.1:3090',
      sidecarState: s.sidecarConnected ? 'Connected' : 'Offline',
      launchTabBg: s.view === 'launch' ? 'oklch(0.3 0.02 255)' : 'transparent',
      launchTabFg: s.view === 'launch' ? 'oklch(0.95 0.01 255)' : MUTED,
      launchTabBorder: s.view === 'launch' ? 'oklch(0.42 0.03 255)' : 'transparent',
      catalogTabBg: s.view === 'catalog' ? 'oklch(0.3 0.02 255)' : 'transparent',
      catalogTabFg: s.view === 'catalog' ? 'oklch(0.95 0.01 255)' : MUTED,
      catalogTabBorder: s.view === 'catalog' ? 'oklch(0.42 0.03 255)' : 'transparent',
      assistantTabBg: s.view === 'assistant' ? 'oklch(0.3 0.02 255)' : 'transparent',
      assistantTabFg: s.view === 'assistant' ? 'oklch(0.95 0.01 255)' : MUTED,
      assistantTabBorder: s.view === 'assistant' ? 'oklch(0.42 0.03 255)' : 'transparent',
      cellsSummary: s.cells.filter(c => c.state === 'running').length + ' running',
      snapshotAt: CATALOG_SNAPSHOT.fetched_at.slice(0, 16).replace('T', ' '),
      versions,
      localProfiles,
      hasLocalProfiles: localProfiles.length > 0,
      noLocalProfiles: localProfiles.length === 0,
      profileCountLabel: localProfiles.length + (localProfiles.length === 1 ? ' profile found' : ' profiles found'),
      hasVersions: versions.length > 0,
      noVersions: versions.length === 0,
      versionCountLabel: versions.length + (versions.length === 1 ? ' version found' : ' versions found'),
      certifiedPackages,
      hasCertifiedPackages: certifiedPackages.length > 0,
      noCertifiedPackages: certifiedPackages.length === 0,
      versionsDirectory: (s.versionsDirectory && s.versionsDirectory.path) || '~/dsh-versions',
      versionFormOpen: s.versionFormOpen,
      versionPath: s.versionPath,
      versionBusy: s.versionBusy,
      versionControlsDisabled: !s.sidecarConnected || s.versionBusy,
      addVersionLabel: s.versionFormOpen ? 'Close' : 'Add',
      toggleVersionForm: () => this.setState({
        versionFormOpen: !s.versionFormOpen,
        versionPath: s.versionFormOpen ? '' : s.versionPath
      }),
      setVersionPath: event => this.setState({ versionPath: event.target.value }),
      saveVersion: () => this.saveLocalVersion(),
      rescanVersions: () => this.rescanVersions(),
      communityTrees,
      hasCommunityTrees: communityTrees.length > 0,
      sandboxTitle: sandbox.ready ? 'Isolation ready' : 'Isolation setup required',
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
      treeCountLabel: s.trees.length + ' detected · evidence-based',
      coverageGap: s.coverageGaps.length
        ? s.coverageGaps.length + (s.coverageGaps.length === 1 ? ' folder needs attention' : ' folders need attention')
        : '',
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
      setQuery: e => { this.setState({ query: e.target.value }); this.scheduleCatalogRefresh(); },
      catalogSort: s.catalogSort,
      setCatalogSort: e => { this.setState({ catalogSort: e.target.value }); this.scheduleCatalogRefresh(); },
      knownLicenseOnly: s.knownLicenseOnly,
      toggleKnownLicense: e => { this.setState({ knownLicenseOnly: !!e.target.checked }); this.scheduleCatalogRefresh(); },
      repoTypes: [{ id: 'plugin', label: 'Plugins' }, { id: 'fork', label: 'Forks' }].map(f => ({
        ...f,
        count: storeCounts && Number(storeCounts[f.id] || 0) > 0
          ? Number(storeCounts[f.id])
          : CATALOG.filter(a => a.type === f.id).length,
        selected: s.catalogType === f.id,
        border: s.catalogType === f.id ? 'oklch(0.43 0.05 235)' : 'transparent',
        bg: s.catalogType === f.id ? 'oklch(0.29 0.035 235)' : 'transparent',
        color: s.catalogType === f.id ? 'oklch(0.88 0.035 235)' : MUTED,
        select: () => { this.navigate('catalog', f.id); this.scheduleCatalogRefresh(); }
      })),
      seedCount: CATALOG_SNAPSHOT.entries.length,
      pluginCount,
      forkCount,
      catalogCountLabel: displayedPluginCount.toLocaleString('en-US') + ' plugins · ' + displayedForkCount.toLocaleString('en-US') + ' forks',
      resultCount: (storeActive && s.storeTotal > results.length
        ? results.length + ' of ' + s.storeTotal.toLocaleString('en-US')
        : String(results.length)
      ) + ' ' + (s.catalogType === 'plugin' ? 'plugins' : (s.catalogType === 'fork' ? 'forks' : 'packages')),
      catalogSourceLabel: storeActive
        ? 'Imported catalog store' + coverageLabel
        : (s.sidecarConnected && s.catalogStore.available
          ? 'Embedded snapshot · no imported ' + s.catalogType + ' records'
          : (s.sidecarConnected ? 'Embedded snapshot · no store imported' : 'Embedded snapshot')),
      storeActive,
      storeLoading: s.storeLoading,
      storeError: s.storeError,
      hasStoreError: !!s.storeError,
      canLoadMore: storeActive && !!s.storeCursor && !s.storeLoading,
      loadMoreLabel: s.storeLoading ? 'Loading…' : 'Load more results',
      loadMore: () => this.refreshCatalog({ append: true }),
      sortExplanation: s.catalogSort === 'recommended'
        ? (storeActive
          ? 'Explainable hidden-gem priority · metadata only, not a security verdict'
          : (s.catalogType === 'plugin' ? 'Evidence-ranked · not a security verdict' : 'Captured snapshot order'))
        : (s.catalogSort === 'stars' ? 'GitHub stars · not a quality score' : (s.catalogSort === 'recent' ? 'Most recent repository push' : 'Alphabetical by owner / repository')),
      results,
      noResults: results.length === 0,
      hasDetail: !!detail.id,
      detail,
      detailPopularityLabel: detail.catalogPackage ? detail.components.length + ' pinned component(s)' : detail.starsLabel + ' GitHub stars',
      detailRows,
      detailTopics: (detail.topics || []).slice(0, 8),
      detailCompatibilityText,
      detailEvidenceText,
      detailTaxonomy,
      detailRisk: detail.catalogPackage
        ? detail.risk.level + ' risk · package candidate B' + String(detail.rank).padStart(2, '0')
        : (detail.hiddenGem
          ? detail.hiddenGem.confidence + ' · ' + detail.hiddenGem.gaps.length + ' evidence gap(s)'
          : (detail.curation ? detail.curation.security_risk + ' risk · static-review priority P' + String(detail.curation.rank).padStart(2, '0') : 'Unassessed')),
      isPackageDetail: !!detail.catalogPackage,
      isRepositoryDetail: !!detail.id && !detail.catalogPackage,
      isPluginDetail: detail.type === 'plugin',
      isForkDetail: detail.type === 'fork',
      packageComponents: detail.catalogPackage ? detail.components.map(component => ({
        ...component,
        name: component.package.name,
        version: component.package.version,
        registry: component.package.registry,
        repositoryUrl: component.repository.url + '/tree/' + component.repository.commit,
        packageUrl: component.package.url,
        shortCommit: component.repository.commit.slice(0, 12)
      })) : [],
      packageVersions,
      noPackageVersions: packageVersions.length === 0,
      selectedPackageVersion,
      setPackageVersion: event => this.setState({ packageVersionId: event.target.value }),
      installPackage: () => detail.catalogPackage ? this.installPackage(detail) : undefined,
      installDisabled: !detail.catalogPackage || !s.sidecarConnected || !sandbox.ready || !selectedPackageVersion || !recipeConfigured || s.packageInstallBusy,
      installLabel: s.packageInstallBusy ? 'Testing package…' : (latestPackageInstall && latestPackageInstall.state === 'ready' ? 'Install again' : 'Verify, test & install'),
      installStatus: latestPackageInstall
        ? (latestPackageInstall.state === 'ready' ? 'Ready · tested profile saved' : latestPackageInstall.detail)
        : (recipeConfigured ? 'Signed recipe configured locally' : 'Signed recipe required'),
      acquireLabel: detail.catalogPackage ? detail.acquisition.label : 'Acquire verified bytes',
      acquireReason: detail.catalogPackage ? detail.acquisition.reason : 'A schema-valid signed package record is required before acquisition.',
      sharePackagePage: () => detail.catalogPackage ? this.copyPackagePage(detail) : undefined,
      saveConfiguration: () => detail.id ? this.saveCatalogConfiguration(detail) : undefined,
      saveConfigurationDisabled: !detail.id || !s.sidecarConnected || !selectedPackageVersion || s.configurationBusy,
      saveConfigurationLabel: s.configurationBusy ? 'Saving…' : 'Save configuration',
      hasPackageLink: !!(detail.package && detail.package.url),
      detailPackageUrl: detail.package ? detail.package.url : '',
      detailPackageLabel: detail.package ? 'View ' + detail.package.registry + ' package ↗' : '',
      catalogProfiles: s.profiles.map(profile => ({
        ...profile,
        selected: profile.id === (selectedCatalogProfile && selectedCatalogProfile.id)
      })),
      selectedCatalogProfileId: selectedCatalogProfile ? selectedCatalogProfile.id : '',
      setCatalogProfile: event => this.setState({ catalogProfileId: event.target.value }),
      hasCatalogProfiles: s.profiles.length > 0,
      noCatalogProfiles: s.profiles.length === 0,
      pluginInstallable,
      pluginCommandUnavailable: detail.type === 'plugin' && !pluginInstallable,
      pluginInstallCommand,
      copyPluginInstall: () => pluginInstallCommand
        ? this.copyText(pluginInstallCommand, 'Copied exact plugin install command')
        : undefined,
      forkDownloadUrl,
      forkDownloadCommand,
      copyForkDownload: () => forkDownloadCommand
        ? this.copyText(forkDownloadCommand, 'Copied pinned download command')
        : undefined,
      hasForkDownload: !!forkDownloadUrl,
      hasDiscussionLink: !!detail.discussion_url,
      detailDiscussionUrl: detail.discussion_url || '',
      emptyTitle: emptyCopy.title,
      emptyDescription: emptyCopy.description,
      emptyActionLabel: emptyCopy.action,
      resetCatalogFilters: emptyCopy.run,
      copyRef: () => detail.id ? this.copyRepositoryRef(detail) : undefined,

      assistantVersions: packageVersions,
      selectedAssistantVersion: s.assistantVersionId || selectedPackageVersion,
      setAssistantVersion: event => this.setState({ assistantVersionId: event.target.value }),
      startAssistant: () => this.startAssistant(),
      assistantStartDisabled: !s.sidecarConnected || !sandbox.ready || !packageVersions.length || s.assistantBusy,
      assistantStartLabel: s.assistantBusy ? 'Starting…' : (s.assistantUrl ? 'Restart isolated assistant' : 'Start isolated assistant'),
      assistantReady: !!s.assistantUrl,
      assistantEmpty: !s.assistantUrl,
      assistantUrl: s.assistantUrl,
      openAssistant: () => {
        if (s.assistantUrl && typeof window !== 'undefined') window.open(s.assistantUrl, '_blank', 'noopener');
      },
      configurations: s.configurations.map(configuration => ({
        ...configuration,
        selectionLabel: (configuration.selections || []).length + ((configuration.selections || []).length === 1 ? ' selection' : ' selections'),
        versionLabel: ((s.savedVersions.find(item => item.id === configuration.version_id) || {}).primary_tree || {}).version || 'Missing version',
        statusLabel: configuration.status === 'draft' ? 'Draft' : ((configuration.runtime || {}).runnable ? 'Ready' : 'Needs setup'),
        statusColor: (configuration.runtime || {}).runnable ? OK : (configuration.status === 'draft' ? WARN : MUTED),
        run: () => this.runConfiguration(configuration),
        runDisabled: !(configuration.runtime || {}).runnable || s.configurationBusy,
        runLabel: (configuration.runtime || {}).runnable ? 'Run in Apptainer' : 'Not ready'
      })),
      noConfigurations: s.configurations.length === 0,

      previewOpen: !!s.preview,
      previewTitle: s.preview === 'profile'
        ? 'Confirm local profile — direct host process'
        : 'Confirm launch — exact argv and environment keys',
      previewConfirmLabel: s.preview === 'profile' ? 'Run local profile' : 'Start cell',
      idemKey: 'preview-' + (s.treeId || 'no-tree') + '-' + (s.port || 'headless'),
      previewLines,
      previewNotes,
      closePreview: () => this.setState({ preview: null, previewData: null, pendingProfile: null }),
      confirmPreview: () => s.preview === 'profile' ? this.startLocalProfile() : this.startCell(),

      toast: s.toast
    };
  }
}


Component.catalog = CATALOG;
Component.catalogSnapshot = CATALOG_SNAPSHOT;
return Component;
};
