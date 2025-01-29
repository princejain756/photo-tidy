"""Read the capture date out of a JPEG's EXIF block.

Only the bits photo-tidy needs are implemented: walk the JPEG marker
segments, find the APP1 segment that carries an Exif payload, then read
DateTimeOriginal (or the plain DateTime tag) from the first IFD.  Parsing
uses the standard library so the tool still runs on a bare Python 3.8
install with no dependencies.
"""

import os
import struct
from datetime import datetime

SOI = b"\xff\xd8"
APP1_CODE = 0xE1
EOI_CODE = 0xD9
SOS_CODE = 0xDA
EXIF_PREFIX = b"Exif\x00\x00"
MAX_SEGMENT_SIZE = 0xFFFF
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


class ExifError(ValueError):
    """Raised when a JPEG or its EXIF block cannot be understood."""


def _unpack(order, code, buffer, offset):
    try:
        return struct.unpack_from(order + code, buffer, offset)[0]
    except struct.error as exc:
        raise ExifError("truncated EXIF data") from exc


def _as_int(raw, order):
    return int.from_bytes(raw, "little" if order == "<" else "big")


def _ifd_tags(tiff, offset, order):
    """Return ``{tag: raw value bytes}`` for the IFD at *offset*."""
    if offset <= 0 or offset + 2 > len(tiff):
        raise ExifError("IFD offset outside the EXIF block")
    count = _unpack(order, "H", tiff, offset)
    if offset + 2 + count * 12 > len(tiff):
        # Cameras do write odd counts; read what is actually present.
        count = max(0, (len(tiff) - offset - 2) // 12)
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


def parse_exif_datetime(tiff):
    """Decode a TIFF block (the bytes after ``Exif\\0\\0``) to a datetime."""
    if tiff[:2] == b"II":
        order = "<"
    elif tiff[:2] == b"MM":
        order = ">"
    else:
        raise ExifError("unknown byte order marker")
    if _unpack(order, "H", tiff, 2) != TIFF_MAGIC:
        raise ExifError("bad TIFF header")
    tags = _ifd_tags(tiff, _unpack(order, "I", tiff, 4), order)
    raw = tags.get(TAG_DATETIME)
    pointer = tags.get(TAG_EXIF_IFD)
    if pointer:
        sub = _ifd_tags(tiff, _as_int(pointer, order), order)
        raw = sub.get(TAG_DATETIME_ORIGINAL) or raw
    if raw is None:
        raise ExifError("no date tag in the EXIF block")
    return _decode_timestamp(raw)


def read_datetime(path):
    """Return the capture datetime stored in *path*, or ``None``.

    A file with no EXIF block, no date tag or a mangled date simply comes
    back as ``None``; the caller decides what to do with undated photos.
    """
    try:
        with open(path, "rb") as handle:
            if handle.read(2) != SOI:
                return None
            while True:
                lead = handle.read(1)
                if not lead:
                    return None
                if lead != b"\xff":
                    continue
                second = handle.read(1)
                if not second:
                    return None
                code = second[0]
                if code in (0xFF, 0x00):
                    # Fill byte or a stuffed zero; the real marker follows.
                    continue
                if code in (EOI_CODE, SOS_CODE):
                    return None
                if code == 0x01 or 0xD0 <= code <= 0xD7:
                    continue
                size_bytes = handle.read(2)
                if len(size_bytes) < 2:
                    return None
                size = struct.unpack(">H", size_bytes)[0]
                if size < 2:
                    return None
                if size > MAX_SEGMENT_SIZE:
                    return None
                payload = handle.read(size - 2)
                if code == APP1_CODE and payload[:6] == EXIF_PREFIX:
                    return parse_exif_datetime(payload[6:])
    except (OSError, ExifError):
        return None


def capture_datetime(path, fallback_mtime=False):
    """Capture time from EXIF, optionally falling back to the file mtime.
