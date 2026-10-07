import logging
import os
import configparser
import random
import signal
import time

import RPi.GPIO as GPIO
from escpos.printer import Serial
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306
from PIL import Image, ImageFont

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BUNDLED_FONT_PATH = os.path.join(BASE_DIR, 'assets', 'FredokaOne-Regular.ttf')

def load_settings():
    """Load configuration from settings.cfg located next to this script."""
    config = configparser.RawConfigParser()
    settings_path = os.path.join(BASE_DIR, 'settings.cfg')
    if not config.read(settings_path):
        raise FileNotFoundError(
            f"settings.cfg not found at {settings_path}. "
            "Copy settings.cfg.example and adjust the paths."
        )
    return config

def resolve_font_path(configured):
    """Return the font to use: the configured one if it exists, else the bundled font.

    A relative path is relative to the repository directory.
    """
    if configured:
        path = os.path.join(BASE_DIR, os.path.expanduser(configured))
        if os.path.isfile(path):
            return path
        logging.warning("Font %s not found, using the bundled font.", path)
    return BUNDLED_FONT_PATH

_config = load_settings()
IMAGES_DIR  = os.path.expanduser(_config.get('DEFAULT', 'IMAGES_DIR'))
FONT_PATH   = resolve_font_path(_config.get('DEFAULT', 'FONT_PATH', fallback=''))
# Seconds of inactivity before the OLED is switched off (burn-in); 0 = never
OLED_TIMEOUT = _config.getint('DEFAULT', 'OLED_TIMEOUT', fallback=300)
# Button wiring: false = pin pulled to 3.3 V when pressed (default), true = pin pulled to GND
BUTTONS_ACTIVE_LOW = _config.getboolean('DEFAULT', 'BUTTONS_ACTIVE_LOW', fallback=False)

# ---------------------------------------------------------------------------
# Hardware constants
# ---------------------------------------------------------------------------

BUTTON_UP_PIN    = 11   # Increase CMC
BUTTON_DOWN_PIN  = 13   # Decrease CMC
BUTTON_PRINT_PIN = 15   # Print a random card

CMC_MIN = 0
CMC_MAX = 16

DEBOUNCE_DELAY = 0.2    # seconds — adjust for your buttons
POLL_INTERVAL  = 0.05   # seconds — reduce CPU usage / prevent thermal throttling

# OLED messages: 128 px wide, 16 px font, drawn at x=5 → at most ~123 px of text
MSG_AT_MAX   = "Max reached"
MSG_AT_MIN   = "Min reached"
MSG_NO_CARDS = "No cards"
MSG_ERROR    = "Print error"

# ---------------------------------------------------------------------------
# Hardware initialisation
# ---------------------------------------------------------------------------

def init_hardware():
    """Initialise and return (printer, display, font16).

    Keeping hardware setup inside a function avoids crashes at import time
    when the hardware is not connected (e.g. during unit tests or development
    on a non-Pi machine).
    """
    # Thermal printer
    printer = Serial(devfile='/dev/serial0', baudrate=9600, bytesize=8,
                     parity='N', stopbits=1, timeout=10.0)

    # OLED display
    serial = i2c(port=1, address=0x3C)
    display = ssd1306(serial)
    font16 = ImageFont.truetype(FONT_PATH, 16)

    # GPIO buttons
    # Default wiring: buttons connect the pin to 3.3 V (active-high); PUD_DOWN holds the
    # line LOW and a press pulls it HIGH. With BUTTONS_ACTIVE_LOW the buttons connect the
    # pin to GND instead: PUD_UP holds the line HIGH and a press pulls it LOW.
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BOARD)
    pull = GPIO.PUD_UP if BUTTONS_ACTIVE_LOW else GPIO.PUD_DOWN
    for pin in (BUTTON_UP_PIN, BUTTON_DOWN_PIN, BUTTON_PRINT_PIN):
        GPIO.setup(pin, GPIO.IN, pull_up_down=pull)

    return printer, display, font16

# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def display_cmc(display, font16, cmc):
    """Show the current CMC value on the OLED."""
    with canvas(display) as draw:
        draw.text((5, 30), f"Mana: {cmc}", fill="white", font=font16)

def display_printing(display, font16, cmc):
    """Show a 'Printing…' message alongside the current CMC."""
    with canvas(display) as draw:
        draw.text((5, 0),  "Printing...", fill="white")
        draw.text((5, 30), f"Mana: {cmc}", fill="white", font=font16)

def display_message(display, font16, message, cmc):
    """Show a temporary message then return to the CMC display."""
    with canvas(display) as draw:
        draw.text((5, 30), str(message), fill="white", font=font16)
    time.sleep(2)
    display_cmc(display, font16, cmc)

# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------

_card_cache = {}  # folder -> (folder mtime, [BMP file names])

