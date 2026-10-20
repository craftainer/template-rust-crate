# template-rust-crate's implementation of template-base's release contract
# (docs/TEMPLATE.md, "Release: a Makefile contract"). release.yml sets
# RELEASE_VERSION / RELEASE_TAG / RELEASE_ARCH. A source crate is built once,
# on one arch. CARGO_PUBLISH (a repo variable; non-empty) turns `publish` on;
# unset skips it. Credentials: see scripts/release-publish.sh.

.PHONY: release-arches build sbom release-assets publish release-check finalize

# Package name from Cargo.toml, so an instance that renames the crate needs no
# change here. A virtual workspace sets CRATE (and CARGO_PACKAGE) itself.
CRATE ?= $(shell python3 -I -c 'import tomllib; print(tomllib.load(open("Cargo.toml", "rb"))["package"]["name"])')
CARGO_PACKAGE ?=
VERSION = $(or $(RELEASE_VERSION),$(shell python3 -I -c 'import tomllib; c = tomllib.load(open("Cargo.toml", "rb")); v = c["package"]["version"]; print(c["workspace"]["package"]["version"] if isinstance(v, dict) else v)'))
ASSET = dist/$(CRATE)-$(VERSION)

# renovate: datasource=docker depName=anchore/syft
SYFT_VERSION := v1.52.0

release-arches:
	@python3 -I -c 'import json; print(json.dumps(["amd64"]))'

# `cargo package` verifies the crate by building the unpacked sources. The
# release version is stamped into Cargo.toml/Cargo.lock only for the duration
# (release-stamped.sh), so the checkout stays clean. The runner's rustup
# honours rust-toolchain.toml, installing the pinned toolchain first.
build:
	@if command -v rustup >/dev/null 2>&1; then rustup toolchain install --profile minimal --no-self-update; fi
	rm -rf dist
	mkdir -p dist
	scripts/release-stamped.sh cargo package --locked --allow-dirty $(if $(CARGO_PACKAGE),-p $(CARGO_PACKAGE))
	cp target/package/$(CRATE)-$(VERSION).crate $(ASSET).crate

# Syft over the unpacked crate: its Cargo.toml and Cargo.lock list the
# dependencies the published source resolves to.
sbom:
	rm -rf dist/.sbom-src
	mkdir -p dist/.sbom-src
	tar -xzf $(ASSET).crate -C dist/.sbom-src --strip-components=1
	docker run --rm -u "$$(id -u):$$(id -g)" --tmpfs /tmp:rw,mode=1777 -e HOME=/tmp -v "$(CURDIR)/dist:/dist" \
		anchore/syft:$(SYFT_VERSION) "dir:/dist/.sbom-src" \
		--source-name $(CRATE) --source-version $(VERSION) -o "spdx-json=/$(ASSET).spdx.json"
	rm -rf dist/.sbom-src

release-assets:
	@set -e; for f in '$(ASSET).crate' '$(ASSET).spdx.json'; do \
		test -f "$$f" || { echo "missing release asset: $$f" >&2; exit 1; }; \
	done; ls dist

# Credentials and the dry-run switch: scripts/release-publish.sh.
publish:
ifeq ($(CARGO_PUBLISH),)
	@echo "CARGO_PUBLISH not set -- skipping publish."
else
	scripts/release-stamped.sh scripts/release-publish.sh
endif

# Runs once after the arch leg, inside the devcontainer; dist/ holds the
# downloaded .crate. See scripts/release-check.sh.
release-check:
	scripts/release-check.sh

# Nothing to combine: a source crate is built once.
finalize:
	@echo "Single source crate -- nothing to finalize."
