import ijson
import argparse
import os
import time
import requests
import json
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Scryfall API endpoint for batch card lookups
SCRYFALL_COLLECTION_URL = 'https://api.scryfall.com/cards/collection'
# Scryfall rate limit: max 10 requests/s — 0.1 s minimum delay
SCRYFALL_DELAY = 0.1
# Maximum identifiers per Scryfall /cards/collection request
BATCH_SIZE = 70
# Scryfall requires a descriptive User-Agent and an Accept header on every request
SCRYFALL_HEADERS = {
    'User-Agent': 'MomirThermalPrinter/1.0',
    'Accept': 'application/json;q=0.9,*/*;q=0.8',
}


def parse_args():
    parser = argparse.ArgumentParser(description="Fetch card image URLs from Scryfall.")
    parser.add_argument(
        "--data-dir",
        default=".",
        help="Directory containing AtomicCards.json and where creatures_image_urls.json "
             "will be written (default: current directory)."
    )
    return parser.parse_args()


def is_valid_creature(card_data):
    """Return True if the card should be included (real creature, not Arena-only or Un-set).

    Arena digital-only reprints are prefixed with "A-" (e.g. "A-Lightning Bolt").
    Using startswith("A-") correctly targets only these prefixed names, avoiding
    false exclusions for cards that happen to contain "A-" elsewhere in their name.
    """
    return (
        "Creature" in card_data["type"]
        and card_data["legalities"]
        and not card_data["name"].startswith("A-")
    )


def load_creatures(atomic_cards_path):
    """Parse AtomicCards.json and return a dict {card name: Scryfall oracle ID}.

    In MTGJSON's AtomicCards format "data" maps each card name to a list of
    printing objects. The file is very large, so it is streamed entry by entry
    (kvitems) instead of being loaded in memory at once, and only the oracle ID
    of each creature is kept.
    """
    creatures = {}
    with open(atomic_cards_path, 'rb') as f:
        for name, printings in ijson.kvitems(f, 'data'):
            try:
                card = printings[0]
                if not is_valid_creature(card):
                    continue
                creatures[name] = card["identifiers"]["scryfallOracleId"]
            except (KeyError, IndexError, TypeError) as e:
                print(f"Skipping card '{name}' due to error: {e!r}")
    return creatures


def make_session():
    """Return a requests.Session with Scryfall headers and retry/backoff on 429/5xx."""
    retry = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"POST"}),  # the collection endpoint is a POST
    )
    session = requests.Session()
    session.headers.update(SCRYFALL_HEADERS)
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def get_image_url(card):
    """Return the 'large' image URL of a Scryfall card, or None if it has none.

    Double-faced cards (transform, modal DFC) have no top-level "image_uris":
    the images are on each face, so fall back to the front face.
    """
    image_uris = card.get("image_uris")
    if not image_uris:
        faces = card.get("card_faces") or [{}]
        image_uris = faces[0].get("image_uris")
    return image_uris.get("large") if image_uris else None


def fetch_batch(session, oracle_ids):
    """POST a batch of oracle IDs to Scryfall and return image URL records."""
    payload = {'identifiers': [{'oracle_id': oid} for oid in oracle_ids]}
    time.sleep(SCRYFALL_DELAY)
    response = session.post(SCRYFALL_COLLECTION_URL, json=payload, timeout=30)
    response.raise_for_status()
    records = []
    for card in response.json().get("data", []):
        image_url = get_image_url(card)
        if image_url is None or "cmc" not in card:
            print(f"Missing image or cmc for card '{card.get('name', '?')}'")
            continue
        records.append({
            "name":      card["name"],
            "image_url": image_url,
            "cmc":       card["cmc"],
        })
    return records


def fetch_all_image_urls(creatures):
    """Fetch image URLs for all creatures in batches and return a list of records."""
    oracle_ids = list(creatures.values())
    total_batches = (len(oracle_ids) + BATCH_SIZE - 1) // BATCH_SIZE
    image_urls = []
    failed_batches = []

    with make_session() as session:
        for i in range(0, len(oracle_ids), BATCH_SIZE):
            batch = oracle_ids[i:i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            try:
                records = fetch_batch(session, batch)
            except requests.exceptions.RequestException as e:
                print(f"Batch {batch_num}/{total_batches} FAILED: {e}")
                failed_batches.append(batch_num)
                continue
            image_urls.extend(records)
            print(f"Batch {batch_num}/{total_batches} done ({len(image_urls)} cards so far)")

    if failed_batches:
        print(f"WARNING: {len(failed_batches)} batch(es) failed ({failed_batches}); "
              "the cards in them are missing. Re-run to retry.")
    return image_urls


def main():
    args = parse_args()
    atomic_cards_path = os.path.join(args.data_dir, 'AtomicCards.json')
    output_path       = os.path.join(args.data_dir, 'creatures_image_urls.json')

    print("Loading creatures from AtomicCards.json…")
    creatures = load_creatures(atomic_cards_path)
    print(f"{len(creatures)} creatures found. Fetching image URLs from Scryfall…")

    image_urls = fetch_all_image_urls(creatures)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(image_urls, f)
    print(f"Saved {len(image_urls)} image URLs to {output_path}")


if __name__ == "__main__":
    main()
