#!/bin/bash
# setup.sh — First-time installation on a Raspberry Pi (Raspberry Pi OS).
#
# What it does (safe to re-run):
#   1. Installs the system packages
#   2. Enables the I2C bus and the hardware serial port, disables the serial login console
#   3. Gives your user access to the hardware (groups i2c, dialout, gpio)
#   4. Creates the Python virtual environment (.venv) and installs requirements.txt
#   5. Creates settings.cfg from settings.cfg.example if it does not exist
#   6. Installs and enables the systemd service (deploy/momir.service, adapted to your
#      user and to the location of this repository)
#
# Usage:  ./setup.sh [-y]      (-y: do not ask questions, do not reboot)
# Run it as your normal user, not with sudo: it asks for your password when needed.
#
# It does NOT download the card images (that takes a while on a Pi Zero 2):
# run ./scripts/update.sh afterwards, or prepare them on a PC and copy them (see README).

set -e

ASSUME_YES=0
case "${1:-}" in
    "") ;;
    -y|--yes) ASSUME_YES=1 ;;
    *) echo "Usage: $0 [-y]"; exit 1 ;;
esac

if [ "$(id -u)" -eq 0 ]; then
    echo "Error: do not run this script as root or with sudo."
    echo "Run it as your normal user (./setup.sh); it asks for your password when needed."
    exit 1
fi

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_NAME="$(id -un)"
SERVICE_NAME="momir"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
SETTINGS_FILE="${APP_DIR}/settings.cfg"

step() { printf '\n=== %s ===\n' "$1"; }
warn() { printf 'Warning: %s\n' "$1" >&2; }
# LC_ALL=C: apt-cache output is localized ("Candidat :" in French)
has_apt_package() { LC_ALL=C apt-cache policy "$1" 2>/dev/null | grep -q 'Candidate: [^(]'; }

REQ_TMP=""
UNIT_TMP=""
trap 'rm -f "${REQ_TMP}" "${UNIT_TMP}"' EXIT

# systemd splits ExecStart on spaces and the unit is written from these values: refuse unsafe ones now
case "${APP_DIR}" in
    *[[:space:]]*)
        echo "Error: the folder '${APP_DIR}' contains a space, which systemd cannot handle in ExecStart."
        echo "Move the repository to a path without spaces and run ./setup.sh again."
        exit 1 ;;
esac
case "${USER_NAME}" in
    ""|*[!A-Za-z0-9._-]*)
        echo "Error: the user name '${USER_NAME}' has characters that are not safe in a systemd unit."
        exit 1 ;;
esac

echo "Installing for user '${USER_NAME}' in ${APP_DIR}"

# ---------------------------------------------------------------------------
# 1. System packages
# ---------------------------------------------------------------------------
step "[1/6] System packages"
if ! command -v apt-get > /dev/null; then
    echo "Error: apt-get not found. This script targets Raspberry Pi OS / Debian."
    exit 1
fi
sudo apt-get update -qq
# python3-pil: Pillow without compiling it (slow on a Pi Zero 2); python3-serial: pyserial
sudo apt-get install -y python3-venv python3-pip python3-pil python3-serial i2c-tools

# RPi.GPIO: use the distribution package when there is one (no compilation), otherwise
# pip builds it, which needs a compiler and the Python headers.
if has_apt_package python3-rpi.gpio; then
    sudo apt-get install -y python3-rpi.gpio
elif has_apt_package python3-rpi-lgpio; then
    sudo apt-get install -y python3-rpi-lgpio
else
    sudo apt-get install -y python3-dev build-essential
fi

# Is the RPi.GPIO module already provided by apt (python3-rpi.gpio or python3-rpi-lgpio)?
# If so, pip must not build or reinstall it.
if python3 -c 'import RPi.GPIO' > /dev/null 2>&1; then
    GPIO_FROM_APT=1
else
    GPIO_FROM_APT=0
fi

# ---------------------------------------------------------------------------
# 2. Hardware: I2C (OLED) and serial port (printer)
# ---------------------------------------------------------------------------
step "[2/6] I2C and serial port"
if command -v raspi-config > /dev/null; then
    sudo raspi-config nonint do_i2c 0          # I2C on
    sudo raspi-config nonint do_serial_cons 1  # no login console on the serial port...
    sudo raspi-config nonint do_serial_hw 0    # ...but the serial hardware on
    echo "I2C enabled, serial hardware enabled, serial console disabled."
