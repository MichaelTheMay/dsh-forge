# Launch checklist

What is left before DSH Forge goes public, in order. Every step here needs a person: it creates an account, spends money, changes what is live, or is a judgement call. Everything else is built and tested on `feat/platform-v1`.

## 1. Land the work

- [ ] **Merge the daily-job fixes into `main`** (pull request #48). Until this lands, the daily catalog job keeps failing and the site serves the Nov 10 catalog.
- [ ] **Run the "Catalog research queue" workflow by hand** once #48 is merged, and confirm it publishes. Evidence accumulates over a few runs; the published queue should report policy `dsh-forge.hidden-gems/v3` within two or three days.
- [ ] **Review and merge `feat/platform-v1` into `main`.** Milestone pull requests #49 to #53 (and the launch-readiness one) are already merged into that branch and describe each part.
- [ ] **Redeploy production from `main`.** The live `/api/catalog` returns an error today while the same code on `main` works, so production is on an older build.
- [ ] **Close pull request #41.** Its tabs idea was rebuilt on current styling; the rest was superseded.

## 2. Check the things that could not be checked on the build machine

Apptainer was not installed there, so these were tested only against a stand-in.

- [ ] Install Apptainer, run `./scripts/install.sh`, start `dsh-forge`.
- [ ] Install and run one plugin and one fork from the catalog. Each should open as a tab.
- [ ] Save two configurations and run a comparison. **This is the one most likely to need a fix:** headless sandbox sessions start with no network, so a real run may not reach a model.

## 3. Label gem picks (10 minutes)

The gem system is scored against your judgement, and has none yet.

```bash
python3 -m gems label --picks gems/eval/data/gem-picks-2026-11-13.json
```

Open the address it prints, look at about 30 picks, and click "Gem" or "Not a gem" for each. Then:

```bash
python3 -m gems backtest-score --dataset gems/eval/data/backtest-2026-10-15.json --output /tmp/backtest-scored.json
python3 -m gems eval --picks gems/eval/data/gem-picks-2026-11-13.json \
  --backtest /tmp/backtest-scored.json --note "first human labels"
```

- [ ] Decide whether to publish the reviewers' critical notes. They are in `gems/reviews-private/` on the build machine only, because they criticise named third-party projects after a quick read.

## 4. Turn on sign-in and likes

Built and covered by tests with stand-in values; never run against real services. Details in [accounts.md](accounts.md).

- [ ] Create a GitHub OAuth app. Callback URL: `https://<your-domain>/api/auth/callback`.
- [ ] Add an Upstash Redis store to the Vercel project.
- [ ] Set `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET` and `DSH_FORGE_SESSION_SECRET` (`openssl rand -base64 48`) in Vercel, then redeploy.
- [ ] Sign in on the live site, like something, and confirm "Most liked" appears on Discover.

## 5. Name and domain

- [ ] Choose the new name.
- [ ] `python3 scripts/rename_product.py "New Name"` shows every place that changes; add `--apply` to do it, then `make check`. Only the name people read changes; the package, command, variables and installer identity stay.
- [ ] Buy and point the domain; update the OAuth callback URL and the site address in the README and docs.
- [ ] Set up a preview deployment for branches so changes can be seen before production.

## 6. Announce

- [ ] Record a short demo of Discover, a plugin page, recommendations and a comparison.
- [ ] Post.

## Known gaps to state honestly at launch

- Runs on Linux only. Windows and macOS can browse.
- The code reviewer is an AI model working from a checklist, and the interface says so.
- A pick is not a safety guarantee. Nothing is run during review.
- Recommendations use fixed rules and are not yet scored against anything.
