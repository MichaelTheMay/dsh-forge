# Development and release workflow

DSH Forge uses two protected long-lived branches:

| Branch | Purpose | Accepted changes |
| --- | --- | --- |
| `development` | Integration branch and default pull-request target | Reviewed feature and fix pull requests with passing CI |
| `main` | Release-ready history only | Promotion pull requests from `development` |

Feature work starts from the latest `development` branch and returns through a
pull request. Direct pushes and force pushes to either protected branch are not
part of the workflow. A release is promoted with a `development` to `main` pull
request. After that pull request passes CI and is merged, an owner creates an
annotated `v*` tag on the resulting `main` commit.

```bash
git switch development
git pull --ff-only origin development
git switch -c feature/short-description

# make the change and run the tests
git push -u origin feature/short-description
gh pr create --base development --head feature/short-description
```

## Continuous integration

`.github/workflows/checks.yml` runs for pull requests and pushes affecting
`development` or `main`. This means the same required check runs before a merge
and once more on the merged commit. It checks whitespace and Python syntax,
validates the embedded catalog, runs the JavaScript and Python suites, and builds
the portable preview.

The protected-branch required check is:

```text
Launcher and catalog checks / checks
```

## Releases

`.github/workflows/release.yml` runs only for `v*` tags. It rejects a tag whose
commit is not contained in `main`, reruns the complete test suite, builds the
portable HTML preview and checksum, and publishes them as a GitHub Release.

```bash
git switch main
git pull --ff-only origin main
git tag -a v0.1.0 -m "DSH Forge v0.1.0"
git push origin v0.1.0
```

## Repository rules

The repository owner should make `development` the default branch and apply
rulesets to both long-lived branches. Require pull requests, one approval,
conversation resolution, and the strict required check above. Block force
pushes and deletion. For `main`, restrict the merge path to repository owners or
release maintainers so it remains release-only.
