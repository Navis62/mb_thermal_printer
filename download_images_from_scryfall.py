import os
import argparse
import urllib.request 
import json

def parse_args():
    parser = argparse.ArgumentParser(description="Download card images from Scryfall.")
    parser.add_argument(
        "--images-dir",
        default=None,
        help="Root directory where CMC folders are created (default: current directory). "
             "When provided, cards whose BMP already exists in <images-dir>/<cmc>/converted_files/ "
             "are skipped so only new cards are downloaded."
    )
    return parser.parse_args()

def bmp_name(card_name):
    """Return the expected BMP filename for a card, matching the naming in download_image()."""
    return card_name.replace("'", "").replace('"', "").replace("/", "") + ".bmp"

def download_images_from_json(json_file, images_dir=None):
    with open(json_file, 'r', encoding='utf-8') as file:
        data = json.load(file)
        skipped = 0
        downloaded = 0
        for item in data:
            cmc = int(item["cmc"])
            name = item["name"]
            # If an images_dir is provided, skip cards that already have a BMP
            if images_dir is not None:
                expected_bmp = os.path.join(images_dir, str(cmc), "converted_files", bmp_name(name))
                if os.path.isfile(expected_bmp):
                    skipped += 1
                    continue
            download_image(item)
            downloaded += 1
        print(f"Done: {downloaded} image(s) downloaded, {skipped} skipped (BMP already exists).")

def download_image(item):
    url = item["image_url"]
    cmc = int(item["cmc"])
    name = item["name"]
    
    # Create directory if it doesn't exist
    directory = str(cmc)
    if not os.path.exists(directory):
        os.makedirs(directory)
    
    # Construct save path, replacing special characters
    save_path = os.path.join(directory, name.replace("'", "").replace('"', "").replace("/", "") + ".jpg")
    
    try:
        urllib.request.urlretrieve(url, save_path) 
        print(f"Downloaded {name} to {save_path}")
    except Exception as e:
        print(f"Failed to download {name}: {e}")

args = parse_args()
download_images_from_json('creatures_image_urls.json', images_dir=args.images_dir)

