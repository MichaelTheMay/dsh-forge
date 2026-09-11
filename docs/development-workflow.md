# Development and release workflow

DSH Forge uses `main` as its protected trunk:

| Branch | Purpose | Accepted changes |
| --- | --- | --- |
| `main` | Integration and release-ready history | Reviewed feature and fix pull requests with passing CI |

Feature work starts from the latest `main` branch and returns through a pull
request. Direct pushes and force pushes to the protected branch are not part of
the workflow. After a pull request passes CI and is merged, an owner creates an
annotated `v*` tag on the resulting `main` commit.

```bash
git switch main
git pull --ff-only origin main
git switch -c feature/short-description

# make the change and run the tests
git push -u origin feature/short-description
gh pr create --base main --head feature/short-description
```

## Continuous integration

`.github/workflows/checks.yml` runs for pull requests and pushes affecting
`main` (and the legacy `development` branch while it exists). This means the
same required check runs before a merge and once more on the merged commit. It
checks whitespace and Python syntax, validates the embedded catalog, runs the
JavaScript and Python suites, and builds the portable preview.

The protected-branch required check is:

```text
Launcher and catalog checks / checks
```

## Releases

`.github/workflows/release.yml` runs only for `v*` tags. It rejects a tag unless
it points to the current `main` tip, reruns the complete test suite, builds the
portable HTML preview and checksum, and publishes them as a GitHub Release.

```bash
git switch main
git fetch --prune --tags origin
git pull --ff-only origin main
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
test -z "$(git tag --list v0.1.0)"
git tag -a v0.1.0 -m "DSH Forge v0.1.0"
git push origin v0.1.0
```

Create the tag only after the release promotion is merged. If a version tag was
created early, remove that tag before reusing the version; do not force-move a
published release tag.

## Repository rules

The repository owner should make `main` the default branch and apply a ruleset
requiring pull requests, one approval, conversation resolution, and the strict
required check above. Block force pushes and deletion.
