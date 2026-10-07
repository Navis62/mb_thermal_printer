import glob
import os
import argparse
import json
import sys
import threading
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Number of parallel download workers
DOWNLOAD_WORKERS = 12

# Suffix of files being downloaded; renamed to .jpg once complete
PARTIAL_SUFFIX = ".part"

# Scryfall asks API clients to identify themselves
HEADERS = {
    'User-Agent': 'MomirThermalPrinter/1.0',
    'Accept': 'image/jpeg;q=0.9,*/*;q=0.8',
}

# Thread-local storage for per-thread HTTP sessions
_thread_local = threading.local()


def _get_session():
    """Return a requests.Session local to the current thread (with retry/backoff on 429/5xx)."""
    if not hasattr(_thread_local, 'session'):
        retry = Retry(
            total=4,
            backoff_factor=1,
            status_forcelist=(429, 500, 502, 503, 504),
        )
        session = requests.Session()
        session.headers.update(HEADERS)
        session.mount("https://", HTTPAdapter(max_retries=retry))
        _thread_local.session = session
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


def jpg_path(images_dir, cmc, card_name):
    """Return the path where the JPG of a card is saved before conversion."""
    return os.path.join(images_dir, str(cmc), sanitise_name(card_name) + ".jpg")


def cleanup_partial_files(images_dir):
    """Remove leftovers of interrupted downloads (<images-dir>/<cmc>/*.part)."""
    for path in glob.glob(os.path.join(glob.escape(images_dir), "*", "*" + PARTIAL_SUFFIX)):
        try:
            os.unlink(path)
        except OSError:
            pass


def download_image(item, images_dir):
    """Download a single card image; return the card name on success or None on failure."""
    url  = item["image_url"]
    cmc  = int(item["cmc"])
    name = item["name"]

    directory = os.path.join(images_dir, str(cmc))
    os.makedirs(directory, exist_ok=True)

    save_path = jpg_path(images_dir, cmc, name)
    try:
        session = _get_session()
        with session.get(url, timeout=30, stream=True) as response:
            response.raise_for_status()
            # Write to a .part file first; rename atomically on success to avoid
            # leaving partial files that could be picked up by the converter.
            tmp_fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=PARTIAL_SUFFIX)
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
    """Download all new card images and return the number of failed downloads.

    Cards whose BMP already exists, or whose JPG was downloaded by a previous
    run but not converted yet, are skipped.
    """
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    cleanup_partial_files(images_dir)

    to_download = []
    converted = pending_conversion = 0
    for item in data:
        cmc, name = int(item["cmc"]), item["name"]
        if bmp_exists(images_dir, cmc, name):
            converted += 1
        elif os.path.isfile(jpg_path(images_dir, cmc, name)):
            pending_conversion += 1
        else:
            to_download.append(item)

    print(f"{len(to_download)} image(s) to download, {converted} already converted, "
          f"{pending_conversion} downloaded and waiting for conversion (skipped).")

    downloaded = 0
    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as executor:
        futures = {executor.submit(download_image, item, images_dir): item for item in to_download}
        for future in as_completed(futures):
            if future.result() is not None:
                downloaded += 1

    failed = len(to_download) - downloaded
    print(f"Done: {downloaded}/{len(to_download)} image(s) downloaded successfully.")
    return failed


if __name__ == "__main__":
    args = parse_args()
    json_file = os.path.join(args.data_dir, 'creatures_image_urls.json')
    failed = download_images_from_json(json_file, images_dir=args.images_dir)
    if failed:
        print(f"WARNING: {failed} image(s) could not be downloaded. Re-run to retry.")
        sys.exit(1)
