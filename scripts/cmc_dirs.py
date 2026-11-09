import glob
import os


def is_cmc_dir(name):
    """Return True for a CMC folder name ("0", "7", "16"...), False for anything else ("assets", ".git")."""
    return name.isascii() and name.isdigit()


def glob_in_cmc_dirs(images_dir, *pattern):
    """Return the sorted paths matching <images-dir>/<cmc>/<pattern...>, in CMC folders only.

    IMAGES_DIR may contain other folders (e.g. it points at the repository): they must never
    be converted or cleaned up.
    """
    matches = glob.glob(os.path.join(glob.escape(images_dir), "*", *pattern))
    return sorted(
        path for path in matches
        if is_cmc_dir(os.path.relpath(path, images_dir).split(os.sep)[0])
    )
