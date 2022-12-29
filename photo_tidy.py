#!/usr/bin/env python3
"""Plan how a folder of photos would be sorted into year/month folders."""

import argparse
import os
import struct
import sys
from collections import namedtuple
from datetime import datetime

SOI = b"\xff\xd8"
APP1 = 0xE1
EOI = 0xD9
SOS = 0xDA
EXIF_PREFIX = b"Exif\x00\x00"
TAG_DATETIME = 0x0132
TAG_EXIF_IFD = 0x8769
TAG_DATETIME_ORIGINAL = 0x9003
TIFF_MAGIC = 42
TYPE_SIZES = {
    1: 1,    # BYTE
    2: 1,    # ASCII
    3: 2,    # SHORT
    4: 4,    # LONG
    5: 8,    # RATIONAL
    6: 1,    # SBYTE
    7: 1,    # UNDEFINED
    8: 2,    # SSHORT
    9: 4,    # SLONG
    10: 8,   # SRATIONAL
    11: 4,   # FLOAT
    12: 8,   # DOUBLE
}
PHOTO_EXTENSIONS = (".jpg", ".jpeg")

Move = namedtuple("Move", "source target taken")
Skip = namedtuple("Skip", "path reason")
Plan = namedtuple("Plan", "root moves skipped")


class ExifError(ValueError):
    """Raised when a JPEG or its EXIF block cannot be understood."""


def _unpack(order, code, buffer, offset):
    try:
        return struct.unpack_from(order + code, buffer, offset)[0]
    except struct.error as exc:
        raise ExifError("truncated EXIF data") from exc


def _as_int(raw, order):
    return int.from_bytes(raw, "little" if order == "<" else "big")


def _ifd(tiff, offset, order):
    """Return ``{tag: raw value bytes}`` for the IFD at *offset*."""
    if offset <= 0 or offset + 2 > len(tiff):
        raise ExifError("IFD offset outside the EXIF block")
    count = _unpack(order, "H", tiff, offset)
    tags = {}
    for index in range(count):
        entry = offset + 2 + index * 12
        if entry + 12 > len(tiff):
            raise ExifError("truncated IFD entry")
        tag = _unpack(order, "H", tiff, entry)
        kind = _unpack(order, "H", tiff, entry + 2)
        amount = _unpack(order, "I", tiff, entry + 4)
        size = TYPE_SIZES.get(kind, 1) * amount
        if size <= 4:
            tags[tag] = tiff[entry + 8:entry + 8 + size]
        else:
            pointer = _unpack(order, "I", tiff, entry + 8)
            tags[tag] = tiff[pointer:pointer + size]
    return tags


def _decode_timestamp(raw):
    text = raw.split(b"\x00", 1)[0].decode("ascii", "replace").strip()
    for pattern in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    raise ExifError("unparsable EXIF date %r" % text)


def parse_datetime(tiff):
    """Decode a TIFF block (the bytes after ``Exif\\0\\0``) to a datetime."""
    if tiff[:2] == b"II":
        order = "<"
    elif tiff[:2] == b"MM":
        order = ">"
    else:
        raise ExifError("unknown byte order marker")
    if _unpack(order, "H", tiff, 2) != TIFF_MAGIC:
        raise ExifError("bad TIFF header")
    tags = _ifd(tiff, _unpack(order, "I", tiff, 4), order)
    raw = tags.get(TAG_DATETIME)
    pointer = tags.get(TAG_EXIF_IFD)
    if pointer:
        sub = _ifd(tiff, _as_int(pointer, order), order)
        raw = sub.get(TAG_DATETIME_ORIGINAL) or raw
    if raw is None:
        raise ExifError("no date tag in the EXIF block")
    return _decode_timestamp(raw)


def read_datetime(path):
    """Return the capture datetime stored in *path*, or ``None``."""
    try:
        with open(path, "rb") as handle:
            if handle.read(2) != SOI:
                return None
            while True:
                head = handle.read(2)
                if len(head) < 2:
                    return None
                code = head[1]
                if code in (EOI, SOS):
                    return None
                if code == 0x01 or 0xD0 <= code <= 0xD7:
                    continue
                size_bytes = handle.read(2)
                if len(size_bytes) < 2:
                    return None
                size = struct.unpack(">H", size_bytes)[0]
                if size < 2:
                    return None
                payload = handle.read(size - 2)
                if code == APP1 and payload[:6] == EXIF_PREFIX:
                    return parse_datetime(payload[6:])
    except (OSError, ExifError):
        return None


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


def build_plan(root, extensions=PHOTO_EXTENSIONS):
    """Plan the moves that sort *root* into year/month folders."""
    root = os.path.abspath(root)
    moves = []
    skipped = []