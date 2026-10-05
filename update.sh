#!/bin/bash
# update.sh — Update Momir Basic card images with the latest Magic sets.
#
# Steps:
#   1. Download the latest AtomicCards.json from MTGJSON
#   2. Fetch image URLs from the Scryfall API
#   3. Download new card images (skips cards already converted to BMP)
#   4. Convert new JPGs to monochrome BMP for the thermal printer
#
# Prerequisites:
#   - settings.cfg (copy settings.cfg.example and set your paths)
#   - python3 with project dependencies: pip install ijson requests
#   - ImageMagick (convert)
#   - curl

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETTINGS_FILE="${SCRIPT_DIR}/settings.cfg"

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
IMAGES_DIR="$(_get_setting IMAGES_DIR)"
DATA_DIR="$(_get_setting DATA_DIR)"

if [ -z "${IMAGES_DIR}" ] || [ -z "${DATA_DIR}" ]; then
    echo "Error: IMAGES_DIR and DATA_DIR must be set in settings.cfg."
    exit 1
fi

echo "=== Momir Basic update ==="
echo "Images directory : ${IMAGES_DIR}"
echo "Data directory   : ${DATA_DIR}"
echo ""

# ---------------------------------------------------------------------------
# 1. Download AtomicCards.json from MTGJSON
# ---------------------------------------------------------------------------
ATOMIC_CARDS_URL="https://mtgjson.com/api/v5/AtomicCards.json.gz"
ATOMIC_CARDS_GZ="${DATA_DIR}/AtomicCards.json.gz"

echo "[1/4] Downloading AtomicCards.json from MTGJSON..."
mkdir -p "${DATA_DIR}"
curl -L --progress-bar -o "${ATOMIC_CARDS_GZ}" "${ATOMIC_CARDS_URL}"
echo "Decompressing..."
gunzip -f "${ATOMIC_CARDS_GZ}"
echo "AtomicCards.json ready."
echo ""

# ---------------------------------------------------------------------------
# 2. Fetch image URLs from Scryfall
# ---------------------------------------------------------------------------
echo "[2/4] Fetching image URLs from Scryfall..."
cd "${SCRIPT_DIR}"
python3 get_image_urls_from_scryfall.py --data-dir "${DATA_DIR}"
echo "Image URLs saved to ${DATA_DIR}/creatures_image_urls.json."
echo ""

# ---------------------------------------------------------------------------
# 3. Download new card images
# ---------------------------------------------------------------------------
echo "[3/4] Downloading new card images to ${IMAGES_DIR}..."
mkdir -p "${IMAGES_DIR}"
python3 download_images_from_scryfall.py --data-dir "${DATA_DIR}" --images-dir "${IMAGES_DIR}"
echo "Images downloaded."
echo ""

# ---------------------------------------------------------------------------
# 4. Convert new JPGs to monochrome BMP
# ---------------------------------------------------------------------------
echo "[4/4] Converting new images to monochrome BMP..."

# Collect all JPGs that have no corresponding BMP yet
mapfile -t JPG_FILES < <(
    find "${IMAGES_DIR}" -mindepth 2 -maxdepth 2 -name "*.jpg" | while IFS= read -r jpg; do
        bmp="${jpg%/*}/converted_files/$(basename "${jpg}" .jpg).bmp"
        [ ! -f "$bmp" ] && echo "$jpg"
    done
)

if [ ${#JPG_FILES[@]} -eq 0 ]; then
    echo "No new images to convert."
else
    echo "Converting ${#JPG_FILES[@]} image(s) in parallel..."
    printf '%s\n' "${JPG_FILES[@]}" | xargs -P "$(nproc)" -I{} bash -c '
        jpg="{}"
        dir="$(dirname "$jpg")"
        name="$(basename "$jpg" .jpg)"
        out="${dir}/converted_files/${name}.bmp"
        mkdir -p "${dir}/converted_files"
        convert "$jpg" -resize 384x -colorspace Gray -monochrome "$out"
    '
fi

echo "Conversion done."
echo ""

echo "=== Update complete! ==="
echo "Converted images are in ${IMAGES_DIR}/<cmc>/converted_files/"
