#!/bin/bash
# update.sh — Met à jour les images de cartes Magic en récupérant les dernières extensions.
#
# Ce script effectue les étapes suivantes :
#   1. Télécharge le dernier fichier AtomicCards.json depuis MTGJSON
#   2. Récupère les URLs d'images depuis l'API Scryfall
#   3. Télécharge les images dans les dossiers par CMC
#   4. Convertit les images en monochrome BMP pour l'imprimante thermique
#
# Prérequis :
#   - python3 avec les dépendances du projet (pip install ijson requests)
#   - ImageMagick (convert)
#   - curl
#
# Usage :
#   ./update.sh [--images-dir <chemin>]
#
#   --images-dir : répertoire où télécharger les images (défaut : ~/Desktop/momir)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGES_DIR="${HOME}/Desktop/momir"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --images-dir)
            IMAGES_DIR="$2"
            shift 2
            ;;
        *)
            echo "Option inconnue : $1"
            echo "Usage : $0 [--images-dir <chemin>]"
            exit 1
            ;;
    esac
done

echo "=== Mise à jour des cartes Momir Basic ==="
echo "Répertoire des images : ${IMAGES_DIR}"
echo ""

# 1. Télécharger le dernier AtomicCards.json depuis MTGJSON
ATOMIC_CARDS_URL="https://mtgjson.com/api/v5/AtomicCards.json.gz"
ATOMIC_CARDS_GZ="${SCRIPT_DIR}/AtomicCards.json.gz"
ATOMIC_CARDS_JSON="${SCRIPT_DIR}/AtomicCards.json"

echo "[1/4] Téléchargement d'AtomicCards.json depuis MTGJSON..."
curl -L --progress-bar -o "${ATOMIC_CARDS_GZ}" "${ATOMIC_CARDS_URL}"
echo "Décompression..."
gunzip -f "${ATOMIC_CARDS_GZ}"
echo "AtomicCards.json téléchargé."
echo ""

# 2. Récupérer les URLs d'images depuis Scryfall
echo "[2/4] Récupération des URLs d'images depuis Scryfall..."
cd "${SCRIPT_DIR}"
python3 get_image_urls_from_scryfall.py
echo "URLs récupérées dans creatures_image_urls.json."
echo ""

# 3. Télécharger les images dans le répertoire cible
echo "[3/4] Téléchargement des images dans ${IMAGES_DIR}..."
mkdir -p "${IMAGES_DIR}"
# Run download script from SCRIPT_DIR (where creatures_image_urls.json lives),
# then move the generated CMC folders to IMAGES_DIR.
cd "${SCRIPT_DIR}"
python3 download_images_from_scryfall.py
# Move any newly created numeric CMC directories to IMAGES_DIR
for cmc_dir in "${SCRIPT_DIR}"/*/; do
    cmc_name="$(basename "$cmc_dir")"
    # Only move directories whose names are integers (CMC folders)
    if [[ "$cmc_name" =~ ^[0-9]+$ ]]; then
        target="${IMAGES_DIR}/${cmc_name}"
        if [ -d "$target" ]; then
            # Merge: move individual files so we don't overwrite existing ones
            while IFS= read -r f; do
                dest="${target}/$(basename "$f")"
                [ -f "$dest" ] || mv "$f" "$dest"
            done < <(find "$cmc_dir" -maxdepth 1 -name "*.jpg")
            rm -rf "$cmc_dir"
        else
            mv "$cmc_dir" "$target"
        fi
    fi
done
echo "Images téléchargées."
echo ""

# 4. Convertir les images en monochrome BMP
echo "[4/4] Conversion des images en monochrome..."
for dir in "${IMAGES_DIR}"/*/; do
    if [ -d "$dir" ]; then
        # Check for JPG files using find to avoid glob-expansion issues
        if find "$dir" -maxdepth 1 -name "*.jpg" | grep -q .; then
            mkdir -p "${dir}converted_files"
            while IFS= read -r jpg_file; do
                output_file="${dir}converted_files/$(basename -- "$jpg_file" .jpg).bmp"
                # Ne re-convertit pas les fichiers déjà existants
                if [ ! -f "$output_file" ]; then
                    echo "Conversion : $jpg_file"
                    convert "$jpg_file" -resize 384x -colorspace Gray -monochrome "$output_file"
                fi
            done < <(find "$dir" -maxdepth 1 -name "*.jpg")
        fi
    fi
done
echo "Conversion terminée."
echo ""

echo "=== Mise à jour terminée ! ==="
echo "Les images converties se trouvent dans ${IMAGES_DIR}/<cmc>/converted_files/"
