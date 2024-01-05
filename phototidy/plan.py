"""Work out where every photo should live before anything touches the disk.

Planning is a pure function of the folder contents: it walks the tree,
reads capture dates, and returns the moves it would make.  Collisions are
resolved here (never in the runner) so a dry run shows exactly the names
a real run would produce.
"""

import os
from datetime import datetime
from typing import List, NamedTuple, Optional

from .exif import capture_datetime
from .hashes import find_duplicates

PHOTO_EXTENSIONS = (".jpg", ".jpeg", ".tif", ".tiff", ".png")


class Move(NamedTuple):
    source: str
    target: str
    taken: Optional[datetime]


class Skip(NamedTuple):
    path: str
    reason: str


class Duplicate(NamedTuple):
    source: str
    duplicate: str


class Plan(NamedTuple):
    root: str
    moves: List[Move]
    skipped: List[Skip]
    duplicates: List[Duplicate]


def normalise_extensions(extensions=None):
    """Turn CLI values like ``jpg`` or ``.JPG`` into ``('.jpg',)``."""
    if not extensions:
        return PHOTO_EXTENSIONS
    cleaned = []
    for extension in extensions:
        value = extension.strip().lower()
        if not value:
            continue
        if not value.startswith("."):
            value = "." + value
        if value not in cleaned:
            cleaned.append(value)
    return tuple(cleaned) or PHOTO_EXTENSIONS


def iter_photos(root, extensions=PHOTO_EXTENSIONS):
    """Every candidate photo below *root*, in a stable order."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if not name.startswith("."))
        for name in sorted(filenames):
            if name.startswith("."):
                continue
            if os.path.splitext(name)[1].lower() in extensions:
                found.append(os.path.join(dirpath, name))
    return found


def month_folder(root, taken):
    """The ``<root>/YYYY/MM`` folder a photo taken at *taken* belongs in."""
    return os.path.join(root, "%04d" % taken.year, "%02d" % taken.month)


def _numbered(target, counter):
    stem, extension = os.path.splitext(target)
    return "%s-%d%s" % (stem, counter, extension)


def unique_target(target, claimed=()):
    """*target* itself, or the first free ``-1``, ``-2``... variant."""
    candidate = target
    counter = 1
    while candidate in claimed or os.path.exists(candidate):
        candidate = _numbered(target, counter)
        counter += 1
    return candidate


def build_plan(root, extensions=None, fallback_mtime=False, collapse_duplicates=False):
    """Plan the moves that sort *root* into year/month folders."""
    root = os.path.abspath(root)
    extensions = normalise_extensions(extensions)
    candidates = iter_photos(root, extensions)

    dates = {path: capture_datetime(path, fallback_mtime=fallback_mtime) for path in candidates}
    duplicates = []
    duplicate_of = {}
    if collapse_duplicates:
        for keep, drop in find_duplicates(candidates, dates):
            duplicates.append(Duplicate(keep, drop))
            duplicate_of[drop] = keep

    moves = []
    skipped = []
    claimed = set()
    for path in candidates:
        taken = dates[path]
        if path in duplicate_of:
            skipped.append(Skip(path, "duplicate of %s" % os.path.basename(duplicate_of[path])))
            continue
        if taken is None:
            skipped.append(Skip(path, "no capture date"))
            continue
        folder = month_folder(root, taken)
        if os.path.dirname(path) == folder:
            skipped.append(Skip(path, "already filed"))
            continue
        target = unique_target(os.path.join(folder, os.path.basename(path)), claimed)
        claimed.add(target)
        moves.append(Move(path, target, taken))
    return Plan(root, moves, skipped, duplicates)


def display(path, root):
    """*path* relative to *root* when possible, for shorter report lines."""
    try:
        return os.path.relpath(path, root)
    except ValueError:
        return path
