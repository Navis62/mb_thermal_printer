"""Unit tests for the data-preparation scripts (scripts/).

Run from the repository root:  python -m unittest discover -s tests
"""
import gzip
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import cmc_dirs
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

    def test_double_faced_card_needs_a_creature_front_face(self):
        # Battles and sagas that transform into a creature: the printed front face is not a creature
        self.assertFalse(urls.is_valid_creature(make_card(type_line="Battle — Siege // Creature — Dragon")))
        self.assertFalse(urls.is_valid_creature(make_card(type_line="Enchantment — Saga // Enchantment Creature — Kami")))
        self.assertTrue(urls.is_valid_creature(make_card(type_line="Creature — Human Wizard // Creature — Human Insect")))
        self.assertTrue(urls.is_valid_creature(make_card(type_line="Creature — Human Peasant // Sorcery — Adventure")))

    def test_is_creature_front_looks_at_the_front_face_only(self):
        self.assertTrue(urls.is_creature_front(make_card()))
        self.assertTrue(urls.is_creature_front(make_card(type_line="Creature — Elf // Land")))
        self.assertFalse(urls.is_creature_front(make_card(type_line="Land // Creature — Elf")))
        self.assertFalse(urls.is_creature_front({}))

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

    def test_cleanup_ignores_folders_that_are_not_cmc(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "assets"))
            part = os.path.join(root, "assets", "x.part")
            open(part, "w").close()
            download.cleanup_partial_files(root)
            self.assertTrue(os.path.exists(part))


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

    def test_find_pending_ignores_folders_that_are_not_cmc(self):
        # IMAGES_DIR pointing at the repository must not pick up assets/wiring.jpg
        with tempfile.TemporaryDirectory() as root:
            card = self.make_jpg(root, 12, "Card")
            os.makedirs(os.path.join(root, "assets"))
            Image.new("RGB", (10, 10)).save(os.path.join(root, "assets", "wiring.jpg"))
            self.assertEqual(convert_images.find_pending(root), [card])

    def test_cleanup_ignores_folders_that_are_not_cmc(self):
        with tempfile.TemporaryDirectory() as root:
            parts = {}
            for folder in ("7", "assets"):
                os.makedirs(os.path.join(root, folder, "converted_files"))
                parts[folder] = os.path.join(root, folder, "converted_files", "x.bmp.part")
                open(parts[folder], "w").close()
            convert_images.cleanup_partial_files(root)
            self.assertFalse(os.path.exists(parts["7"]))
            self.assertTrue(os.path.exists(parts["assets"]))

    def test_corrupt_image_reports_error_and_leaves_no_file(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "2"))
            jpg = os.path.join(root, "2", "Broken.jpg")
            with open(jpg, "w") as f:
                f.write("not a jpeg")
            self.assertIn("Broken.jpg", convert_images.convert_image(jpg))
            self.assertFalse(os.path.exists(convert_images.bmp_path(jpg)))
            self.assertFalse(os.path.exists(convert_images.bmp_path(jpg) + convert_images.PARTIAL_SUFFIX))


class CmcDirsTest(unittest.TestCase):
    def test_only_all_digit_names_are_cmc_folders(self):
        for name in ("0", "7", "16"):
            self.assertTrue(cmc_dirs.is_cmc_dir(name), name)
        for name in ("assets", ".git", "", "1a", "-1", "٣"):
            self.assertFalse(cmc_dirs.is_cmc_dir(name), name)

    def test_glob_returns_sorted_matches_in_cmc_folders_only(self):
        with tempfile.TemporaryDirectory() as root:
            wanted = []
            for folder, name in (("2", "b.jpg"), ("2", "a.jpg"), ("10", "c.jpg"), ("assets", "w.jpg"), (".git", "x.jpg")):
                os.makedirs(os.path.join(root, folder), exist_ok=True)
                path = os.path.join(root, folder, name)
                open(path, "w").close()
                if folder in ("2", "10"):
                    wanted.append(path)
            open(os.path.join(root, "2", "notes.txt"), "w").close()
            self.assertEqual(cmc_dirs.glob_in_cmc_dirs(root, "*.jpg"), sorted(wanted))


