#!/usr/bin/env python3
"""Tests for crate_info.py; run with `python3 -I scripts/test_crate_info.py`."""

import json
import pathlib
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import crate_info  # noqa: E402


class IndexPath(unittest.TestCase):
    def test_shards_by_length(self) -> None:
        cases = {
            "a": "1/a",
            "ab": "2/ab",
            "abc": "3/a/abc",
            "abcd": "ab/cd/abcd",
            "craftainer-crud": "cr/af/craftainer-crud",
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                self.assertEqual(crate_info.index_path(name), expected)

    def test_whole_name_is_lowercased(self) -> None:
        self.assertEqual(crate_info.index_path("MyCrate"), "my/cr/mycrate")
        self.assertEqual(crate_info.index_path("AB"), "2/ab")
        self.assertEqual(crate_info.index_path("ABC"), "3/a/abc")


class Manifest(unittest.TestCase):
    def test_name_override_order(self) -> None:
        manifest = {"package": {"name": "from-toml"}}
        self.assertEqual(crate_info.crate_name(manifest, {}), "from-toml")
        self.assertEqual(crate_info.crate_name(manifest, {"CARGO_PACKAGE": "pkg"}), "pkg")
        self.assertEqual(crate_info.crate_name(manifest, {"CARGO_PACKAGE": "pkg", "CRATE": "c"}), "c")

    def test_version_sources(self) -> None:
        literal = {"package": {"version": "1.2.3"}}
        inherited = {"package": {"version": {"workspace": True}}, "workspace": {"package": {"version": "0.0.0"}}}
        virtual = {"workspace": {"package": {"version": "0.4.0"}}}
        self.assertEqual(crate_info.crate_version(literal, {}), "1.2.3")
        self.assertEqual(crate_info.crate_version(inherited, {}), "0.0.0")
        self.assertEqual(crate_info.crate_version(virtual, {}), "0.4.0")
        self.assertEqual(crate_info.crate_version(inherited, {"RELEASE_VERSION": "9.9.9"}), "9.9.9")

    def test_index_url_base(self) -> None:
        self.assertEqual(crate_info.index_url("MyCrate", {}), "https://index.crates.io/my/cr/mycrate")
        env = {"CRATES_INDEX_URL": "file:///x/"}
        self.assertEqual(crate_info.index_url("abc", env), "file:///x/3/a/abc")


class HasVersion(unittest.TestCase):
    def lookup(self, lines: list[dict], version: str, not_yanked: bool = False) -> int:
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root, crate_info.index_path("MyCrate"))
            path.parent.mkdir(parents=True)
            path.write_text("\n".join(json.dumps(line) for line in lines) + "\n")
            url = crate_info.index_url("MyCrate", {"CRATES_INDEX_URL": pathlib.Path(root).as_uri()})
            return crate_info.has_version(url, version, not_yanked)

    def test_present_missing_and_yanked(self) -> None:
        lines = [{"vers": "1.0.0", "yanked": False}, {"vers": "1.1.0", "yanked": True}]
        self.assertEqual(self.lookup(lines, "1.0.0"), 0)
        self.assertEqual(self.lookup(lines, "2.0.0"), 1)
        self.assertEqual(self.lookup(lines, "1.1.0"), 0)
        self.assertEqual(self.lookup(lines, "1.1.0", not_yanked=True), 1)

    def test_unknown_crate_is_not_published(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            url = crate_info.index_url("MyCrate", {"CRATES_INDEX_URL": pathlib.Path(root).as_uri()})
            self.assertEqual(crate_info.has_version(url, "1.0.0", False), 1)


if __name__ == "__main__":
    unittest.main()