else
    warn "raspi-config not found: enable I2C and the serial port by hand (see README)."
fi

# ---------------------------------------------------------------------------
# 3. Permissions
# ---------------------------------------------------------------------------
step "[3/6] Hardware access for ${USER_NAME}"
for group in i2c dialout gpio; do
    if getent group "${group}" > /dev/null; then
        sudo usermod -aG "${group}" "${USER_NAME}"
        echo "Added to group ${group}."
    fi
done

# ---------------------------------------------------------------------------
# 4. Python environment
# ---------------------------------------------------------------------------
step "[4/6] Python environment"
cd "${APP_DIR}"
# --system-site-packages: reuse the apt packages (Pillow, RPi.GPIO) instead of compiling them
python3 -m venv --system-site-packages .venv
REQUIREMENTS="requirements.txt"
if [ "${GPIO_FROM_APT}" -eq 1 ]; then
    echo "RPi.GPIO is provided by apt: not installing it with pip."
    REQ_TMP="$(mktemp)"
    grep -vi '^RPi.GPIO' requirements.txt > "${REQ_TMP}" || true
    REQUIREMENTS="${REQ_TMP}"
fi
.venv/bin/pip install -r "${REQUIREMENTS}"

# ---------------------------------------------------------------------------
# 5. Settings
# ---------------------------------------------------------------------------
step "[5/6] settings.cfg"
if [ -f "${SETTINGS_FILE}" ]; then
    echo "settings.cfg already exists, left untouched."
else
    # Default folders in the home directory, instead of the /home/pi examples
    sed -e "s|^IMAGES_DIR=.*|IMAGES_DIR=${HOME}/momir_images|" \
        -e "s|^DATA_DIR=.*|DATA_DIR=${HOME}/momir_data|" \
        settings.cfg.example > "${SETTINGS_FILE}"
    echo "settings.cfg created (images in ${HOME}/momir_images, data in ${HOME}/momir_data)."
fi

# ---------------------------------------------------------------------------
# 6. systemd service
# ---------------------------------------------------------------------------
step "[6/6] systemd service"
UNIT_TMP="$(mktemp)"
# deploy/momir.service is the template: adapt the user, the folder and the Python
sed -e "s|^User=.*|User=${USER_NAME}|" \
    -e "s|^WorkingDirectory=.*|WorkingDirectory=${APP_DIR}|" \
    -e "s|^ExecStart=.*|ExecStart=${APP_DIR}/.venv/bin/python ${APP_DIR}/momir_basic.py|" \
    deploy/momir.service > "${UNIT_TMP}"
for key in User WorkingDirectory ExecStart; do
    grep -q "^${key}=" "${UNIT_TMP}" || { echo "Error: no ${key}= line in deploy/momir.service."; exit 1; }
done
sudo install -m 644 "${UNIT_TMP}" "${SERVICE_PATH}"
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
echo "Service ${SERVICE_NAME} installed and enabled at boot."

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
cat <<EOF

=== Setup complete ===
Next steps:
  1. Get the card images into the folder set as IMAGES_DIR in ${SETTINGS_FILE}
     (default created by this script: ${HOME}/momir_images, if settings.cfg was new):
       ./scripts/update.sh                       (long on a Pi Zero 2: CONVERT_WORKERS=2 ./scripts/update.sh)
     This is slow on a Zero 2 (the Atkinson conversion is pure Python): preparing the images on a PC is recommended.
     or prepare them on a PC and copy them over (see "Faster: prepare the images on a PC" in the README).
  2. Check the buttons: if the mana counter climbs by itself, set BUTTONS_ACTIVE_LOW=true in settings.cfg.
  3. Useful commands:
       systemctl status ${SERVICE_NAME}
       journalctl -u ${SERVICE_NAME} -f
       sudo systemctl restart ${SERVICE_NAME}

A reboot is needed the first time so that the I2C, serial and group changes take effect.
EOF

if [ "${ASSUME_YES}" -eq 1 ]; then
    echo "Reboot the Pi when you are ready:  sudo reboot"
else
    read -r -p "Reboot now? (y/N) " answer || answer=n
    case "${answer}" in
        [yY]*) sudo reboot ;;
        *) echo "Then reboot later with:  sudo reboot" ;;
    esac
fi
