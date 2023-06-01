#!/usr/bin/env python3
"""Plan how a folder of photos would be sorted into year/month folders."""

import argparse
import os
import sys
from collections import namedtuple

from phototidy.exif import read_datetime

PHOTO_EXTENSIONS = (".jpg", ".jpeg", ".tif", ".tiff", ".png")

Move = namedtuple("Move", "source target taken")
Skip = namedtuple("Skip", "path reason")
Plan = namedtuple("Plan", "root moves skipped")


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


def build_plan(root, extensions=None):
    """Plan the moves that sort *root* into year/month folders."""
    root = os.path.abspath(root)
    extensions = normalise_extensions(extensions)
    moves = []
    skipped = []
    claimed = set()
    for path in iter_photos(root, extensions):
        taken = read_datetime(path)
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
    return Plan(root, moves, skipped)


def display(path, root):
    """*path* relative to *root* when possible, for shorter report lines."""
    try:
        return os.path.relpath(path, root)
    except ValueError:
        return path


def main(argv=None):
    parser = argparse.ArgumentParser(prog="photo_tidy", description=__doc__)
    parser.add_argument("directory", help="folder to scan")
    args = parser.parse_args(argv)
    if not os.path.isdir(args.directory):
        parser.error("%s is not a directory" % args.directory)

    plan = build_plan(args.directory)
    for move in plan.moves:
        print("move   %s -> %s" % (display(move.source, plan.root), display(move.target, plan.root)))
    for skip in plan.skipped:
        print("skip   %s (%s)" % (display(skip.path, plan.root), skip.reason))
    print("\n%d to move, %d skipped" % (len(plan.moves), len(plan.skipped)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
