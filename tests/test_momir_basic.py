"""Unit tests for momir_basic.py, with the Raspberry Pi hardware mocked.

Run from the repository root:  python -m unittest discover -s tests
"""
import configparser
import os
import shutil
import signal
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

# --- Stub the hardware libraries, which are only available on a Raspberry Pi
GPIO = mock.MagicMock()
GPIO.HIGH, GPIO.LOW = 1, 0
_rpi = types.ModuleType("RPi")
_rpi.GPIO = GPIO
sys.modules["RPi"] = _rpi
sys.modules["RPi.GPIO"] = GPIO
for _name in ("escpos", "escpos.printer", "luma", "luma.core", "luma.core.interface",
              "luma.core.interface.serial", "luma.core.render", "luma.oled", "luma.oled.device"):
    sys.modules[_name] = mock.MagicMock()

# --- settings.cfg does not exist in the repository: provide one at import time
_IMAGES_DIR = tempfile.mkdtemp(prefix="momir_test_")


def _fake_read(self, filenames, encoding=None):
    self.read_string(f"[DEFAULT]\nIMAGES_DIR={_IMAGES_DIR}\nFONT_PATH=/does/not/exist.ttf\n")
    return [filenames]


with mock.patch.object(configparser.RawConfigParser, "read", _fake_read):
    import momir_basic as mb


def tearDownModule():
    shutil.rmtree(_IMAGES_DIR, ignore_errors=True)


class MainLoopCase(unittest.TestCase):
    """Base class: run main() against scripted button states."""

    def setUp(self):
        GPIO.reset_mock()
        GPIO.input.side_effect = None
        self.printer, self.display = mock.MagicMock(), mock.MagicMock()
        self.sleeps = 0
        patches = [
            mock.patch.object(mb, "init_hardware", return_value=(self.printer, self.display, None)),
            mock.patch.object(mb, "display_cmc"),
            mock.patch.object(mb, "display_printing"),
            mock.patch.object(mb, "display_message"),
            mock.patch.object(mb, "_print_image"),
        ]
        (_, self.display_cmc, _, self.display_message, self.print_image) = [p.start() for p in patches]
        for p in patches:
            self.addCleanup(p.stop)

    def run_main(self, pressed, max_sleeps=60, on_sleep=None):
        """Run main(); `pressed(pin, n)` tells if a button is pressed at the n-th sleep."""
        def fake_sleep(_seconds):
            self.sleeps += 1
            if on_sleep:
                on_sleep(self.sleeps)
            if self.sleeps > max_sleeps:
                raise KeyboardInterrupt

        GPIO.input.side_effect = lambda pin: int(pressed(pin, self.sleeps))
        with mock.patch.object(mb.time, "sleep", side_effect=fake_sleep):
            mb.main()


class ButtonsTest(MainLoopCase):
    def test_long_press_on_print_prints_a_single_card(self):
        os.makedirs(os.path.join(_IMAGES_DIR, "0", "converted_files"), exist_ok=True)
        open(os.path.join(_IMAGES_DIR, "0", "converted_files", "a.bmp"), "w").close()
        mb._card_cache.clear()
        # PRINT held for the first 10 sleeps only
        self.run_main(lambda pin, n: pin == mb.BUTTON_PRINT_PIN and n < 10)
        self.assertEqual(self.print_image.call_count, 1)

    def test_up_and_down_change_cmc_within_bounds(self):
        # UP pressed at sleeps 1 and 3, then DOWN at sleep 5
        schedule = {1: mb.BUTTON_UP_PIN, 3: mb.BUTTON_UP_PIN, 5: mb.BUTTON_DOWN_PIN}
        self.run_main(lambda pin, n: schedule.get(n) == pin, max_sleeps=12)
        shown = [c.args[2] for c in self.display_cmc.call_args_list]
        self.assertEqual(shown[0], 0)
        self.assertIn(2, shown)
        self.assertEqual(shown[-1], 1)

    def test_down_at_zero_shows_message(self):
        self.run_main(lambda pin, n: pin == mb.BUTTON_DOWN_PIN and n == 1, max_sleeps=4)
        self.assertEqual(self.display_message.call_args.args[2], mb.MSG_AT_MIN)

    def test_ctrl_c_cleans_up_without_traceback(self):
        self.run_main(lambda pin, n: False, max_sleeps=2)
        GPIO.cleanup.assert_called()

    def test_sigterm_cleans_up(self):
        def on_sleep(n):
            if n == 3:
                signal.raise_signal(signal.SIGTERM)
        with self.assertRaises(SystemExit):
            self.run_main(lambda pin, n: False, on_sleep=on_sleep)
        GPIO.cleanup.assert_called()

    def test_hardware_init_failure_cleans_up_and_raises(self):
        mb.init_hardware.side_effect = OSError("no printer")
        with self.assertRaises(OSError):
            mb.main()
        GPIO.cleanup.assert_called()


