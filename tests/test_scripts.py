"""Unit tests for the data-preparation scripts (scripts/).

Run from the repository root:  python -m unittest discover -s tests
"""
import gzip
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import convert_images
import download_images_from_scryfall as download
import get_image_urls_from_scryfall as urls
import progress
from PIL import Image


def make_card(**overrides):
    """Return a minimal Scryfall card object for a legal, paper creature."""
    card = {
        "name": "Grizzly Bears",
        "type_line": "Creature — Bear",
        "layout": "normal",
        "cmc": 2.0,
        "games": ["paper", "mtgo"],
        "legalities": {"modern": "legal", "standard": "not_legal"},
        "image_uris": {"normal": "https://example.test/normal.jpg", "large": "https://example.test/large.jpg"},
    }
    card.update(overrides)
    return card


class IsValidCreatureTest(unittest.TestCase):
    def test_regular_creature(self):
        self.assertTrue(urls.is_valid_creature(make_card()))

    def test_artifact_creature_and_banned_card(self):
        self.assertTrue(urls.is_valid_creature(make_card(type_line="Artifact Creature — Golem")))
        self.assertTrue(urls.is_valid_creature(make_card(legalities={"modern": "banned"})))

    def test_non_creature(self):
        self.assertFalse(urls.is_valid_creature(make_card(type_line="Instant")))

    def test_tokens_and_other_fake_cards(self):
        for layout in ("token", "double_faced_token", "emblem", "art_series"):
            self.assertFalse(urls.is_valid_creature(make_card(layout=layout)), layout)

    def test_not_legal_anywhere(self):
        self.assertFalse(urls.is_valid_creature(make_card(legalities={"modern": "not_legal"})))
        self.assertFalse(urls.is_valid_creature(make_card(legalities={})))

    def test_arena_only(self):
        self.assertFalse(urls.is_valid_creature(make_card(games=["arena"])))
        self.assertTrue(urls.is_valid_creature(make_card(games=["arena", "paper"])))
        self.assertTrue(urls.is_valid_creature(make_card(games=["mtgo"])))

    def test_arena_rebalanced_name(self):
        self.assertFalse(urls.is_valid_creature(make_card(name="A-Grizzly Bears")))


class GetImageUrlTest(unittest.TestCase):
    def test_top_level_image(self):
        self.assertEqual(urls.get_image_url(make_card()), "https://example.test/normal.jpg")

    def test_double_faced_card_uses_front_face(self):
        card = make_card(card_faces=[{"image_uris": {"normal": "front"}}, {"image_uris": {"normal": "back"}}])
        del card["image_uris"]
        self.assertEqual(urls.get_image_url(card), "front")

    def test_no_image(self):
        card = make_card(card_faces=[{}])
        del card["image_uris"]
        self.assertIsNone(urls.get_image_url(card))


class LoadCreatureRecordsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cards = [
            make_card(),
            make_card(name="Lightning Bolt", type_line="Instant"),
            make_card(name="Goblin", layout="token"),
            make_card(name="Delver of Secrets // Insectile Aberration", cmc=1.0,
                      card_faces=[{"image_uris": {"normal": "front"}}, {"image_uris": {"normal": "back"}}]),
            make_card(name="Broken"),
        ]
        del self.cards[3]["image_uris"]
        del self.cards[4]["image_uris"]
        self.lines = "\n".join(json.dumps(c) for c in self.cards) + "\n"

    def check(self, path):
        records = urls.load_creature_records(path)
        self.assertEqual([r["name"] for r in records],
                         ["Grizzly Bears", "Delver of Secrets // Insectile Aberration"])
        self.assertEqual(records[1], {"name": "Delver of Secrets // Insectile Aberration",
                                      "image_url": "front", "cmc": 1.0})

    def test_gzip_file(self):
        path = os.path.join(self.tmp.name, "cards.jsonl.gz")
        with gzip.open(path, "wt", encoding="utf-8") as f:
            f.write(self.lines)
        self.check(path)

    def test_plain_file(self):
        path = os.path.join(self.tmp.name, "cards.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.lines)
        self.check(path)


class DownloadHelpersTest(unittest.TestCase):
    def test_sanitise_name(self):
        self.assertEqual(download.sanitise_name("Fire // Ice"), "Fire  Ice")
        self.assertEqual(download.sanitise_name("Urza's \"Best\""), "Urzas Best")

    def test_bmp_exists_and_jpg_path(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertFalse(download.bmp_exists(root, 2, "Bear"))
            os.makedirs(os.path.join(root, "2", "converted_files"))
            open(os.path.join(root, "2", "converted_files", "Bear.bmp"), "w").close()
            self.assertTrue(download.bmp_exists(root, 2, "Bear"))
            self.assertEqual(download.jpg_path(root, 2, "Bear"), os.path.join(root, "2", "Bear.jpg"))

    def test_sanitise_name_removes_windows_forbidden_chars(self):
        self.assertEqual(download.sanitise_name("Summon: Choco/Mog"), "Summon ChocoMog")
        self.assertEqual(download.sanitise_name('What? "Who*" <A|B>'), "What Who AB")
        self.assertEqual(download.sanitise_name("Bear."), "Bear")

    def test_cleanup_partial_files(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "2"))
            part, jpg = os.path.join(root, "2", "x.part"), os.path.join(root, "2", "Bear.jpg")
            open(part, "w").close()
            open(jpg, "w").close()
            download.cleanup_partial_files(root)
            self.assertFalse(os.path.exists(part))
            self.assertTrue(os.path.exists(jpg))


class ConvertImagesTest(unittest.TestCase):
    def make_jpg(self, root, cmc, name, size=(488, 680)):
        os.makedirs(os.path.join(root, str(cmc)), exist_ok=True)
        path = os.path.join(root, str(cmc), name + ".jpg")
        Image.new("RGB", size, (128, 128, 128)).save(path)
        return path

    def test_convert_to_printer_width_monochrome(self):
        with tempfile.TemporaryDirectory() as root:
            jpg = self.make_jpg(root, 2, "Bear")
            self.assertIsNone(convert_images.convert_image(jpg))
            out = convert_images.bmp_path(jpg)
            self.assertEqual(out, os.path.join(root, "2", "converted_files", "Bear.bmp"))
            with Image.open(out) as img:
                self.assertEqual(img.mode, "1")
                self.assertEqual(img.size, (convert_images.PRINTER_WIDTH, 535))
            self.assertFalse(os.path.exists(out + convert_images.PARTIAL_SUFFIX))

    def test_find_pending_skips_converted(self):
        with tempfile.TemporaryDirectory() as root:
            done = self.make_jpg(root, 2, "Done")
            todo = self.make_jpg(root, 3, "Todo")
            convert_images.convert_image(done)
            self.assertEqual(convert_images.find_pending(root), [todo])

    def test_corrupt_image_reports_error_and_leaves_no_file(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "2"))
            jpg = os.path.join(root, "2", "Broken.jpg")
            with open(jpg, "w") as f:
                f.write("not a jpeg")
            self.assertIn("Broken.jpg", convert_images.convert_image(jpg))
            self.assertFalse(os.path.exists(convert_images.bmp_path(jpg)))
            self.assertFalse(os.path.exists(convert_images.bmp_path(jpg) + convert_images.PARTIAL_SUFFIX))


class ProgressTests(unittest.TestCase):
    def test_prints_one_line_per_step_and_at_the_end(self):
        import contextlib, io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            p = progress.Progress(40, "x")  # step = 2 items (5%)
            for _ in range(40):
                p.tick()
        lines = out.getvalue().splitlines()
        self.assertEqual(len(lines), 20)
        self.assertIn("40/40 (100%)", lines[-1])
        self.assertIn("[" + "#" * progress.BAR_WIDTH + "]", lines[-1])

    def test_small_totals_print_every_item(self):
        import contextlib, io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            p = progress.Progress(3, "x")
            for _ in range(3):
                p.tick()
        self.assertEqual(len(out.getvalue().splitlines()), 3)

    def test_format_duration(self):
        self.assertEqual(progress.format_duration(42), "42s")
        self.assertEqual(progress.format_duration(425), "7m05s")
        self.assertEqual(progress.format_duration(7380), "2h03m")


if __name__ == "__main__":
    unittest.main()
