import argparse
import glob
import os
import sys
from concurrent.futures import ProcessPoolExecutor

from PIL import Image, ImageFilter

from progress import Progress

# Print width of the thermal printer, in dots
PRINTER_WIDTH = 384

# Greys <= BLACK_POINT become black, >= WHITE_POINT become white, GAMMA shapes the ramp between
BLACK_POINT, WHITE_POINT, GAMMA = 60, 170, 1.2
CONTRAST_LUT = [
    round(min(1.0, max(0.0, (v - BLACK_POINT) / (WHITE_POINT - BLACK_POINT))) ** GAMMA * 255)
    for v in range(256)
]

# Suffix of files being written; renamed to .bmp once complete
PARTIAL_SUFFIX = ".part"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert downloaded card JPGs to monochrome BMPs for the thermal printer.")
    parser.add_argument(
        "--images-dir",
        default=".",
        help="Root directory containing the <cmc>/ sub-folders (default: current directory). "
             "BMPs are written to <images-dir>/<cmc>/converted_files/."
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=os.cpu_count() or 1,
        help="Number of parallel conversion processes (default: number of CPUs). "
             "Lower it on low-memory boards such as the Pi Zero 2."
    )
    return parser.parse_args()


def bmp_path(jpg):
    """Return the path of the BMP matching a JPG: <cmc>/converted_files/<name>.bmp."""
    directory, filename = os.path.split(jpg)
    return os.path.join(directory, "converted_files", os.path.splitext(filename)[0] + ".bmp")


def find_pending(images_dir):
    """Return the JPGs (<images-dir>/<cmc>/*.jpg) that have no BMP yet."""
    pattern = os.path.join(glob.escape(images_dir), "*", "*.jpg")
    return [jpg for jpg in sorted(glob.glob(pattern)) if not os.path.isfile(bmp_path(jpg))]


def cleanup_partial_files(images_dir):
    """Remove leftovers of interrupted conversions (<cmc>/converted_files/*.part)."""
    for path in glob.glob(os.path.join(glob.escape(images_dir), "*", "converted_files",
                                       "*" + PARTIAL_SUFFIX)):
        try:
            os.unlink(path)
        except OSError:
            pass


def convert_image(jpg):
    """Convert one JPG to a 1-bit BMP, PRINTER_WIDTH dots wide; return None or an error message.

    The BMP is written to a .part file and renamed on success, so an interrupted
    conversion never leaves a truncated BMP that would be skipped (and printed) later.
    """
    out = bmp_path(jpg)
    tmp = out + PARTIAL_SUFFIX
    try:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with Image.open(jpg) as img:
            height = max(1, round(img.height * PRINTER_WIDTH / img.width))
            gray = img.convert("L").resize((PRINTER_WIDTH, height), Image.Resampling.LANCZOS)
            # Sharpen, then push light greys to white and dark greys to black: otherwise the
            # dithering below speckles the card frame and makes the text unreadable.
            gray = gray.filter(ImageFilter.UnsharpMask(radius=1.2, percent=150, threshold=2))
            gray = gray.point(CONTRAST_LUT)
            gray.convert("1").save(tmp, format="BMP")  # 1-bit conversion uses Floyd-Steinberg dithering
        os.replace(tmp, out)
        return None
    except Exception as e:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return f"{jpg}: {e}"


def convert_all(images_dir, workers=None):
    """Convert every pending JPG in parallel and return the number of failures."""
    cleanup_partial_files(images_dir)
    pending = find_pending(images_dir)
    if not pending:
        print("No new images to convert.")
        return 0

    print(f"Converting {len(pending)} image(s) in parallel...")
    with ProcessPoolExecutor(max_workers=max(1, workers or os.cpu_count() or 1)) as executor:
        progress = Progress(len(pending), "convert")
        errors = []
        for error in executor.map(convert_image, pending, chunksize=8):
            if error:
                errors.append(error)
            progress.tick()

    for error in errors:
        print(f"Failed to convert {error}")
    print(f"Done: {len(pending) - len(errors)}/{len(pending)} image(s) converted.")
    return len(errors)


if __name__ == "__main__":
    args = parse_args()
    failed = convert_all(args.images_dir, args.workers)
    if failed:
        sys.exit(1)