class ConvertEndToEndTest(unittest.TestCase):
    def make_card(self, root, cmc, name, size=(488, 680)):
        os.makedirs(os.path.join(root, str(cmc)), exist_ok=True)
        path = os.path.join(root, str(cmc), name + ".jpg")
        # Black top half, white bottom half: both must stay pure after dithering
        img = Image.new("L", size, 255)
        img.paste(0, (0, 0, size[0], size[1] // 2))
        img.convert("RGB").save(path, quality=95)
        return path

    def test_height_keeps_the_aspect_ratio_whatever_the_source_size(self):
        with tempfile.TemporaryDirectory() as root:
            for name, size, height in (("Small", (100, 140), 538), ("Wide", (800, 400), 192)):
                jpg = self.make_card(root, 3, name, size)
                self.assertIsNone(convert_images.convert_image(jpg))
                with Image.open(convert_images.bmp_path(jpg)) as img:
                    self.assertEqual((img.mode, img.size), ("1", (384, height)), name)

    def test_printed_card_keeps_black_and_white_areas(self):
        with tempfile.TemporaryDirectory() as root:
            jpg = self.make_card(root, 4, "Contrast")
            convert_images.convert_image(jpg)
            with Image.open(convert_images.bmp_path(jpg)) as img:
                img = img.convert("L")
                top = img.crop((10, 10, 374, 200)).getextrema()
                bottom = img.crop((10, 340, 374, 520)).getextrema()
            self.assertEqual(top, (0, 0))
            self.assertEqual(bottom, (255, 255))

    def test_convert_all_converts_everything_and_leaves_no_part_file(self):
        import contextlib, io
        with tempfile.TemporaryDirectory() as root:
            jpgs = [self.make_card(root, 1, "A", (100, 140)), self.make_card(root, 5, "B", (100, 140))]
            stale = os.path.join(root, "1", "converted_files")
            os.makedirs(stale)
            stale = os.path.join(stale, "Old.bmp.part")
            open(stale, "w").close()
            with contextlib.redirect_stdout(io.StringIO()):
                failures = convert_images.convert_all(root, workers=1)
            self.assertEqual(failures, 0)
            for jpg in jpgs:
                self.assertTrue(os.path.isfile(convert_images.bmp_path(jpg)))
            self.assertFalse(os.path.exists(stale))
            leftovers = [f for _, _, files in os.walk(root) for f in files if f.endswith(convert_images.PARTIAL_SUFFIX)]
            self.assertEqual(leftovers, [])
            self.assertEqual(convert_images.find_pending(root), [])

    def test_convert_all_reports_failures_and_still_converts_the_rest(self):
        import contextlib, io
        with tempfile.TemporaryDirectory() as root:
            good = self.make_card(root, 2, "Good", (100, 140))
            bad = os.path.join(root, "2", "Bad.jpg")
            with open(bad, "w") as f:
                f.write("not a jpeg")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                failures = convert_images.convert_all(root, workers=1)
            self.assertEqual(failures, 1)
            self.assertTrue(os.path.isfile(convert_images.bmp_path(good)))
            self.assertFalse(os.path.exists(convert_images.bmp_path(bad)))
            self.assertIn("Failed to convert", out.getvalue())

    def test_convert_all_with_nothing_to_do_returns_zero(self):
        import contextlib, io
        with tempfile.TemporaryDirectory() as root:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(convert_images.convert_all(root, workers=1), 0)
            self.assertIn("No new images", out.getvalue())


class AtkinsonDitherTest(unittest.TestCase):
    def dither(self, level, size=(32, 32)):
        return convert_images.atkinson_dither(Image.new("L", size, level))

    def test_returns_a_one_bit_image_of_the_same_size(self):
        out = self.dither(128, (40, 17))
        self.assertEqual((out.mode, out.size), ("1", (40, 17)))

    def test_pure_black_and_white_stay_pure(self):
        self.assertEqual(self.dither(0).getextrema(), (0, 0))
        self.assertEqual(self.dither(255).getextrema(), (255, 255))

    def test_light_and_dark_areas_have_no_speckles(self):
        # Atkinson drops part of the error: near-white / near-black become solid
        self.assertEqual(self.dither(250).getextrema(), (255, 255))
        self.assertEqual(self.dither(5).getextrema(), (0, 0))

    def test_mid_grey_is_roughly_half_black(self):
        pixels = list(self.dither(128, (64, 64)).getdata())
        black = pixels.count(0) / len(pixels)
        self.assertTrue(0.35 < black < 0.65, black)


class HalftoneDitherTest(unittest.TestCase):
    def halftone(self, level, size=(48, 48)):
        return convert_images.halftone_dither(Image.new("L", size, level))

    def black_ratio(self, image):
        pixels = list(image.getdata())
        return pixels.count(0) / len(pixels)

    def test_returns_a_one_bit_image_of_the_same_size(self):
        out = self.halftone(128, (50, 17))
        self.assertEqual((out.mode, out.size), ("1", (50, 17)))

    def test_pure_black_and_white_stay_pure(self):
        self.assertEqual(self.halftone(0).getextrema(), (0, 0))
        self.assertEqual(self.halftone(255).getextrema(), (255, 255))

    def test_coverage_follows_the_grey_level(self):
        ratios = [self.black_ratio(self.halftone(level)) for level in (230, 180, 128, 75, 25)]
        self.assertEqual(ratios, sorted(ratios))                 # darker input, more black dots
        self.assertTrue(0.4 < ratios[2] < 0.6, ratios[2])        # mid grey is about half black

    def test_dots_are_clustered(self):
        # a mid-tone is rendered as blobs, not as isolated pixels: most black pixels have a black neighbour
        image = self.halftone(100, (60, 60)).convert("L")
        w, h = image.size
        px = image.load()
        black = [(x, y) for x in range(1, w - 1) for y in range(1, h - 1) if px[x, y] == 0]
        touching = sum(1 for x, y in black if 0 in (px[x + 1, y], px[x - 1, y], px[x, y + 1], px[x, y - 1]))
        self.assertGreater(touching / len(black), 0.7)

    def test_dither_follows_the_DITHER_setting(self):
        gray = Image.new("L", (32, 32), 100)
        with mock.patch.object(convert_images, "DITHER", "atkinson"):
            self.assertEqual(list(convert_images.dither(gray).getdata()),
                             list(convert_images.atkinson_dither(gray).getdata()))
        with mock.patch.object(convert_images, "DITHER", "halftone"):
            self.assertEqual(list(convert_images.dither(gray).getdata()),
                             list(convert_images.halftone_dither(gray).getdata()))


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
