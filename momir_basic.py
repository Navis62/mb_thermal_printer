from escpos.printer import Serial
import os, random, configparser
import RPi.GPIO as GPIO
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306 #imports of different modules
from luma.core.legacy import text
from PIL import Image
from PIL import ImageFont
import time

# Load settings
_config = configparser.RawConfigParser()
_settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings.cfg')
if not _config.read(_settings_path):
    raise FileNotFoundError(f"settings.cfg not found at {_settings_path}. Copy settings.cfg.example and adjust the paths.")
IMAGES_DIR = os.path.expanduser(_config.get('DEFAULT', 'IMAGES_DIR'))

#Button pins
BUTTON_1_PIN = 11  
BUTTON_2_PIN = 13
BUTTON_3_PIN = 15

cmc = 0 #cmc variable for tracking cmc

p = Serial(devfile='/dev/serial0', baudrate=9600, bytesize=8, parity='N', stopbits=1, timeout=10.0) #initilize thermal printer serial 

#initilize OLED screen serial ports, set communication and set font/size
serial = i2c(port=1, address=0x3C) 
device = ssd1306(serial)
font16 = ImageFont.truetype('/home/navis/.fonts/FredokaOne-Regular.ttf', 16) 

def display_cmc(cmc):
    with canvas(device) as draw:
        draw.text((5, 30), "Mana : " + str(cmc), fill="white", font=font16)
        
#display initial cmc = 0
display_cmc(cmc) 

def display_print_message(cmc):
    with canvas(device) as draw:
        draw.text((5, 0), "Impression", fill="white")#, font=font16)
        draw.text((5, 30), "Mana : " + str(cmc), fill="white", font=font16)
        
def display_message(message):
    with canvas(device) as draw:
        draw.text((5, 30), str(message), fill="white", font=font16)
    time.sleep(2)
    display_cmc(cmc)
        
#ignore button warnings and set numbering mode to BOARD
GPIO.setwarnings(False) 
GPIO.setmode(GPIO.BOARD)

#set GPIO settings for buttons
GPIO.setup(BUTTON_1_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) 
GPIO.setup(BUTTON_2_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(BUTTON_3_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

def print_random_image(cmc): #function to print image
    path = os.path.join(IMAGES_DIR, str(cmc), 'converted_files')
    try:
        image_path = os.path.join(path, random.choice(os.listdir(path)))
        print_image(image_path)
        p.textln("")
        p.textln("")
        p.textln("")
    except Exception as e:
        print("An error occurred:", e)

def print_image(image_path):
    with Image.open(image_path) as img:
        img = img.convert('1')
        p.image(img)

debounce_delay = 0.2  # Adjust this value as needed for your buttons

while True: # Run forever
    time.sleep(0.05)  # Reduce CPU usage, prevent thermal throttling
    if GPIO.input(BUTTON_1_PIN) == GPIO.LOW: #increase CMC button
        if cmc < 16: #highest cmc is 16, so we don't want to go over that
            cmc = cmc + 1
            display_cmc(cmc)
            time.sleep(debounce_delay)  # Debounce delay
        else:
            display_message("Trop haut, mec !")
    if GPIO.input(BUTTON_2_PIN) == GPIO.LOW: #decrease CMC button
        if cmc > 0: #lowest cmc is 0 so we don't want to go negative
            cmc = cmc - 1
            display_cmc(cmc)
            time.sleep(debounce_delay)  # Debounce delay
        else:
            display_message("Mais t'es con ?")
    if GPIO.input(BUTTON_3_PIN) == GPIO.LOW: #printing button
        display_print_message(cmc)
        print_random_image(cmc)
        time.sleep(debounce_delay)  # Debounce delay
