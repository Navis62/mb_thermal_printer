#!/bin/bash
# update.sh — Update Momir Basic card images with the latest Magic sets.
#
# Steps:
#   1. Download the Scryfall bulk data and extract the list of creature cards
#   2. Download new card images (skips cards already converted to BMP)
#   3. Convert new JPGs to monochrome BMP for the thermal printer
#   4. Clean up temporary files (JPGs, Scryfall bulk file, creatures_image_urls.json)
#
# Options:
#   --refresh   download and convert every card again, even the ones already
#               converted (to apply new conversion settings to the whole library;
#               needs about 2 GB of free disk space while it runs)
#   --prune     delete the BMPs of cards that are no longer in the card list
#   -h, --help  show this help
#
# Environment:
#   PYTHON=/path/to/python   interpreter to use (default: python3), e.g. the one
#                            of a virtualenv: PYTHON=.venv/bin/python ./scripts/update.sh
#   CONVERT_WORKERS=2        limit the conversion processes (default: all CPUs)
#                            on low-memory boards such as the Pi Zero 2
#
# Prerequisites:
#   - settings.cfg (copy settings.cfg.example and set your paths)
#   - python3 with project dependencies: pip install -r requirements.txt

set -e

# Card names contain accents/symbols (e.g. "Ratonhnhaké:ton"): force UTF-8 for output and
# file names so a non-UTF-8 terminal locale (latin-1, C) cannot make downloads fail
export PYTHONUTF8=1

usage() {
    sed -n '/^# Options:/,/^# Prerequisites:/p' "${BASH_SOURCE[0]}" | sed '$d; s/^# \{0,1\}//'
}

DOWNLOAD_ARGS=()
CONVERT_ARGS=()
for arg in "$@"; do
    case "${arg}" in
        --refresh) DOWNLOAD_ARGS+=(--force); CONVERT_ARGS+=(--force) ;;
        --prune)   DOWNLOAD_ARGS+=(--prune) ;;
        -h|--help) usage; exit 0 ;;
        *)         echo "Unknown option: ${arg}" >&2; usage >&2; exit 1 ;;
    esac
done

PYTHON="${PYTHON:-python3}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "${SCRIPT_DIR}")"
SETTINGS_FILE="${ROOT_DIR}/settings.cfg"

if [ ! -f "${SETTINGS_FILE}" ]; then
    echo "Error: settings.cfg not found."
    echo "Copy settings.cfg.example to settings.cfg and set your paths."
    exit 1
fi

# Parse only known keys from settings.cfg (avoids arbitrary code execution)
_get_setting() {
    grep -v '^\s*[#\[]' "${SETTINGS_FILE}" \
        | grep "^\s*$1\s*=" \
        | tail -1 \
        | cut -d'=' -f2- \
        | tr -d '\r' \
        | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}

# Expand a leading "~" like momir_basic.py does (os.path.expanduser)
_expand_tilde() {
    case "$1" in
        "~"|"~/"*) printf '%s' "${HOME}${1#\~}" ;;
        *)         printf '%s' "$1" ;;
    esac
}
IMAGES_DIR="$(_expand_tilde "$(_get_setting IMAGES_DIR)")"
DATA_DIR="$(_expand_tilde "$(_get_setting DATA_DIR)")"

if [ -z "${IMAGES_DIR}" ] || [ -z "${DATA_DIR}" ]; then
    echo "Error: IMAGES_DIR and DATA_DIR must be set in settings.cfg."
    exit 1
fi

echo "=== Momir Basic update ==="
echo "Images directory : ${IMAGES_DIR}"
echo "Data directory   : ${DATA_DIR}"
echo ""

# ---------------------------------------------------------------------------
# 1. Download the Scryfall bulk data and extract the creature cards
# ---------------------------------------------------------------------------
echo "[1/4] Fetching the list of creature cards from Scryfall..."
mkdir -p "${DATA_DIR}"
cd "${SCRIPT_DIR}"
"${PYTHON}" get_image_urls_from_scryfall.py --data-dir "${DATA_DIR}"
echo "Image URLs saved to ${DATA_DIR}/creatures_image_urls.json."
echo ""

# ---------------------------------------------------------------------------
# 2. Download new card images
# ---------------------------------------------------------------------------
echo "[2/4] Downloading new card images to ${IMAGES_DIR}..."
mkdir -p "${IMAGES_DIR}"
DOWNLOAD_FAILED=0
# Failed downloads must not prevent converting the images that did arrive
"${PYTHON}" download_images_from_scryfall.py --data-dir "${DATA_DIR}" --images-dir "${IMAGES_DIR}" \
    "${DOWNLOAD_ARGS[@]}" || DOWNLOAD_FAILED=1
echo "Image download step finished."
echo ""

# ---------------------------------------------------------------------------
# 3. Convert new JPGs to monochrome BMP
# ---------------------------------------------------------------------------
echo "[3/4] Converting new images to monochrome BMP..."

# CONVERT_WORKERS limits the parallel processes (e.g. CONVERT_WORKERS=2 on a Pi Zero 2)
"${PYTHON}" convert_images.py --images-dir "${IMAGES_DIR}" --workers "${CONVERT_WORKERS:-$(nproc)}" \
    "${CONVERT_ARGS[@]}"

echo "Conversion done."
echo ""

# ---------------------------------------------------------------------------
# 4. Clean up temporary files
# ---------------------------------------------------------------------------
echo "[4/4] Cleaning up temporary files..."

# Remove downloaded JPGs now that they have been converted to BMP
find "${IMAGES_DIR}" -mindepth 2 -maxdepth 2 -name "*.jpg" -delete
echo "JPG files removed."

# Remove the Scryfall bulk file (only needed during this run)
BULK_FILE="${DATA_DIR}/oracle-cards.jsonl.gz"
if [ -f "${BULK_FILE}" ]; then
    rm -f "${BULK_FILE}"
    echo "oracle-cards.jsonl.gz removed."
fi

# Remove creatures_image_urls.json (regenerated on every run)
CREATURES_JSON="${DATA_DIR}/creatures_image_urls.json"
if [ -f "${CREATURES_JSON}" ]; then
    rm -f "${CREATURES_JSON}"
    echo "creatures_image_urls.json removed."
fi

echo "Cleanup done."
echo ""

if [ "${DOWNLOAD_FAILED}" -ne 0 ]; then
    echo "=== Update finished with errors ==="
    echo "Some images could not be downloaded (see messages above). Re-run this script to retry."
    exit 1
fi

echo "=== Update complete! ==="
echo "Converted images are in ${IMAGES_DIR}/<cmc>/converted_files/"
