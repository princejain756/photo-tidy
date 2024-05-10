"""Find photos that are byte-for-byte duplicates of one another.

The hash is taken over the file contents in fixed-size blocks so that a
multi-gigabyte RAW overflows nothing.  Duplicates are collapsed to a
single keeper: the oldest capture date wins, and on a tie the shallowest
path (then the alphabetically first) stays.
"""

import hashlib
import os
from collections import defaultdict

BLOCK_SIZE = 1 << 20


def file_digest(path, block_size=BLOCK_SIZE):
    """SHA-256 of *path*'s contents, read in blocks."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(block_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def group_by_digest(paths, digest=file_digest):
    """Map every digest to the paths sharing it, dropping unique ones."""
    seen = defaultdict(list)
    for path in paths:
        try:
            seen[digest(path)].append(path)
        except OSError:
            continue
    return {key: found for key, found in seen.items() if len(found) > 1}


def _keeper_order(path, taken_map):
    """Sort key ranking the likeliest original copy first.

    A dated file beats an undated one, an earlier capture beats a later
    one, a shallow path beats a nested one, and a short name beats a
    decorative variant such as ``IMG_0001-copy.jpg``.
    """
    taken = taken_map.get(path)
    depth = os.path.dirname(path).count(os.sep)
    return (taken is None, taken, depth, len(path), path)


def choose_keepers(paths, taken_map=None):
    """Split *paths* into ``(keep, drop)`` for one duplicate group."""
    taken_map = taken_map or {}
    ordered = sorted(paths, key=lambda path: _keeper_order(path, taken_map))
    return ordered[0], ordered[1:]


def find_duplicates(paths, taken_map=None, digest=file_digest):
    """Return a list of ``(source, duplicate)`` pairs to collapse.

    *taken_map* maps a path to its capture date and decides which copy of
    a duplicate is kept.
    """
    pairs = []
    for group in group_by_digest(paths, digest=digest).values():
        if len(group) < 2:
            continue
        keep, drop = choose_keepers(group, taken_map)
        for path in drop:
            pairs.append((keep, path))
    pairs.sort(key=lambda pair: pair[1])
    return pairs
