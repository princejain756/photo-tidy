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
