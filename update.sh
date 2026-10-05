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
#   - settings.cfg (copier settings.cfg.example et adapter les chemins)
#   - python3 avec les dépendances du projet (pip install ijson requests)
#   - ImageMagick (convert)
#   - curl

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETTINGS_FILE="${SCRIPT_DIR}/settings.cfg"

if [ ! -f "${SETTINGS_FILE}" ]; then
    echo "Erreur : settings.cfg introuvable."
    echo "Copie settings.cfg.example vers settings.cfg et adapte les chemins."
    exit 1
fi

# Load settings (strip section headers and comments, then evaluate key=value pairs)
eval "$(grep -v '^\s*[#\[]' "${SETTINGS_FILE}" | grep '=')"

if [ -z "${IMAGES_DIR}" ] || [ -z "${DATA_DIR}" ]; then
    echo "Erreur : IMAGES_DIR et DATA_DIR doivent être définis dans settings.cfg."
    exit 1
fi

echo "=== Mise à jour des cartes Momir Basic ==="
echo "Répertoire des images : ${IMAGES_DIR}"
echo ""

# 1. Télécharger le dernier AtomicCards.json depuis MTGJSON
ATOMIC_CARDS_URL="https://mtgjson.com/api/v5/AtomicCards.json.gz"
ATOMIC_CARDS_GZ="${DATA_DIR}/AtomicCards.json.gz"

echo "[1/4] Téléchargement d'AtomicCards.json depuis MTGJSON..."
mkdir -p "${DATA_DIR}"
curl -L --progress-bar -o "${ATOMIC_CARDS_GZ}" "${ATOMIC_CARDS_URL}"
echo "Décompression..."
gunzip -f "${ATOMIC_CARDS_GZ}"
echo "AtomicCards.json téléchargé."
echo ""

# 2. Récupérer les URLs d'images depuis Scryfall
echo "[2/4] Récupération des URLs d'images depuis Scryfall..."
cd "${SCRIPT_DIR}"
python3 get_image_urls_from_scryfall.py --data-dir "${DATA_DIR}"
echo "URLs récupérées dans ${DATA_DIR}/creatures_image_urls.json."
echo ""

# 3. Télécharger les images dans le répertoire cible
echo "[3/4] Téléchargement des images dans ${IMAGES_DIR}..."
mkdir -p "${IMAGES_DIR}"
# Run from SCRIPT_DIR; scripts read their input files from DATA_DIR.
# The download script writes directly into IMAGES_DIR and skips cards whose BMP already exists.
python3 download_images_from_scryfall.py --data-dir "${DATA_DIR}" --images-dir "${IMAGES_DIR}"
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
