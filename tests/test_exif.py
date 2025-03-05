"""Tests for reading capture dates out of JPEG EXIF blocks."""

import pytest

from phototidy import exif


def test_reads_datetime_original(make_jpeg):
    path = make_jpeg("shot.jpg", datetime_original="2019:03:14 09:26:53")
    assert exif.read_datetime(path).isoformat() == "2019-03-14T09:26:53"


def test_falls_back_to_ifd0_datetime(make_jpeg):
    path = make_jpeg("scanned.jpg", datetime_tag="2001:01:02 03:04:05")
    assert exif.read_datetime(path).year == 2001


def test_prefers_datetime_original_over_ifd0(make_jpeg):
    path = make_jpeg(
        "both.jpg",
        datetime_original="2018:07:04 10:00:00",
        datetime_tag="2001:01:02 03:04:05",
    )
    assert exif.read_datetime(path).year == 2018


def test_jpeg_without_exif_has_no_date(make_jpeg):
    assert exif.read_datetime(make_jpeg("plain.jpg")) is None


def test_non_jpeg_file_has_no_date(tmp_path):
    path = tmp_path / "fake.jpg"
    path.write_bytes(b"this is not a jpeg at all")
    assert exif.read_datetime(str(path)) is None


def test_missing_file_is_not_an_exception(tmp_path):
    assert exif.read_datetime(str(tmp_path / "gone.jpg")) is None


def test_truncated_exif_block_is_survivable(make_jpeg):
    path = make_jpeg("cut.jpg", datetime_original="2019:03:14 09:26:53")
    with open(path, "rb") as handle:
        data = handle.read()
    with open(path, "wb") as handle:
        handle.write(data[:24])
    assert exif.read_datetime(path) is None


def test_unparsable_date_is_not_an_exception(make_jpeg):
    path = make_jpeg("odd.jpg", datetime_original="not a date at all")
    assert exif.read_datetime(path) is None


def test_capture_datetime_without_fallback_ignores_mtime(make_jpeg):
    assert exif.capture_datetime(make_jpeg("plain.jpg")) is None


def test_capture_datetime_can_fall_back_to_mtime(make_jpeg):
    path = make_jpeg("plain.jpg")
    assert exif.capture_datetime(path, fallback_mtime=True) is not None


def test_capture_datetime_prefers_exif_over_mtime(make_jpeg):
    path = make_jpeg("dated.jpg", datetime_original="2019:03:14 09:26:53")
    assert exif.capture_datetime(path, fallback_mtime=True).year == 2019


def test_missing_folder_is_a_usage_error(tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        import photo_tidy

        photo_tidy.main([str(tmp_path / "nope")])
    assert excinfo.value.code == 2


def test_reads_a_big_endian_exif_block(make_jpeg, tmp_path):
    from conftest import jpeg_bytes_big_endian

    path = tmp_path / "motorola.jpg"
    path.write_bytes(jpeg_bytes_big_endian("2017:06:30 12:00:00"))
    assert exif.read_datetime(str(path)).year == 2017


def test_paddings_before_a_marker_are_tolerated(make_jpeg):
    path = make_jpeg("pad.jpg", datetime_original="2019:03:14 09:26:53")
    with open(path, "rb") as handle:
        data = handle.read()
    # Splice junk between the SOI and the APP1 segment.
    broken = data[:2] + b"\xff\x00\xff\x00" + data[2:]
    with open(path, "wb") as handle:
        handle.write(broken)
    assert exif.read_datetime(path) is not None


def test_an_ifd_claiming_more_entries_than_it_has(make_jpeg):
    path = make_jpeg("short.jpg", datetime_original="2019:03:14 09:26:53")
    with open(path, "rb") as handle:
        data = bytearray(handle.read())
    # The EXIF count word sits 12 bytes into the segment payload.
    marker = data.index(b"Exif\x00\x00") + 6 + 8
    data[marker:marker + 2] = b"\xff\x00"
    with open(path, "wb") as handle:
        handle.write(bytes(data))
    assert exif.read_datetime(path) is not None


def test_capture_datetime_mtime_fallback_survives_a_missing_file(tmp_path):
    assert exif.capture_datetime(str(tmp_path / "gone.jpg"), fallback_mtime=True) is None
