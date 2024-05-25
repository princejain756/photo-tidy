"""Tests for the command line entry point."""

import io
import os

import pytest

from phototidy import cli
from phototidy.run import read_journal


def run(argv):
    out = io.StringIO()
    code = cli.main(argv, out=out)
    return code, out.getvalue()


def test_reports_each_planned_move(photo_root):
    code, out = run([photo_root])
    assert code == 0
    assert "move   incoming/a.jpg -> 2019/03/a.jpg" in out


def test_reports_skipped_photos_with_a_reason(photo_root):
    _, out = run([photo_root])
    assert "skip   incoming/undated.jpg (no capture date)" in out


def test_ends_with_a_summary_line(photo_root):
    _, out = run([photo_root])
    assert "3 to move, 1 skipped" in out


def test_a_folder_of_undated_photos_still_reports(tmp_path, make_jpeg):
    make_jpeg("undated.jpg")
    code, out = run([str(tmp_path)])
    assert code == 0
    assert "0 to move, 1 skipped" in out


def test_dry_run_leaves_the_files_alone(photo_root):
    before = sorted(os.listdir(os.path.join(photo_root, "incoming")))
    run([photo_root])
    assert sorted(os.listdir(os.path.join(photo_root, "incoming"))) == before
    assert not os.path.exists(os.path.join(photo_root, ".phototidy"))


def test_run_flag_moves_the_files(photo_root):
    code, out = run([photo_root, "--run"])