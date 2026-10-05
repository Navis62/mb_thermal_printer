import os
import configparser
import random
import time

import RPi.GPIO as GPIO
from escpos.printer import Serial
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306
from PIL import Image, ImageFont

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

# ---------------------------------------------------------------------------
# Hardware initialisation
# ---------------------------------------------------------------------------

# Thermal printer
printer = Serial(devfile='/dev/serial0', baudrate=9600, bytesize=8, parity='N', stopbits=1, timeout=10.0)

# OLED display
_serial = i2c(port=1, address=0x3C)
display  = ssd1306(_serial)
font16   = ImageFont.truetype(FONT_PATH, 16)

# GPIO buttons
# Wiring: buttons connect the pin to 3.3 V (active-high).
# PUD_DOWN holds the line LOW by default; a button press pulls it HIGH.
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)
for pin in (BUTTON_UP_PIN, BUTTON_DOWN_PIN, BUTTON_PRINT_PIN):
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def display_cmc(cmc):
    """Show the current CMC value on the OLED."""
    with canvas(display) as draw:
        draw.text((5, 30), f"Mana: {cmc}", fill="white", font=font16)

def display_printing(cmc):
    """Show a 'Printing…' message alongside the current CMC."""
    with canvas(display) as draw:
        draw.text((5, 0),  "Printing...", fill="white")
        draw.text((5, 30), f"Mana: {cmc}", fill="white", font=font16)

def display_message(message, cmc):
    """Show a temporary message then return to the CMC display."""
    with canvas(display) as draw:
        draw.text((5, 30), str(message), fill="white", font=font16)
    time.sleep(2)
    display_cmc(cmc)

# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------

def print_random_card(cmc):
    """Pick a random converted BMP for the given CMC and print it."""
    path = os.path.join(IMAGES_DIR, str(cmc), 'converted_files')
    try:
        files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
        if not files:
            raise FileNotFoundError(f"No converted images found in {path}")
        image_path = os.path.join(path, random.choice(files))
        _print_image(image_path)
        # Feed paper
        printer.textln("")
        printer.textln("")
        printer.textln("")
    except Exception as e:
        print(f"Print error: {e}")

def _print_image(image_path):
    """Send a single image to the thermal printer."""
    with Image.open(image_path) as img:
        img = img.convert('1')
        printer.image(img)

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    cmc = 0
    display_cmc(cmc)

    while True:
        time.sleep(POLL_INTERVAL)

        if GPIO.input(BUTTON_UP_PIN) == GPIO.HIGH:
            if cmc < CMC_MAX:
                cmc += 1
                display_cmc(cmc)
            else:
                display_message("Already at max!", cmc)
            time.sleep(DEBOUNCE_DELAY)

        elif GPIO.input(BUTTON_DOWN_PIN) == GPIO.HIGH:
            if cmc > CMC_MIN:
                cmc -= 1
                display_cmc(cmc)
            else:
                display_message("Already at 0!", cmc)
            time.sleep(DEBOUNCE_DELAY)

        elif GPIO.input(BUTTON_PRINT_PIN) == GPIO.HIGH:
            display_printing(cmc)
            print_random_card(cmc)
            time.sleep(DEBOUNCE_DELAY)

if __name__ == "__main__":
    main()