def list_cards(path):
    """Return the BMP file names in a folder, re-reading it only when it has changed.

    A folder's mtime changes when files are added or removed (e.g. by update.sh),
    so new cards are picked up without restarting the program.
    Raises FileNotFoundError if the folder does not exist.
    """
    mtime = os.stat(path).st_mtime
    cached = _card_cache.get(path)
    if cached is None or cached[0] != mtime:
        # Only complete BMPs: skip leftovers such as "*.bmp.part"
        files = [f for f in os.listdir(path) if f.lower().endswith('.bmp')]
        cached = _card_cache[path] = (mtime, files)
    return cached[1]

def print_random_card(printer, display, font16, cmc):
    """Pick a random converted BMP for the given CMC and print it."""
    path = os.path.join(IMAGES_DIR, str(cmc), 'converted_files')
    try:
        files = list_cards(path)
        if not files:
            raise FileNotFoundError(f"No converted images found in {path}")
        image_path = os.path.join(path, random.choice(files))
        _print_image(printer, image_path)
        # Feed paper
        printer.textln("")
        printer.textln("")
        printer.textln("")
    except FileNotFoundError as e:
        # Missing CMC folder or no converted BMP in it
        logging.error("No cards available: %s", e)
        display_message(display, font16, MSG_NO_CARDS, cmc)
    except Exception as e:
        logging.error("Print error: %s", e)
        display_message(display, font16, MSG_ERROR, cmc)

def _print_image(printer, image_path):
    """Send a single image to the thermal printer."""
    with Image.open(image_path) as img:
        img = img.convert('1')
        printer.image(img)

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def _handle_sigterm(signum, frame):
    """Turn SIGTERM (kill, systemd stop) into a normal exit so cleanup runs."""
    raise SystemExit(0)

def _is_pressed(pin):
    """Return True if the given button is currently pressed."""
    pressed_level = GPIO.LOW if BUTTONS_ACTIVE_LOW else GPIO.HIGH
    return GPIO.input(pin) == pressed_level

def _any_pressed(*pins):
    """Return True if any of the given buttons is currently pressed."""
    return any(_is_pressed(pin) for pin in pins)

def _wait_for_release(*pins):
    """Block until all the given buttons are released."""
    while _any_pressed(*pins):
        time.sleep(POLL_INTERVAL)

def main():
    signal.signal(signal.SIGTERM, _handle_sigterm)

    try:
        printer, display, font16 = init_hardware()
    except Exception as e:
        logging.critical("Hardware initialisation failed: %s", e)
        GPIO.cleanup()
        raise

    all_buttons = (BUTTON_UP_PIN, BUTTON_DOWN_PIN, BUTTON_PRINT_PIN)
    cmc = 0
    display_cmc(display, font16, cmc)
    display_on = True
    last_activity = time.monotonic()

    try:
        while True:
            time.sleep(POLL_INTERVAL)

            # OLED saver: switch the screen off after a while, wake it with any
            # button (that press only wakes the screen, it does nothing else).
            if display_on and OLED_TIMEOUT and time.monotonic() - last_activity > OLED_TIMEOUT:
                display.hide()
                display_on = False
                logging.info("OLED off after %s s of inactivity.", OLED_TIMEOUT)
            if not display_on:
                if _any_pressed(*all_buttons):
                    display.show()
                    display_on = True
                    last_activity = time.monotonic()
                    _wait_for_release(*all_buttons)
                continue

            if _is_pressed(BUTTON_UP_PIN):
                last_activity = time.monotonic()
                if cmc < CMC_MAX:
                    cmc += 1
                    display_cmc(display, font16, cmc)
                    time.sleep(DEBOUNCE_DELAY)
                else:
                    display_message(display, font16, MSG_AT_MAX, cmc)

            elif _is_pressed(BUTTON_DOWN_PIN):
                last_activity = time.monotonic()
                if cmc > CMC_MIN:
                    cmc -= 1
                    display_cmc(display, font16, cmc)
                    time.sleep(DEBOUNCE_DELAY)
                else:
                    display_message(display, font16, MSG_AT_MIN, cmc)

            elif _is_pressed(BUTTON_PRINT_PIN):
                display_printing(display, font16, cmc)
                print_random_card(printer, display, font16, cmc)
                display_cmc(display, font16, cmc)
                # Wait for the button to be released: a long press must not
                # print a second card as soon as the first one is done.
                _wait_for_release(BUTTON_PRINT_PIN)
                time.sleep(DEBOUNCE_DELAY)
                last_activity = time.monotonic()

    except KeyboardInterrupt:
        logging.info("Interrupted, shutting down.")
    finally:
        GPIO.cleanup()
        logging.info("GPIO cleaned up.")

if __name__ == "__main__":
    main()
