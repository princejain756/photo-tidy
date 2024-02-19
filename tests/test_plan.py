"""Tests for turning capture dates into year/month move plans."""

import os
from datetime import datetime

from phototidy.plan import (
    PHOTO_EXTENSIONS,
    build_plan,
    display,
    iter_photos,
    month_folder,
    normalise_extensions,
    unique_target,
)


def test_month_folder_uses_zero_padded_parts(tmp_path):
    taken = datetime(2019, 3, 14, 9, 26, 53)
    folder = month_folder(str(tmp_path), taken)
    assert folder == os.path.join(str(tmp_path), "2019", "03")


def test_plan_points_at_year_and_month_folder(photo_root):
    plan = build_plan(photo_root)
    targets = sorted(display(move.target, plan.root) for move in plan.moves)
    assert targets == [
        os.path.join("2019", "03", "a.jpg"),
        os.path.join("2020", "12", "b.JPG"),
        os.path.join("2020", "12", "c.jpeg"),
    ]


def test_plan_keeps_the_original_file_name(photo_root):
    plan = build_plan(photo_root)
    for move in plan.moves:
        assert os.path.basename(move.target) == os.path.basename(move.source)


def test_plan_skips_photos_without_a_date(photo_root):
    plan = build_plan(photo_root)
    skipped = sorted(os.path.basename(item.path) for item in plan.skipped)
    assert skipped == ["undated.jpg"]
    assert plan.skipped[0].reason == "no capture date"


def test_plan_ignores_non_photo_files(photo_root):
    plan = build_plan(photo_root)
    every = [os.path.basename(move.source) for move in plan.moves]
    every += [os.path.basename(item.path) for item in plan.skipped]
    assert "notes.txt" not in every


def test_plan_is_empty_for_a_folder_without_photos(tmp_path):
    plan = build_plan(str(tmp_path))
    assert plan.moves == []
    assert plan.skipped == []


def test_plan_does_not_touch_the_filesystem(photo_root):
    before = sorted(os.listdir(photo_root))
    build_plan(photo_root)
    assert sorted(os.listdir(photo_root)) == before


def test_collision_gets_a_numbered_suffix(make_jpeg):
    first = make_jpeg("same.jpg", datetime_original="2020:05:05 05:05:05", subdir="x")
    make_jpeg("same.jpg", datetime_original="2020:05:05 05:05:05", subdir="y")
    plan = build_plan(os.path.dirname(os.path.dirname(first)))
    targets = [move.target for move in plan.moves]
    assert len(targets) == 2
    assert len(set(targets)) == 2
    assert targets[0].endswith("same.jpg")
    assert targets[1].endswith("same-1.jpg")


def test_collision_avoids_a_file_already_on_disk(make_jpeg, tmp_path):
    existing = tmp_path / "2020" / "05"
    existing.mkdir(parents=True)
    (existing / "same.jpg").write_bytes(b"already here")
    make_jpeg("same.jpg", datetime_original="2020:05:05 05:05:05", subdir="incoming")
    plan = build_plan(str(tmp_path))
    assert plan.moves[0].target.endswith("same-1.jpg")


def test_photo_already_in_place_is_reported(make_jpeg, tmp_path):
    make_jpeg(
        "filed.jpg", datetime_original="2020:05:05 05:05:05", subdir=os.path.join("2020", "05")
    )
    plan = build_plan(str(tmp_path))
    assert plan.moves == []
    assert plan.skipped[0].reason == "already filed"


def test_cli_uses_the_plan_module(photo_root, capsys):
    import photo_tidy

    photo_tidy.main([photo_root])
    assert "move   incoming/a.jpg -> 2019/03/a.jpg" in capsys.readouterr().out


def test_duplicates_are_reported_with_their_keeper(make_jpeg, tmp_path):
    first = make_jpeg("a.jpg", datetime_original="2020:01:01 00:00:00", subdir="in")
    copy = tmp_path / "in" / "copy.jpg"
    copy.write_bytes(open(first, "rb").read())
    plan = build_plan(str(tmp_path), collapse_duplicates=True)
    assert len(plan.duplicates) == 1
    assert plan.duplicates[0].source == first
    assert plan.duplicates[0].duplicate == str(copy)


def test_duplicate_copy_is_skipped_not_moved(make_jpeg, tmp_path):
    first = make_jpeg("a.jpg", datetime_original="2020:01:01 00:00:00", subdir="in")
    copy = tmp_path / "in" / "copy.jpg"
    copy.write_bytes(open(first, "rb").read())
    plan = build_plan(str(tmp_path), collapse_duplicates=True)
    skipped = {os.path.basename(item.path): item.reason for item in plan.skipped}
    assert skipped["copy.jpg"] == "duplicate of a.jpg"
    assert [os.path.basename(move.source) for move in plan.moves] == ["a.jpg"]


def test_duplicates_are_ignored_unless_asked_for(make_jpeg, tmp_path):
    first = make_jpeg("a.jpg", datetime_original="2020:01:01 00:00:00", subdir="in")
    copy = tmp_path / "in" / "copy.jpg"
    copy.write_bytes(open(first, "rb").read())
    plan = build_plan(str(tmp_path))
    assert plan.duplicates == []
    assert len(plan.moves) == 2