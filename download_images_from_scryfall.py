import os
import argparse
import urllib.request 
import json

def parse_args():
    parser = argparse.ArgumentParser(description="Download card images from Scryfall.")
    parser.add_argument(
        "--data-dir",
        default=".",
        help="Directory containing creatures_image_urls.json (default: current directory)."
    )
    parser.add_argument(
        "--images-dir",
        default=".",
        help="Root directory where CMC folders are created (default: current directory). "
             "Cards whose BMP already exists in <images-dir>/<cmc>/converted_files/ "
             "are skipped so only new cards are downloaded."
    )
    return parser.parse_args()

def sanitise_name(card_name):
    """Sanitise a card name for use as a filename, matching the on-disk convention."""
    return card_name.replace("'", "").replace('"', "").replace("/", "")

def bmp_exists(images_dir, cmc, card_name):
    """Return True if the converted BMP for this card already exists."""
    bmp_path = os.path.join(images_dir, str(cmc), "converted_files", sanitise_name(card_name) + ".bmp")
    return os.path.isfile(bmp_path)

def download_images_from_json(json_file, images_dir):
    with open(json_file, 'r', encoding='utf-8') as file:
        data = json.load(file)
        skipped = 0
        downloaded = 0
        for item in data:
            cmc = int(item["cmc"])
            name = item["name"]
            if bmp_exists(images_dir, cmc, name):
                skipped += 1
                continue
            download_image(item, images_dir)
            downloaded += 1
        print(f"Done: {downloaded} image(s) downloaded, {skipped} skipped (BMP already exists).")

def download_image(item, images_dir):
    url = item["image_url"]
    cmc = int(item["cmc"])
    name = item["name"]
    
    # Create CMC directory inside images_dir if it doesn't exist
    directory = os.path.join(images_dir, str(cmc))
    if not os.path.exists(directory):
        os.makedirs(directory)
    
    # Construct save path, replacing special characters
    save_path = os.path.join(directory, sanitise_name(name) + ".jpg")
    
    try:
        urllib.request.urlretrieve(url, save_path) 
        print(f"Downloaded {name} to {save_path}")
    except Exception as e:
        print(f"Failed to download {name}: {e}")

if __name__ == "__main__":
    args = parse_args()
    json_file = os.path.join(args.data_dir, 'creatures_image_urls.json')
    download_images_from_json(json_file, images_dir=args.images_dir)


