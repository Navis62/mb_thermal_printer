# mb_thermal_printer

Here are the scripts and steps i took to create a momir basic thermal printer, using a cheap thermal printer and a  raspberry pi

A step by step on how this was done is 

- Get the latest MTGJSON AtomicCards.json file from mtgjson.com
- Extract the scryfall id's and other useful information form the JSON file
- Get the image url's from scryfall and download them to one folder per cmc
- Using imagemagick convert the jpgs to monochrome grayscale
- Connect buttons, thermal printer and OLED screen to Raspberry Pi GPIO pins
- Add python script, and image files to Raspberry Pi
- Add python script to crontab startup so that it is automatically started when the Pi is powered on

Description of files: <br />
**get_image_urls_from_scryfall.py** - Get URLs for the actual image files from Scryfall, uses the Scryfall API and creates a new JSON file for us <br />
**download_images_from_scryfall.py** - Downloads the actual images into folders from Scryfalls database <br />
**convert_images_to_monochrome.sh** - Converts the JPG files into monochrome BMP files, this needs to be run on a Linux installation with imagemagick <br />
**momir_basic.py** - Actual python program that runs on the Pi for the printer <br />

I used the following hardware <br />
3x KY-004 Push Button  <br />
3x 1k OHM Resistors (optional, but will extend the lifetime of your buttons. They should be placed between the 3.3v and the button in that case) <br />
1x 3 x 0.91" OLED 128 x 32 pixels I2C Screen <br />
1x Raspberry Pi Zero 2 <br />
1x QR204 Thermal Printer <br />
1x 12V Female 2.1mm x 5.5mm DC Power Jack Adapter <br />
1x 9v 2A Male DC Power Adapter <br />
1x Power cable for Raspberry PI <br />
1x 400-Point Breadboard Kit with Dupont Cable and Jumper Wire <br />
1x 32gb micro SD card <br />

# Convert to BIN example

#Create a new folder for the binary files

mkdir -p ../binary_files

#Iterate through each BMP file and convert it to binary (PBM), remove header, and pad zero

for file in *.bmp; do
    echo "Creating BIN file for: $file" 

    # Define the output filename in the binary_files directory by replacing the extension with pbm
    output_file="../binary_files/$(basename -- "$file" .bmp).pbm"

    # Use ImageMagick's convert command to convert BMP to binary (PBM) with a depth of 1
    convert "$file" -threshold 50% -compress none pbm:- | \
    
    # Remove the PBM header and pad zeros to make the height even
    awk 'NR>2 {print $0} END{if(NR%2!=0) print "0"}' > "$output_file"
done