class ActiveLowTest(unittest.TestCase):
    def test_pressed_level_follows_the_wiring(self):
        GPIO.input.side_effect = lambda pin: 0
        with mock.patch.object(mb, "BUTTONS_ACTIVE_LOW", True):
            self.assertTrue(mb._is_pressed(mb.BUTTON_UP_PIN))
        with mock.patch.object(mb, "BUTTONS_ACTIVE_LOW", False):
            self.assertFalse(mb._is_pressed(mb.BUTTON_UP_PIN))
        GPIO.input.side_effect = None


class OledSleepTest(MainLoopCase):
    def run_with_clock(self, pressed, clock, **kw):
        """main() with a controllable time.monotonic()."""
        with mock.patch.object(mb.time, "monotonic", side_effect=lambda: clock["t"]):
            self.run_main(pressed, **kw)

    def test_screen_switches_off_then_wakes_without_acting(self):
        clock = {"t": 0.0}
        # Inactive until sleep 5 (clock jumps past the timeout), then UP pressed at 8-9
        def on_sleep(n):
            clock["t"] = 0.0 if n < 5 else mb.OLED_TIMEOUT + 10.0
        self.run_with_clock(lambda pin, n: pin == mb.BUTTON_UP_PIN and 8 <= n < 10, clock,
                            max_sleeps=14, on_sleep=on_sleep)
        self.display.hide.assert_called_once()
        self.display.show.assert_called_once()
        # The waking press must not have increased the CMC
        shown = [c.args[2] for c in self.display_cmc.call_args_list]
        self.assertEqual(set(shown), {0})

    def test_timeout_zero_never_switches_off(self):
        clock = {"t": 0.0}
        with mock.patch.object(mb, "OLED_TIMEOUT", 0):
            self.run_with_clock(lambda pin, n: False, clock, max_sleeps=5,
                                on_sleep=lambda n: clock.update(t=1e9))
        self.display.hide.assert_not_called()


class PrintRandomCardTest(unittest.TestCase):
    def setUp(self):
        mb._card_cache.clear()
        self.dm = mock.patch.object(mb, "display_message").start()
        self.addCleanup(mock.patch.stopall)

    def folder(self, cmc):
        path = os.path.join(_IMAGES_DIR, str(cmc), "converted_files")
        os.makedirs(path, exist_ok=True)
        return path

    def test_empty_and_missing_folders_show_no_cards(self):
        self.folder(5)
        with mock.patch.object(mb, "_print_image"):
            mb.print_random_card(mock.MagicMock(), None, None, 5)    # empty
            mb.print_random_card(mock.MagicMock(), None, None, 14)   # missing
        self.assertEqual([c.args[2] for c in self.dm.call_args_list], [mb.MSG_NO_CARDS] * 2)

    def test_printer_failure_shows_print_error(self):
        open(os.path.join(self.folder(6), "a.bmp"), "w").close()
        with mock.patch.object(mb, "_print_image", side_effect=OSError("boom")):
            mb.print_random_card(mock.MagicMock(), None, None, 6)
        self.assertEqual(self.dm.call_args.args[2], mb.MSG_ERROR)

    def test_only_complete_bmps_are_candidates(self):
        folder = self.folder(7)
        for name in ("a.bmp", "b.bmp.part", "notes.txt"):
            open(os.path.join(folder, name), "w").close()
        self.assertEqual(mb.list_cards(folder), ["a.bmp"])

    def test_card_list_is_cached_and_refreshed_when_folder_changes(self):
        folder = self.folder(8)
        open(os.path.join(folder, "a.bmp"), "w").close()
        with mock.patch.object(mb.os, "listdir", wraps=os.listdir) as listdir:
            mb.list_cards(folder)
            mb.list_cards(folder)
            self.assertEqual(listdir.call_count, 1)
            open(os.path.join(folder, "b.bmp"), "w").close()
            os.utime(folder, (1, os.stat(folder).st_mtime + 5))  # make the change visible on coarse clocks
            self.assertEqual(sorted(mb.list_cards(folder)), ["a.bmp", "b.bmp"])
            self.assertEqual(listdir.call_count, 2)


class FontTest(unittest.TestCase):
    def test_missing_configured_font_falls_back_to_bundled(self):
        self.assertEqual(mb.resolve_font_path("/does/not/exist.ttf"), mb.BUNDLED_FONT_PATH)
        self.assertEqual(mb.resolve_font_path(""), mb.BUNDLED_FONT_PATH)
        self.assertTrue(os.path.isfile(mb.BUNDLED_FONT_PATH))

    def test_existing_and_relative_fonts(self):
        self.assertEqual(mb.resolve_font_path(mb.BUNDLED_FONT_PATH), mb.BUNDLED_FONT_PATH)
        self.assertEqual(os.path.normpath(mb.resolve_font_path("assets/FredokaOne-Regular.ttf")),
                         os.path.normpath(mb.BUNDLED_FONT_PATH))

    def test_messages_fit_the_oled(self):
        from PIL import ImageFont
        font = ImageFont.truetype(mb.BUNDLED_FONT_PATH, 16)
        for msg in (mb.MSG_AT_MAX, mb.MSG_AT_MIN, mb.MSG_NO_CARDS, mb.MSG_ERROR):
            self.assertLessEqual(font.getlength(msg), 123, msg)  # 128 px - 5 px margin


if __name__ == "__main__":
    unittest.main()
