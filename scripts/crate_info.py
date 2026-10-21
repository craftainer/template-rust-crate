#!/usr/bin/env python3
"""Answers "which crate, which version, where on the sparse index?" for the release tooling.

One implementation for the Makefile, release-check.sh, release-publish.sh and
the semver-checks hook, so the name lookup and the index layout can't drift.

Usage (run with `python3 -I`):
  crate_info.py name                 crate name
  crate_info.py version              RELEASE_VERSION, else the version in Cargo.toml
  crate_info.py index-url [name]     sparse-index URL of a crate (default: this one)
  crate_info.py has-version VERSION [--not-yanked]
                                     exit 0 if the index lists VERSION, 1 if not
                                     (crate unknown included), 2 if the index failed

Env: CRATE or CARGO_PACKAGE (override the name; a virtual workspace needs one),
RELEASE_VERSION, CRATES_INDEX_URL (default https://index.crates.io; a file://
URL works for tests).
"""

import json
import os
import sys
import tomllib
import urllib.error
import urllib.request

DEFAULT_INDEX = "https://index.crates.io"


def load_manifest(path: str = "Cargo.toml") -> dict:
    with open(path, "rb") as handle:
        return tomllib.load(handle)


def crate_name(manifest: dict, env: "os._Environ[str] | dict[str, str]") -> str:
    for key in ("CRATE", "CARGO_PACKAGE"):
        if env.get(key):
            return env[key]
    try:
        return manifest["package"]["name"]
    except KeyError:
        sys.exit("Cargo.toml has no [package] name (virtual workspace?): set CRATE or CARGO_PACKAGE")


def crate_version(manifest: dict, env: "os._Environ[str] | dict[str, str]") -> str:
    if env.get("RELEASE_VERSION"):
        return env["RELEASE_VERSION"]
    version = manifest.get("package", {}).get("version")
    if version is None or isinstance(version, dict):
        version = manifest.get("workspace", {}).get("package", {}).get("version")
    if not isinstance(version, str):
        sys.exit("no literal version in Cargo.toml's [package] or [workspace.package]")
    return version


def index_path(name: str) -> str:
    """Sparse-index path of a crate: the index lowercases the whole name."""
    name = name.lower()
    if len(name) <= 2:
        return f"{len(name)}/{name}"
    if len(name) == 3:
        return f"3/{name[0]}/{name}"
    return f"{name[:2]}/{name[2:4]}/{name}"


def index_url(name: str, env: "os._Environ[str] | dict[str, str]") -> str:
    base = (env.get("CRATES_INDEX_URL") or DEFAULT_INDEX).rstrip("/")
    return f"{base}/{index_path(name)}"


def has_version(url: str, version: str, not_yanked: bool) -> int:
    request = urllib.request.Request(url, headers={"User-Agent": "craftainer-release-tooling"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            body = response.read().decode()
    except urllib.error.HTTPError as error:
        if error.code in (404, 410):
            return 1
        print(f"index lookup failed: HTTP {error.code} for {url}", file=sys.stderr)
        return 2
    except (urllib.error.URLError, OSError) as error:
        if isinstance(getattr(error, "reason", None), FileNotFoundError) or isinstance(error, FileNotFoundError):
            return 1
        print(f"index lookup failed: {error}", file=sys.stderr)
        return 2
    for line in body.splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry["vers"] == version and not (not_yanked and entry["yanked"]):
            return 0
    return 1


def main(argv: list[str]) -> int:
    env = os.environ
    command = argv[0] if argv else ""
    if command == "name" and len(argv) == 1:
        print(crate_name(load_manifest(), env))
    elif command == "version" and len(argv) == 1:
        print(crate_version(load_manifest(), env))
    elif command == "index-url" and len(argv) in (1, 2):
        name = argv[1] if len(argv) == 2 else crate_name(load_manifest(), env)
        print(index_url(name, env))
    elif command == "has-version" and len(argv) in (2, 3):
        name = crate_name(load_manifest(), env)
        return has_version(index_url(name, env), argv[1], "--not-yanked" in argv[2:])
    else:
        print(__doc__, file=sys.stderr)
        return 64
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
