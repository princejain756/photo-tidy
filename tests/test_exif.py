"""Tests for reading capture dates out of JPEG EXIF blocks."""

import os

import pytest

import photo_tidy


def test_reads_datetime_original(make_jpeg):
    path = make_jpeg("shot.jpg", datetime_original="2019:03:14 09:26:53")
    assert photo_tidy.read_datetime(path).isoformat() == "2019-03-14T09:26:53"


def test_falls_back_to_ifd0_datetime(make_jpeg):
    path = make_jpeg("scanned.jpg", datetime_tag="2001:01:02 03:04:05")
    assert photo_tidy.read_datetime(path).year == 2001


def test_prefers_datetime_original_over_ifd0(make_jpeg):
    path = make_jpeg(
        "both.jpg",
        datetime_original="2018:07:04 10:00:00",
        datetime_tag="2001:01:02 03:04:05",
    )
    assert photo_tidy.read_datetime(path).year == 2018


def test_jpeg_without_exif_has_no_date(make_jpeg):
    assert photo_tidy.read_datetime(make_jpeg("plain.jpg")) is None


def test_non_jpeg_file_has_no_date(tmp_path):
    path = tmp_path / "fake.jpg"
    path.write_bytes(b"this is not a jpeg at all")
    assert photo_tidy.read_datetime(str(path)) is None


def test_missing_file_is_not_an_exception(tmp_path):
    assert photo_tidy.read_datetime(str(tmp_path / "gone.jpg")) is None


def test_truncated_exif_block_is_survivable(make_jpeg):
    path = make_jpeg("cut.jpg", datetime_original="2019:03:14 09:26:53")
    with open(path, "rb") as handle:
        data = handle.read()
    with open(path, "wb") as handle:
        handle.write(data[:24])
    assert photo_tidy.read_datetime(path) is None


def test_unparsable_date_is_not_an_exception(make_jpeg):
    path = make_jpeg("odd.jpg", datetime_original="not a date at all")
    assert photo_tidy.read_datetime(path) is None


def test_iter_photos_returns_images_only(photo_root):
    found = photo_tidy.iter_photos(photo_root)
    names = sorted(os.path.basename(path) for path in found)
    assert names == ["a.jpg", "b.JPG", "c.jpeg", "undated.jpg"]


def test_iter_photos_of_empty_folder_is_empty(tmp_path):
    assert photo_tidy.iter_photos(str(tmp_path)) == []


def test_main_lists_each_photo(photo_root, capsys):
    assert photo_tidy.main([photo_root]) == 0
    out = capsys.readouterr().out
    assert "2019-03-14 09:26:53" in out
    assert "undated" in out.split("unknown")[1]


def test_main_rejects_missing_folder(tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        photo_tidy.main([str(tmp_path / "nope")])
    assert excinfo.value.code == 2
