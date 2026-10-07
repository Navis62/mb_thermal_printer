"""Tests for the --prune and --force (refresh) options of the image scripts.

Run from the repository root:  python -m unittest discover -s tests
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import convert_images
import download_images_from_scryfall as download
from PIL import Image


def touch(path, content=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def card(name, cmc):
    return {"name": name, "image_url": "https://example.test/x.jpg", "cmc": float(cmc)}


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = self._tmp.name

    def bmp(self, cmc, name):
        return os.path.join(self.root, str(cmc), "converted_files", name + ".bmp")

    def write_list(self, cards):
        path = os.path.join(self.root, "creatures_image_urls.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cards, f)
        return path


class FindObsoleteBmpsTest(TempDirCase):
    def test_classifies_bmps(self):
        cards = [card("Grizzly Bears", 2), card("Fire // Ice", 3), card("Summon: Anima", 5)]
        for cmc, name in [(2, "Grizzly Bears"), (3, "Fire  Ice"), (5, "Summon Anima")]:
            touch(self.bmp(cmc, name))
        touch(self.bmp(2, "Left The List"))            # card no longer in the list
        touch(self.bmp(4, "Grizzly Bears"))            # card now has another CMC
        expected = ["2/converted_files/Left The List.bmp", "4/converted_files/Grizzly Bears.bmp"]
        if os.name != "nt":                            # ":" is not allowed in Windows file names
            touch(self.bmp(5, "Summon: Anima"))        # old file name, from before names were sanitised
            expected.append("5/converted_files/Summon: Anima.bmp")

        obsolete, total = download.find_obsolete_bmps(cards, self.root)
        self.assertEqual(total, 5 + (os.name != "nt"))
        self.assertEqual(sorted(os.path.relpath(p, self.root).replace("\\", "/") for p in obsolete),
                         sorted(expected))


class PruneTest(TempDirCase):
    def setUp(self):
        super().setUp()
        self.cards = [card(f"Card {i}", 2) for i in range(10)]
        for c in self.cards:
            touch(self.bmp(2, c["name"]))

    def prune(self, cards):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            removed = download.prune_obsolete_bmps(cards, self.root)
        return removed, out.getvalue()

    def test_removes_obsolete_bmps_only(self):
        touch(self.bmp(2, "Old Card"))
        removed, _ = self.prune(self.cards)
        self.assertEqual(removed, 1)
        self.assertFalse(os.path.exists(self.bmp(2, "Old Card")))
        self.assertTrue(all(os.path.exists(self.bmp(2, c["name"])) for c in self.cards))

    def test_nothing_to_remove(self):
        removed, out = self.prune(self.cards)
        self.assertEqual(removed, 0)
        self.assertIn("No obsolete", out)

    def test_refuses_to_delete_most_of_the_library(self):
        # An empty or truncated card list must not wipe the library
        removed, out = self.prune([])
        self.assertEqual(removed, 0)
        self.assertIn("Nothing was deleted", out)
        removed, _ = self.prune(self.cards[:2])        # 8 of 10 BMPs would go
        self.assertEqual(removed, 0)
        self.assertTrue(all(os.path.exists(self.bmp(2, c["name"])) for c in self.cards))

    def test_threshold_is_inclusive_at_half(self):
        removed, _ = self.prune(self.cards[:5])        # exactly 5 of 10: allowed
        self.assertEqual(removed, 5)


class DownloadForceTest(TempDirCase):
    def run_download(self, cards, **kwargs):
        json_file = self.write_list(cards)
        with mock.patch.object(download, "download_image", return_value="ok") as dl, \
                contextlib.redirect_stdout(io.StringIO()):
            failed = download.download_images_from_json(json_file, self.root, **kwargs)
        return failed, [c.args[0]["name"] for c in dl.call_args_list]

    def setUp(self):
        super().setUp()
        self.cards = [card("Converted", 2), card("Waiting", 2), card("New", 3)]
        touch(self.bmp(2, "Converted"))
        touch(os.path.join(self.root, "2", "Waiting.jpg"))

    def test_default_skips_converted_and_waiting_cards(self):
        failed, names = self.run_download(self.cards)
        self.assertEqual((failed, names), (0, ["New"]))

    def test_force_downloads_every_card_again(self):
        failed, names = self.run_download(self.cards, force=True)
        self.assertEqual(failed, 0)
        self.assertEqual(sorted(names), ["Converted", "New", "Waiting"])

    def test_prune_runs_before_downloading(self):
        touch(self.bmp(2, "Left The List"))
        self.run_download(self.cards, prune=True)
        self.assertFalse(os.path.exists(self.bmp(2, "Left The List")))
        self.assertTrue(os.path.exists(self.bmp(2, "Converted")))

    def test_without_prune_nothing_is_deleted(self):
        touch(self.bmp(2, "Left The List"))
        self.run_download(self.cards)
        self.assertTrue(os.path.exists(self.bmp(2, "Left The List")))


class ConvertForceTest(TempDirCase):
    def test_force_converts_again_files_that_already_have_a_bmp(self):
        os.makedirs(os.path.join(self.root, "2"))
        jpg = os.path.join(self.root, "2", "Bear.jpg")
        Image.new("RGB", (488, 680), (90, 90, 90)).save(jpg)
        touch(self.bmp(2, "Bear"), "old conversion")

        self.assertEqual(convert_images.find_pending(self.root), [])
        self.assertEqual(convert_images.find_pending(self.root, force=True), [jpg])

        with contextlib.redirect_stdout(io.StringIO()):
            failed = convert_images.convert_all(self.root, workers=1, force=True)
        self.assertEqual(failed, 0)
        with Image.open(self.bmp(2, "Bear")) as img:   # the placeholder was replaced by a real BMP
            self.assertEqual(img.mode, "1")


if __name__ == "__main__":
    unittest.main()
