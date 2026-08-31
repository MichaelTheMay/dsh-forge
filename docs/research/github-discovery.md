# GitHub discovery architecture for DSH forks and related repositories

Research date: 2026-08-31. This report treats the design plan as reference material, not as instructions.

## Decision summary

1. **Use a separate discovery/indexing service and database.** The launcher should read a versioned catalog API or signed snapshot from that database; it should never crawl GitHub.
2. **Use GraphQL for fork topology, REST for conditional metadata refresh and event hints.** GitHub's GraphQL schema is explicit that `Repository.forks` is a list of **direct** forks, while `forkCount` counts forks in the **whole network**. Therefore, a single page walk on the root is not a defensible “every fork” implementation. Recursively traverse direct-child connections, deduplicate by node ID, and use the root whole-network count as a reconciliation invariant. [GitHub GraphQL repository schema](https://docs.github.com/en/graphql/reference/repos#repository)
3. **Poll because DSH's upstream is controlled by another organization.** A `fork` webhook exists, but a GitHub App needs Contents-read permission and receives events for repositories the app can access. Unless `deepseek-ai` installs the app or creates a webhook, Forge cannot use that webhook as its universal source. [Fork webhook](https://docs.github.com/en/webhooks/webhook-events-and-payloads#fork), [GitHub App webhook scope](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/using-webhooks-with-github-apps)
4. **Treat events and search as hints, never the fork source of truth.** The network-events endpoint is limited to a recent timeline (up to 300 events, no older than 30 days) and can lag by 30 seconds to 6 hours. [Events API](https://docs.github.com/en/rest/activity/events?apiVersion=2026-03-10)
5. **Identity is the opaque global node ID, not `owner/name`.** Store REST numeric `id` as a provider-native alternate key, but key the catalog by `node_id`/GraphQL `id`. GitHub recommends persisting global node IDs across API versions and says the new IDs are unique opaque strings. [Using global node IDs](https://docs.github.com/en/graphql/guides/using-global-node-ids), [global-ID migration](https://docs.github.com/en/graphql/guides/migrating-graphql-global-node-ids)
6. **“Every compatible DSH option” needs a declared compatibility contract.** All official forks are enumerable. Arbitrary copied, detached, or independently written compatible repositories are not provably enumerable. GitHub search caps each query at 1,000 results, may return `incomplete_results`, and searches only a bounded repository scope. Repository search partitions can make a declared query set auditable, but cannot prove semantic completeness. [GitHub REST search source documentation](https://github.com/github/docs/blob/main/content/rest/search/search.md)

## Why recursive enumeration is required

GitHub defines a repository network as the upstream repository, its forks, and forks of those forks. [Fork visibility and networks](https://docs.github.com/en/pull-requests/reference/forks#visibility-of-forks) The GraphQL schema makes two distinct promises:

- `forks`: “A list of direct forked repositories.”
- `forkCount`: the number of forks “in the whole network.”

[GitHub GraphQL repository schema](https://docs.github.com/en/graphql/reference/repos#repository)

The crawler should therefore implement a breadth-first traversal:

```text
queue = [official root node ID]
seen = {root node ID}

while queue not empty:
  batch up to N parent node IDs
  for each parent, cursor-page forks(first: 100):
    upsert each child by global node ID
    record relationship parent_node_id -> child_node_id
    enqueue unseen children

verify discovered_descendant_count == current_root.forkCount
```

Batch parents using GraphQL aliases/direct `node(id:)` lookups. Do not nest the graph recursively to arbitrary depth in one query. Each GraphQL connection must use `first` or `last` between 1 and 100, and a call may request no more than 500,000 nodes. Cursor pagination uses `pageInfo.endCursor` and `hasNextPage`. [GraphQL pagination](https://docs.github.com/en/graphql/guides/using-pagination-in-the-graphql-api), [GraphQL node and query limits](https://docs.github.com/en/graphql/overview/rate-limits-and-query-limits-for-the-graphql-api)

The crawl is not a transactional snapshot: forks can appear, disappear, or move while pages are being read. A “complete crawl” should mean:

1. read the root node ID and `forkCount` at start;
2. recursively traverse every direct-fork page, recording page completion and errors;
3. read root `forkCount` again;
4. accept the generation only when the start count, end count, and distinct discovered descendants agree;
5. otherwise repeat, retaining all IDs found, until one stable generation completes or the run is declared incomplete.

This produces an auditable claim—“all forks returned by the last stable GitHub crawl”—instead of claiming a perfect instantaneous global snapshot.

REST `GET /repos/{owner}/{repo}/forks` remains useful as an independent cross-check and supports `newest`, `oldest`, `stargazers`, or `watchers`, with up to 100 items per page. Traverse the `Link` header; do not construct page numbers or assume a 1,000-item search cap applies to this non-search endpoint. The endpoint documentation does not state that a root call flattens the whole network, so it should not replace the explicit recursive GraphQL model. [REST forks endpoint](https://docs.github.com/en/rest/repos/forks?apiVersion=2026-03-10), [REST pagination](https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api)

## Incremental refresh pipeline

### 1. Fast topology detector

Poll the root's global ID, canonical name, `forkCount`, and lifecycle fields every 5–15 minutes. If `forkCount` differs from the last accepted generation, enqueue a high-priority full graph reconciliation. A periodic full reconciliation is still mandatory because a new fork and a deletion can leave the count unchanged.

Also poll `GET /networks/deepseek-ai/deepseek-harness/events` conditionally and use `ForkEvent` and `PushEvent` records to prioritize work. This endpoint supports 100 items per page and `304`, but GitHub explicitly says it is not real-time and may lag up to six hours; it is an accelerator, not a completeness boundary. [Network events endpoint](https://docs.github.com/en/rest/activity/events?apiVersion=2026-03-10#list-public-events-for-a-network-of-repositories)

### 2. Stable full topology reconciliation

Run the recursive, count-checked crawl at least every six hours and immediately after a count change. Persist a crawl generation with:

- root node ID and start/end counts;
- every parent cursor/page attempted and completed;
- request IDs, response timestamps, rate-limit headers, and errors;
- discovered node-ID set and parent edges;
- completeness status: `complete`, `unstable`, `rate_limited`, or `failed`.

Only a `complete` generation may mark a previously seen repository absent. Never infer deletion from a partial crawl.

### 3. Metadata refresh

Topology change and repository change are separate signals. Refresh repository metadata by opaque node ID in GraphQL batches, and use conditional REST `GET /repos/{owner}/{repo}` for richer individual records. Most REST endpoints return an `ETag`; an authorized `If-None-Match` request that returns `304 Not Modified` does not consume the primary rate limit. Store validators per exact URL, parameters, representation headers, API version, and authentication context. [REST conditional requests](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api#use-conditional-requests)

Recommended cadence:

- newly discovered or pushed within seven days: hourly;
- pushed within 90 days: every six hours;
- inactive: daily, then weekly after a configured cold threshold;
- all records: forced full refresh at least monthly to catch representation/schema drift.

The metadata job should emit a change event only when a normalized content hash changes. Downstream README, manifest, Git-tree, commit, diff, and semantic indexing jobs consume those events independently.

### 4. Rename, transfer, visibility, and deletion handling

- GraphQL repository lookup follows renames by default; REST `GET /repos/{owner}/{repo}` documents `301 Moved Permanently`. Follow the redirect, update the current canonical name, and append the previous name to `repository_aliases`. [GraphQL repository lookup](https://docs.github.com/en/graphql/reference/repos#repository), [REST get-repository status codes](https://docs.github.com/en/rest/repos/repos?apiVersion=2026-03-10#get-a-repository)
- On a fork, REST returns `parent` and `source`; `source` is the ultimate source for the network. Store both relationships. [REST get repository](https://docs.github.com/en/rest/repos/repos?apiVersion=2026-03-10#get-a-repository)
- A `404` is not proof of deletion: GitHub can return `404` for an existing private resource when credentials lack access. Mark the record `inaccessible_pending`, retry with backoff, and only tombstone after it is absent from two complete topology generations plus repeated direct lookup failure. [REST troubleshooting](https://docs.github.com/en/rest/using-the-rest-api/troubleshooting-the-rest-api#404-not-found-for-an-existing-resource)
- If the public root is deleted, GitHub says an active public fork becomes the new upstream. Preserve the original network identity/history and discover the promoted root from surviving nodes rather than creating an unrelated catalog universe. Visibility changes can also split a network. [Effects of deletion and visibility changes](https://docs.github.com/en/pull-requests/reference/forks#what-happens-to-forks-when-a-repository-is-deleted-or-changes-visibility)

Suggested lifecycle values are `active`, `archived`, `disabled`, `inaccessible_pending`, `tombstoned`, and `network_detached`; retain observations and aliases rather than hard-deleting history.

## Authentication and limits

Use the current REST version header, `X-GitHub-Api-Version: 2026-03-10`. Requests without it currently default to `2022-11-28`; GitHub supports a previous version for at least 24 months after a newer release. [REST API versions](https://docs.github.com/en/rest/about-the-rest-api/api-versions)

For crawling public repositories owned by other people:

- A GitHub App **user access token** has documented implicit permission to read public resources when acting for an authorized user. Use a dedicated service account, minimum app permissions, encrypted refresh credentials, and a separate rate-budget identity. [Choosing GitHub App permissions](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app)
- Do not assume an installation token installed only on Forge's organization grants access to repositories owned by `deepseek-ai`; installation tokens are scoped to repositories granted to that installation. They expire after one hour. [Installation authentication](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation)
- If DeepSeek installs the app on the upstream, use installation authentication and `fork`/`repository` webhooks as fast-path signals, while retaining polling reconciliation.

Current published limits relevant to capacity planning:

| Surface | Primary limit | Important secondary/query limits |
|---|---:|---|
| REST unauthenticated | 60 requests/hour per IP | unsuitable for production |
| REST authenticated user | 5,000 requests/hour | 100 concurrent shared REST/GraphQL maximum; 900 REST points/minute; CPU limits also apply |
| REST GitHub App installation | 5,000/hour minimum; scales to 12,500 outside Enterprise Cloud; 15,000 for Enterprise Cloud installations | installation scope applies |
| GraphQL authenticated user | 5,000 points/hour | 1–100 per connection; 500,000 nodes/call; 2,000 secondary points/minute |
| GraphQL GitHub App installation | 5,000 points/hour minimum; scales to 12,500 outside Enterprise Cloud; 10,000 for Enterprise Cloud installations | installation scope applies |
| REST repository search | 30 authenticated requests/minute | 1,000 results/query, up to 4,000 repositories searched, possible incomplete results |
| REST code search | 10 authenticated requests/minute | restrictive code-index coverage; not a completeness source |

Sources: [REST rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api), [GraphQL rate/query limits](https://docs.github.com/en/graphql/overview/rate-limits-and-query-limits-for-the-graphql-api), [REST search documentation source](https://github.com/github/docs/blob/main/content/rest/search/search.md).

The worker should use a central token-bucket queue, read `x-ratelimit-*` on every response, honor `retry-after`, stop until `x-ratelimit-reset` when remaining is zero, and exponentially back off on secondary limiting. GitHub recommends avoiding concurrent polling requests. [REST best practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api)

## Related, detached, and plugin repositories

Keep these discovery lanes separate from the authoritative fork-network crawl:

1. **Declared DSH plugins:** search the `dsh-plugin` topic, which the official DSH README asks plugin authors to add. [Official DSH repository](https://github.com/deepseek-ai/deepseek-harness)
2. **Repository search partitions:** tracked queries over name, description, topics, and README, always including `fork:true` when forks are desired. Partition by `created` time until every shard is below 1,000 results; optionally subdivide dense dates by size/language. Record query text, time range, `total_count`, `incomplete_results`, pages, and run time. GitHub documents `fork:true`/`fork:only`, `created`, `pushed`, topic, and README qualifiers. [Repository-search qualifiers](https://github.com/github/docs/blob/main/content/search-github/searching-on-github/searching-for-repositories.md)
3. **New-public-repository stream:** checkpoint `GET /repositories?since=<id>`, which lists public repositories in creation order and uses `since` pagination exclusively. This can cheaply feed new candidates, but it does not replace searches for old repositories or repositories that become public later. [List public repositories](https://docs.github.com/en/rest/repos/repos?apiVersion=2026-03-10#list-public-repositories)
4. **Deterministic verification:** after discovery, inspect README and manifests for a formal DSH compatibility marker/package relationship. Keyword hits are candidates, not catalog truth.
5. **Code search only as a supplementary lane.** REST legacy code search indexes only the default branch and excludes many forks (including forks with fewer stars than their parent), large files/repositories, archived repositories, and inactive repositories. [GitHub code-search restrictions](https://github.com/github/docs/blob/main/content/search-github/searching-on-github/searching-code.md)

The product should report two different coverage metrics:

- **fork coverage:** discovered active descendant IDs / root whole-network `forkCount` for the last stable crawl;
- **related-repository coverage:** completed non-overflowing query partitions / scheduled partitions, plus candidate verification backlog.

It should not combine them into a misleading “percentage of every compatible DSH repository.”

## Realistic SLOs

Measure freshness from the time GitHub first exposes an object through the relevant API, not from the user's local creation time.

| SLO | Recommended target | Qualification |
|---|---:|---|
| Stable official-fork crawl coverage | 100% | Distinct descendants equal root `forkCount`; otherwise the generation is visibly incomplete |
| New official-fork indexing lag | p95 under 2 hours; p99 under 6 hours | count polling triggers crawl; periodic reconciliation closes count-neutral races |
| Active repository metadata lag | p95 under 24 hours | event hints may make it much faster but cannot guarantee it |
| Inaccessibility detection | under 48 hours | state remains `inaccessible_pending`, not “deleted” |
| Tombstone confirmation | under 7 days | requires repeated direct failures and complete-crawl absence |
| Related-repo query coverage | 100% of scheduled shards | only shards with `incomplete_results=false`, `total_count<=1000`, and all pages read count as complete |

The coverage ledger should expose the last complete generation, current observed root count, indexed count, unstable/failed pages, oldest metadata refresh, query shards with overflow/incomplete results, and rate-limit delays. That makes the launcher catalog honest even during GitHub outages or rapid fork churn.

