# One command that runs exactly what .github/workflows/checks.yml runs.
# Green here means green in CI.

.PHONY: check lint embed test-js test-py test-gems preview

export PYTHONDONTWRITEBYTECODE = 1

check: lint embed test-js test-py test-gems preview
	@echo "check: all green"

lint:
	git diff --check
	python3 -m compileall -q dsh_forge scripts tests $(wildcard gems)

# The catalog embedded in web/launcher.js must match the local snapshot.
# CI uses `git diff --exit-code`; comparing checksums gives the same answer
# on a working tree that has other uncommitted edits to that file.
embed:
	python3 scripts/ingest_package_catalog.py --check
	@before=$$(sha256sum web/launcher.js); \
	python3 scripts/embed_catalog.py >/dev/null; \
	after=$$(sha256sum web/launcher.js); \
	[ "$$before" = "$$after" ] || { echo "embed: web/launcher.js was out of date; review and commit it"; exit 1; }

test-js:
	node --test tests/catalog.test.cjs tests/auth.test.mjs tests/likes.test.mjs

test-py:
	python3 -m unittest discover -s tests -p 'test_*.py'

# The hidden-gem system has its own tests so it can be worked on alone.
test-gems:
	@if [ -f gems/tests/__init__.py ]; then python3 -m unittest discover -s gems/tests -t . -p 'test_*.py'; fi

preview:
	python3 scripts/package_preview.py dist/DSH_Forge_Launcher_Preview.html
