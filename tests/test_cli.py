"""Tests for the command line entry point."""

import pytest

import photo_tidy


def test_reports_each_planned_move(photo_root, capsys):
    assert photo_tidy.main([photo_root]) == 0
    out = capsys.readouterr().out
    assert "move   incoming/a.jpg -> 2019/03/a.jpg" in out


def test_reports_skipped_photos_with_a_reason(photo_root, capsys):
    photo_tidy.main([photo_root])
    out = capsys.readouterr().out
    assert "skip   incoming/undated.jpg (no capture date)" in out


def test_ends_with_a_summary_line(photo_root, capsys):
    photo_tidy.main([photo_root])
    assert "3 to move, 1 skipped" in capsys.readouterr().out


def test_a_folder_with_only_photos_without_dates_still_reports(tmp_path, make_jpeg, capsys):
    make_jpeg("undated.jpg")
    assert photo_tidy.main([str(tmp_path)]) == 0
    assert "0 to move, 1 skipped" in capsys.readouterr().out


def test_no_arguments_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as excinfo:
        photo_tidy.main([])
    assert excinfo.value.code == 2
