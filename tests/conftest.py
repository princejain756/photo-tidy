"""Shared helpers that build tiny JPEGs with hand-made EXIF blocks."""

import os
import struct
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TAG_DATETIME = 0x0132
TAG_EXIF_IFD = 0x8769
TAG_DATETIME_ORIGINAL = 0x9003
TYPE_ASCII = 2
TYPE_LONG = 4
ASCII_SIZE = 24


def _entry(tag, kind, count, value):
    return struct.pack("<HHI", tag, kind, count) + value


def tiff_block(datetime_original=None, datetime_tag=None):
    """Build a little-endian TIFF block holding only date tags.

    The layout is laid out by hand: IFD0, then the EXIF sub-IFD, then a
    single data area.  Offsets are absolute from the start of the TIFF
    block, exactly as a camera writes them.
    """
    has_main_text = datetime_tag is not None
    has_sub_ifd = datetime_original is not None

    main_count = int(has_main_text) + int(has_sub_ifd)
    main_ifd_size = 2 + 12 * main_count + 4
    main_data_start = 8 + main_ifd_size
    main_data_size = ASCII_SIZE if has_main_text else 0
    exif_ifd_offset = main_data_start + main_data_size
    exif_text_offset = exif_ifd_offset + (2 + 12 + 4) if has_sub_ifd else None

    main_entries = b""
    if has_main_text:
        assert len(datetime_tag) + 1 <= ASCII_SIZE
        main_entries += _entry(
            TAG_DATETIME, TYPE_ASCII, ASCII_SIZE, struct.pack("<I", main_data_start)
        )
    if has_sub_ifd:
        main_entries += _entry(
            TAG_EXIF_IFD, TYPE_LONG, 1, struct.pack("<I", exif_ifd_offset)
        )

    tiff = b"II" + struct.pack("<H", 42) + struct.pack("<I", 8)
    tiff += struct.pack("<H", main_count) + main_entries + struct.pack("<I", 0)
    if has_main_text:
        tiff += datetime_tag.encode("ascii").ljust(ASCII_SIZE, b"\x00")
    if has_sub_ifd:
        assert len(datetime_original) + 1 <= ASCII_SIZE
        tiff += struct.pack("<H", 1)
        tiff += _entry(
            TAG_DATETIME_ORIGINAL,
            TYPE_ASCII,
            ASCII_SIZE,
            struct.pack("<I", exif_text_offset),
        )
        tiff += struct.pack("<I", 0)
        tiff += datetime_original.encode("ascii").ljust(ASCII_SIZE, b"\x00")
    return tiff


def jpeg_bytes(datetime_original=None, datetime_tag=None, extra_segments=b""):
    """A minimal but structurally valid JPEG carrying an optional EXIF block."""
    out = b"\xff\xd8"
    out += extra_segments
    tiff = tiff_block(datetime_original=datetime_original, datetime_tag=datetime_tag)
    payload = b"Exif\x00\x00" + tiff
    out += b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload
    out += b"\xff\xdb" + struct.pack(">H", 4) + b"\x00\x00"
    out += b"\xff\xda" + struct.pack(">H", 2)
    out += b"\x00\x01\x02\x03\xff\xd9"
    return out


@pytest.fixture
def make_jpeg(tmp_path):
    """Write a JPEG under *tmp_path* and return its path."""

    def _make(name="photo.jpg", datetime_original=None, datetime_tag=None, subdir=""):
        folder = tmp_path / subdir if subdir else tmp_path
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / name
        path.write_bytes(
            jpeg_bytes(datetime_original=datetime_original, datetime_tag=datetime_tag)
        )
        return str(path)

    return _make


@pytest.fixture
def photo_root(tmp_path):
    """A folder tree with dated, undated and non-photo files."""
    root = tmp_path / "library"
    incoming = root / "incoming"
    incoming.mkdir(parents=True)
    for name, taken in (
        ("a.jpg", "2019:03:14 09:26:53"),
        ("b.JPG", "2020:12:01 18:04:00"),
        ("c.jpeg", "2020:12:24 08:00:01"),
    ):
        (incoming / name).write_bytes(jpeg_bytes(datetime_original=taken))
    (incoming / "undated.jpg").write_bytes(jpeg_bytes())
    (incoming / "notes.txt").write_text("not a photo\n")
    return str(root)


def tiff_block_big_endian(datetime_original):
    """The same minimal EXIF block as :func:`tiff_block`, big-endian."""
    text = datetime_original.encode("ascii").ljust(ASCII_SIZE, b"\x00")
    main_count = 1
    main_size = 2 + 12 * main_count + 4
    exif_ifd_offset = 8 + main_size
    text_offset = exif_ifd_offset + (2 + 12 + 4)
    tiff = b"MM" + struct.pack(">H", 42) + struct.pack(">I", 8)
    tiff += struct.pack(">H", main_count)
    tiff += struct.pack(">HHI", TAG_EXIF_IFD, TYPE_LONG, 1) + struct.pack(">I", exif_ifd_offset)
    tiff += struct.pack(">I", 0)
    tiff += struct.pack(">H", 1)
    tiff += struct.pack(">HHI", TAG_DATETIME_ORIGINAL, TYPE_ASCII, ASCII_SIZE)
    tiff += struct.pack(">I", text_offset)
    tiff += struct.pack(">I", 0)
    tiff += text
    return tiff


def jpeg_bytes_big_endian(datetime_original):
    payload = b"Exif\x00\x00" + tiff_block_big_endian(datetime_original)
    return (
        b"\xff\xd8"
        + b"\xff\xe1"
        + struct.pack(">H", len(payload) + 2)
        + payload
        + b"\xff\xda"
        + struct.pack(">H", 2)
        + b"\x00\x01\xff\xd9"
    )
