import os
import argparse
import json
import threading
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# Number of parallel download workers
DOWNLOAD_WORKERS = 12

# Thread-local storage for per-thread HTTP sessions
_thread_local = threading.local()


def _get_session():
    """Return a requests.Session local to the current thread."""
    if not hasattr(_thread_local, 'session'):
        _thread_local.session = requests.Session()
    return _thread_local.session


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
        help="Root directory where CMC sub-folders are created (default: current directory). "
             "Cards whose BMP already exists in <images-dir>/<cmc>/converted_files/ are skipped."
    )
    return parser.parse_args()


def sanitise_name(card_name):
    """Sanitise a card name for use as a filename."""
    return card_name.replace("'", "").replace('"', "").replace("/", "")


def bmp_exists(images_dir, cmc, card_name):
    """Return True if a converted BMP already exists for this card."""
    bmp_path = os.path.join(images_dir, str(cmc), "converted_files", sanitise_name(card_name) + ".bmp")
    return os.path.isfile(bmp_path)


def download_image(item, images_dir):
    """Download a single card image; return the card name on success or None on failure."""
    url  = item["image_url"]
    cmc  = int(item["cmc"])
    name = item["name"]

    directory = os.path.join(images_dir, str(cmc))
    os.makedirs(directory, exist_ok=True)

    save_path = os.path.join(directory, sanitise_name(name) + ".jpg")
    try:
        session = _get_session()
        response = session.get(url, timeout=30, stream=True)
        response.raise_for_status()
        # Write to a temp file first; rename atomically on success to avoid
        # leaving partial files that could be picked up by the printer.
        tmp_fd, tmp_path = tempfile.mkstemp(dir=directory)
        try:
            with os.fdopen(tmp_fd, 'wb') as tmp_f:
                for chunk in response.iter_content(chunk_size=8192):
                    tmp_f.write(chunk)
            os.replace(tmp_path, save_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        return name
    except Exception as e:
        print(f"Failed to download '{name}': {e}")
        return None


def download_images_from_json(json_file, images_dir):
    """Download all new card images, skipping those whose BMP already exists."""
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Partition into new vs. already-converted cards
    to_download = [item for item in data if not bmp_exists(images_dir, int(item["cmc"]), item["name"])]
    skipped     = len(data) - len(to_download)

    print(f"{len(to_download)} image(s) to download, {skipped} already converted (skipped).")

    downloaded = 0
    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as executor:
        futures = {executor.submit(download_image, item, images_dir): item for item in to_download}
        for future in as_completed(futures):
            if future.result() is not None:
                downloaded += 1

    print(f"Done: {downloaded}/{len(to_download)} image(s) downloaded successfully.")


if __name__ == "__main__":
    args = parse_args()
    json_file = os.path.join(args.data_dir, 'creatures_image_urls.json')
    download_images_from_json(json_file, images_dir=args.images_dir)
