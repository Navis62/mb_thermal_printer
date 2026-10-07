import argparse
import gzip
import json
import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Scryfall bulk data: one card object per Oracle ID (https://scryfall.com/docs/api/bulk-data)
BULK_DATA_URL = 'https://api.scryfall.com/bulk-data/oracle-cards'
# Name of the downloaded bulk file, inside --data-dir
BULK_FILENAME = 'oracle-cards.jsonl.gz'
# Scryfall requires a descriptive User-Agent and an Accept header on every request
SCRYFALL_HEADERS = {
    'User-Agent': 'MomirThermalPrinter/1.0',
    'Accept': 'application/json;q=0.9,*/*;q=0.8',
}

# Layouts that are not real cards (the bulk file also contains them)
EXCLUDED_LAYOUTS = {'token', 'double_faced_token', 'emblem', 'art_series'}


def parse_args():
    parser = argparse.ArgumentParser(description="Fetch creature card image URLs from Scryfall.")
    parser.add_argument(
        "--data-dir",
        default=".",
        help="Directory where the Scryfall bulk file is downloaded and where "
             "creatures_image_urls.json will be written (default: current directory)."
    )
    return parser.parse_args()


def make_session():
    """Return a requests.Session with Scryfall headers and retry/backoff on 429/5xx."""
    retry = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
    )
    session = requests.Session()
    session.headers.update(SCRYFALL_HEADERS)
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def write_atomically(path, write):
    """Call write(file) on a .part file, then rename it to path once complete."""
    tmp_path = path + ".part"
    try:
        with open(tmp_path, 'wb') as f:
            write(f)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def download_bulk_file(session, dest_path):
    """Download the Oracle Cards bulk file (JSON Lines, gzip) to dest_path."""
    response = session.get(BULK_DATA_URL, timeout=30)
    response.raise_for_status()
    info = response.json()
    url = info.get('jsonl_download_uri')
    if not url:
        raise RuntimeError(f"No 'jsonl_download_uri' in the Scryfall bulk-data answer: {sorted(info)}")

    size_mb = info.get('compressed_size', 0) / 1e6
    print(f"Downloading {url} ({size_mb:.0f} MB)…")

    def write(f):
        with session.get(url, timeout=60, stream=True) as r:
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=1 << 16):
                f.write(chunk)

    write_atomically(dest_path, write)


def is_legal_somewhere(card):
    """Return True if the card is legal, restricted or banned in at least one format.

    Cards that are "not_legal" everywhere are Un-set / joke cards.
    """
    return any(status != 'not_legal' for status in card.get('legalities', {}).values())


def is_arena_only(card):
    """Return True for digital-only Alchemy cards, which only exist on MTG Arena."""
    games = set(card.get('games', []))
    return bool(games) and games <= {'arena'}


def is_valid_creature(card):
    """Return True if the card is a real, printable creature card."""
    return (
        'Creature' in card.get('type_line', '')
        and card.get('layout') not in EXCLUDED_LAYOUTS
        and is_legal_somewhere(card)
        and not is_arena_only(card)
        and not card.get('name', '').startswith('A-')
    )


def get_image_url(card):
    """Return the 'normal' (488x680) image URL of a Scryfall card, or None if it has none.

    That is plenty for a 384 px wide thermal print and about half the size of 'large'.
    Double-faced cards (transform, modal DFC) have no top-level "image_uris":
    the images are on each face, so fall back to the front face.
    """
    image_uris = card.get('image_uris')
    if not image_uris:
        faces = card.get('card_faces') or [{}]
        image_uris = faces[0].get('image_uris')
    return image_uris.get('normal') if image_uris else None


def iter_cards(bulk_path):
    """Yield the card objects of a bulk file, one JSON object per line (streamed)."""
    with open(bulk_path, 'rb') as raw:
        is_gzip = raw.read(2) == b'\x1f\x8b'
    opener = gzip.open if is_gzip else open
    with opener(bulk_path, 'rt', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_creature_records(bulk_path):
    """Return the {name, image_url, cmc} records of all creature cards in a bulk file."""
    records = []
    for card in iter_cards(bulk_path):
        if not is_valid_creature(card):
            continue
        image_url = get_image_url(card)
        if image_url is None or 'cmc' not in card:
            print(f"Missing image or cmc for card '{card.get('name', '?')}'")
            continue
        records.append({
            "name":      card["name"],
            "image_url": image_url,
            "cmc":       card["cmc"],
        })
    return records


def main():
    args = parse_args()
    bulk_path   = os.path.join(args.data_dir, BULK_FILENAME)
    output_path = os.path.join(args.data_dir, 'creatures_image_urls.json')
    os.makedirs(args.data_dir, exist_ok=True)

    with make_session() as session:
        download_bulk_file(session, bulk_path)

    print("Extracting creatures…")
    records = load_creature_records(bulk_path)

    write_atomically(output_path, lambda f: f.write(json.dumps(records).encode('utf-8')))
    print(f"Saved {len(records)} image URLs to {output_path}")


if __name__ == "__main__":
    main()
