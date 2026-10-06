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

def load_settings():
    """Load configuration from settings.cfg located next to this script."""
    config = configparser.RawConfigParser()
    settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings.cfg')
    if not config.read(settings_path):
        raise FileNotFoundError(
            f"settings.cfg not found at {settings_path}. "
            "Copy settings.cfg.example and adjust the paths."
        )
    return config

_config = load_settings()
IMAGES_DIR = os.path.expanduser(_config.get('DEFAULT', 'IMAGES_DIR'))
FONT_PATH  = os.path.expanduser(_config.get('DEFAULT', 'FONT_PATH'))

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
    _printer = Serial(devfile='/dev/serial0', baudrate=9600, bytesize=8,
                      parity='N', stopbits=1, timeout=10.0)

    # OLED display
    _serial = i2c(port=1, address=0x3C)
    _display = ssd1306(_serial)
    _font16 = ImageFont.truetype(FONT_PATH, 16)

    # GPIO buttons
    # Wiring: buttons connect the pin to 3.3 V (active-high).
    # PUD_DOWN holds the line LOW by default; a button press pulls it HIGH.
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BOARD)
    for pin in (BUTTON_UP_PIN, BUTTON_DOWN_PIN, BUTTON_PRINT_PIN):
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    return _printer, _display, _font16

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

def print_random_card(printer, display, font16, cmc):
    """Pick a random converted BMP for the given CMC and print it."""
    path = os.path.join(IMAGES_DIR, str(cmc), 'converted_files')
    try:
        files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
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

def main():
    signal.signal(signal.SIGTERM, _handle_sigterm)

    try:
        printer, display, font16 = init_hardware()
    except Exception as e:
        logging.critical("Hardware initialisation failed: %s", e)
        GPIO.cleanup()
        raise

    cmc = 0
    display_cmc(display, font16, cmc)

    try:
        while True:
            time.sleep(POLL_INTERVAL)

            if GPIO.input(BUTTON_UP_PIN) == GPIO.HIGH:
                if cmc < CMC_MAX:
                    cmc += 1
                    display_cmc(display, font16, cmc)
                    time.sleep(DEBOUNCE_DELAY)
                else:
                    display_message(display, font16, MSG_AT_MAX, cmc)

            elif GPIO.input(BUTTON_DOWN_PIN) == GPIO.HIGH:
                if cmc > CMC_MIN:
                    cmc -= 1
                    display_cmc(display, font16, cmc)
                    time.sleep(DEBOUNCE_DELAY)
                else:
                    display_message(display, font16, MSG_AT_MIN, cmc)

            elif GPIO.input(BUTTON_PRINT_PIN) == GPIO.HIGH:
                display_printing(display, font16, cmc)
                print_random_card(printer, display, font16, cmc)
                display_cmc(display, font16, cmc)
                # Wait for the button to be released: a long press must not
                # print a second card as soon as the first one is done.
                while GPIO.input(BUTTON_PRINT_PIN) == GPIO.HIGH:
                    time.sleep(POLL_INTERVAL)
                time.sleep(DEBOUNCE_DELAY)

    except KeyboardInterrupt:
        logging.info("Interrupted, shutting down.")
    finally:
        GPIO.cleanup()
        logging.info("GPIO cleaned up.")

if __name__ == "__main__":
    main()
