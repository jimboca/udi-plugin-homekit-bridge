# udi-plugin-homekit-bridge — lint/XML checks and Plugins release artifacts.
#
# Plugins release flow (clean tree; not detached HEAD):
#   1. Commit changes (bump VERSION in const.py only when cutting a new version).
#   2. `gmake release`     — tag v<VERSION> and push current branch + tag.
#                           Then in Plugins UI, edit the plugin and set Version to that exact VERSION.
#   3. `gmake beta`        — push HEAD to the `beta` branch and build $(NAME)-beta-<VERSION>.zip.
#   4. `gmake production`  — push HEAD to `production` and build $(NAME)-production-<VERSION>.zip.
# The track-specific zip files are the deliverables uploaded to Plugins.
#
# On FreeBSD use `gmake` (pkg install gmake). Do not cut releases unless asked.

PYTHON ?= python3
NAME = HomeKitBridge
GIT_REMOTE ?= origin
BRANCH_BETA ?= beta
BRANCH_PRODUCTION ?= production
XML_FILES = profile/*/*.xml

# Canonical version lives in const.py (nodes/__init__.py re-exports it).
VERSION_FILE = const.py

check: xml-check

xml-check:
	xmllint --noout $(XML_FILES)

help:
	@echo "Quality"
	@echo "  gmake check / xml-check   Validate profile XML"
	@echo ""
	@echo "Plugins release (clean tree; not detached HEAD)"
	@echo "  gmake release             Tag v\$$VERSION; push current branch + tag"
	@echo "  gmake beta                Push HEAD -> $(GIT_REMOTE)/$(BRANCH_BETA); build $(NAME)-$(BRANCH_BETA)-\$$VERSION.zip"
	@echo "  gmake production          Push HEAD -> $(GIT_REMOTE)/$(BRANCH_PRODUCTION); build $(NAME)-$(BRANCH_PRODUCTION)-\$$VERSION.zip"
	@echo "  gmake zip                 Ad-hoc local $(NAME).zip"
	@echo "                           After release/beta, set Version in Plugins UI to \$$VERSION"

clean:
	$(PYTHON) -c "import pathlib, shutil; r = pathlib.Path('.'); [shutil.rmtree(p, ignore_errors=True) for p in r.rglob('__pycache__') if p.is_dir()]; shutil.rmtree('.pytest_cache', ignore_errors=True)"
	rm -f $(NAME)*.zip

zip:
	rm -f $(NAME).zip
	zip -x@zip_exclude.lst -r $(NAME).zip *

beta:
	@set -e; \
	ROOT=$$(pwd); \
	VERSION=$$(sed -n 's/^VERSION = ["'"'"']\([^"'"'"']*\)["'"'"']$$/\1/p' "$$ROOT/$(VERSION_FILE)"); \
	test -n "$$VERSION" || { echo "Could not parse VERSION from $$ROOT/$(VERSION_FILE)"; exit 1; }; \
	test -z "$$(git -C "$$ROOT" status --porcelain)" || { \
		echo "Working tree is not clean. Commit or stash before make beta."; \
		git -C "$$ROOT" status --short; \
		exit 1; \
	}; \
	BRANCH=$$(git -C "$$ROOT" rev-parse --abbrev-ref HEAD); \
	if [ "$$BRANCH" = "HEAD" ]; then \
		echo "ERROR: detached HEAD. Checkout a branch, then run make beta."; \
		exit 1; \
	fi; \
	git -C "$$ROOT" push "$(GIT_REMOTE)" HEAD:"$(BRANCH_BETA)"; \
	echo "Pushed $$(git -C "$$ROOT" rev-parse --short HEAD) to $(GIT_REMOTE)/$(BRANCH_BETA)."; \
	ZIPFILE="$(NAME)-$(BRANCH_BETA)-$$VERSION.zip"; \
	rm -f "$$ZIPFILE"; \
	zip -x@zip_exclude.lst -r "$$ZIPFILE" * >/dev/null; \
	echo "Built $$ROOT/$$ZIPFILE for upload to Plugins."; \
	echo "Plugins UI action required: edit this plugin and set Version to $$VERSION."

production:
	@set -e; \
	ROOT=$$(pwd); \
	VERSION=$$(sed -n 's/^VERSION = ["'"'"']\([^"'"'"']*\)["'"'"']$$/\1/p' "$$ROOT/$(VERSION_FILE)"); \
	test -n "$$VERSION" || { echo "Could not parse VERSION from $$ROOT/$(VERSION_FILE)"; exit 1; }; \
	test -z "$$(git -C "$$ROOT" status --porcelain)" || { \
		echo "Working tree is not clean. Commit or stash before make production."; \
		git -C "$$ROOT" status --short; \
		exit 1; \
	}; \
	BRANCH=$$(git -C "$$ROOT" rev-parse --abbrev-ref HEAD); \
	if [ "$$BRANCH" = "HEAD" ]; then \
		echo "ERROR: detached HEAD. Checkout a branch, then run make production."; \
		exit 1; \
	fi; \
	git -C "$$ROOT" push "$(GIT_REMOTE)" HEAD:"$(BRANCH_PRODUCTION)"; \
	echo "Pushed $$(git -C "$$ROOT" rev-parse --short HEAD) to $(GIT_REMOTE)/$(BRANCH_PRODUCTION)."; \
	ZIPFILE="$(NAME)-$(BRANCH_PRODUCTION)-$$VERSION.zip"; \
	rm -f "$$ZIPFILE"; \
	zip -x@zip_exclude.lst -r "$$ZIPFILE" * >/dev/null; \
	echo "Built $$ROOT/$$ZIPFILE for upload to Plugins."

release:
	@set -e; \
	ROOT=$$(pwd); \
	VERSION=$$(sed -n 's/^VERSION = ["'"'"']\([^"'"'"']*\)["'"'"']$$/\1/p' "$$ROOT/$(VERSION_FILE)"); \
	test -n "$$VERSION" || { echo "Could not parse VERSION from $$ROOT/$(VERSION_FILE)"; exit 1; }; \
	test -z "$$(git -C "$$ROOT" status --porcelain)" || { \
		echo "Working tree is not clean. Commit or stash before make release."; \
		git -C "$$ROOT" status --short; \
		exit 1; \
	}; \
	BRANCH=$$(git -C "$$ROOT" rev-parse --abbrev-ref HEAD); \
	if [ "$$BRANCH" = "HEAD" ]; then \
		echo "ERROR: detached HEAD. Checkout your release branch, then run make release."; \
		exit 1; \
	fi; \
	if git -C "$$ROOT" rev-parse -q --verify "refs/tags/v$$VERSION" >/dev/null 2>&1; then \
		echo "Tag v$$VERSION already exists. Delete: git -C \"$$ROOT\" tag -d v$$VERSION"; \
		exit 1; \
	fi; \
	git -C "$$ROOT" tag -a "v$$VERSION" -m "Release $$VERSION"; \
	echo "Created annotated tag v$$VERSION."; \
	git -C "$$ROOT" push "$(GIT_REMOTE)" "$$BRANCH" "v$$VERSION"; \
	echo "Pushed $$BRANCH and v$$VERSION to $(GIT_REMOTE)."; \
	echo "Plugins UI action required: edit this plugin and set Version to $$VERSION."

.PHONY: check xml-check help clean zip beta production release
