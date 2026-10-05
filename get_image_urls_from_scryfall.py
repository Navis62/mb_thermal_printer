import ijson
import argparse
import os
import time
import requests
import json

# Scryfall API endpoint for batch card lookups
SCRYFALL_COLLECTION_URL = 'https://api.scryfall.com/cards/collection'
# Scryfall rate limit: max 10 requests/s — 0.1 s minimum delay
SCRYFALL_DELAY = 0.1
# Maximum identifiers per Scryfall /cards/collection request
BATCH_SIZE = 70


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

    Cards with names starting with "A-" are digital-only Arena reprints of existing cards
    (e.g. "A-Lightning Bolt") and are intentionally excluded to avoid duplicates.
    Note: using startswith("A-") is deliberately more precise than the original
    'not in' check — it only excludes cards prefixed with "A-", not any card
    whose name happens to contain that substring.
    """
    return (
        "Creature" in card_data["type"]
        and card_data["legalities"]
        and not card_data["name"].startswith("A-")
    )


def load_creatures(atomic_cards_path):
    """Parse AtomicCards.json and return a dict of creature cards keyed by card name."""
    creatures = {}
    with open(atomic_cards_path, 'r', encoding='utf-8') as f:
        for item in ijson.items(f, 'data'):
            try:
                for name, printings in item.items():
                    if is_valid_creature(printings[0]):
                        creatures[name] = printings
            except Exception as e:
                print(f"Skipping card due to error: {e}")
    return creatures


def fetch_batch(session, oracle_ids):
    """POST a batch of oracle IDs to Scryfall and return image URL records."""
    payload = {'identifiers': [{'oracle_id': oid} for oid in oracle_ids]}
    time.sleep(SCRYFALL_DELAY)
    response = session.post(SCRYFALL_COLLECTION_URL, json=payload)
    response.raise_for_status()
    records = []
    for card in response.json().get("data", []):
        try:
            records.append({
                "name":      card["name"],
                "image_url": card["image_uris"]["large"],
                "cmc":       card["cmc"],
            })
        except KeyError as e:
            print(f"Missing field for card '{card.get('name', '?')}': {e}")
    return records


def fetch_all_image_urls(creatures):
    """Fetch image URLs for all creatures in batches and return a list of records."""
    oracle_ids = [v[0]["identifiers"]["scryfallOracleId"] for v in creatures.values()]
    total_batches = (len(oracle_ids) + BATCH_SIZE - 1) // BATCH_SIZE
    image_urls = []

    with requests.Session() as session:
        for i in range(0, len(oracle_ids), BATCH_SIZE):
            batch = oracle_ids[i:i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            try:
                records = fetch_batch(session, batch)
                image_urls.extend(records)
            except requests.exceptions.RequestException as e:
                print(f"Batch {batch_num}/{total_batches} failed: {e}")
            print(f"Batch {batch_num}/{total_batches} done ({len(image_urls)} cards so far)")

    return image_urls


def main():
    args = parse_args()
    atomic_cards_path = os.path.join(args.data_dir, 'AtomicCards.json')
    output_path       = os.path.join(args.data_dir, 'creatures_image_urls.json')

    print("Loading creatures from AtomicCards.json…")
    creatures = load_creatures(atomic_cards_path)
    print(f"{len(creatures)} creatures found. Fetching image URLs from Scryfall…")

    image_urls = fetch_all_image_urls(creatures)

    with open(output_path, 'w') as f:
        json.dump(image_urls, f)
    print(f"Saved {len(image_urls)} image URLs to {output_path}")


if __name__ == "__main__":
    main()
