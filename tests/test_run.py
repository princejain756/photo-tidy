"""Tests for executing a plan and undoing the last run."""

import json
import os
import shutil

import pytest

from phototidy.plan import build_plan
from phototidy.run import (
    execute,
    journal_folder,
    journal_path,
    latest_journal,
    list_journals,
    prune_journals,
    read_journal,
    undo,
)


def sorted_photo(photo_root):
    return build_plan(photo_root)


def test_execute_moves_every_planned_file(photo_root):
    plan = sorted_photo(photo_root)
    result = execute(plan, stamp="20200101T000000")
    assert result.failed == []
    assert len(result.moved) == 3
    for move in plan.moves:
        assert os.path.exists(move.target)
        assert not os.path.exists(move.source)


def test_execute_reports_nothing_for_an_empty_plan(tmp_path):
    result = execute(build_plan(str(tmp_path)), stamp="20200101T000000")
    assert result.moved == []
    assert result.failed == []


def test_execute_writes_a_journal_of_the_moves(photo_root):
    plan = sorted_photo(photo_root)
    result = execute(plan, stamp="20200101T000000")
    records = read_journal(result.journal)
    assert len(records) == 3
    assert {record["target"] for record in records} == {move.target for move in plan.moves}


def test_journal_lives_under_the_photo_tidy_folder(photo_root):
    plan = sorted_photo(photo_root)
    result = execute(plan, stamp="20200101T000000")
    assert os.path.dirname(result.journal) == os.path.join(plan.root, ".phototidy")


def test_journal_name_sorts_chronologically(photo_root):
    root = build_plan(photo_root).root
    first = journal_path(root, "20200101T000000")
    second = journal_path(root, "20200102T000000")
    assert first < second


def test_latest_journal_picks_the_newest(photo_root):
    plan = sorted_photo(photo_root)
    execute(plan, stamp="20200101T000000")
    execute(build_plan(photo_root), stamp="20210303T030303")
    assert latest_journal(plan.root).endswith("20210303T030303.jsonl")


def test_latest_journal_is_none_before_any_run(tmp_path):
    assert latest_journal(str(tmp_path)) is None


def test_list_journals_is_empty_without_the_folder(tmp_path):
    assert list_journals(str(tmp_path)) == []


def test_undo_restores_the_files(photo_root):
    plan = sorted_photo(photo_root)
    execute(plan, stamp="20200101T000000")
    result = undo(plan.root)
    assert result.failed == []
    assert len(result.restored) == 3
    for move in plan.moves:
        assert os.path.exists(move.source)
        assert not os.path.exists(move.target)


def test_undo_removes_the_emptied_month_folders(photo_root):
    plan = sorted_photo(photo_root)
    execute(plan, stamp="20200101T000000")
    undo(plan.root)
    assert not os.path.exists(os.path.join(plan.root, "2019", "03"))
    assert os.path.isdir(plan.root)


def test_undo_keeps_folders_that_still_hold_photos(photo_root):
    plan = sorted_photo(photo_root)
    execute(plan, stamp="20200101T000000")
    stray = os.path.join(plan.root, "2020", "12", "later.jpg")
    with open(stray, "wb") as handle:
        handle.write(b"arrived after the run")
    undo(plan.root)
    assert os.path.isdir(os.path.join(plan.root, "2020", "12"))


def test_undo_without_a_journal_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        undo(str(tmp_path))


def test_undo_reports_files_that_vanished(photo_root):
    plan = sorted_photo(photo_root)
    execute(plan, stamp="20200101T000000")
    os.unlink(plan.moves[0].target)
    outcome = undo(plan.root)
    assert len(outcome.failed) == 1
    assert outcome.failed[0].error == "moved file is gone"


def test_undo_can_target_a_named_journal(photo_root):
    plan = sorted_photo(photo_root)
    first = execute(plan, stamp="20200101T000000")
    execute(build_plan(photo_root), stamp="20200102T000000")
    undo(plan.root, journal=first.journal)
    for move in plan.moves:
        assert os.path.exists(move.source)


def fail_on(monkeypatch, broken_name):
    """Make every transfer of *broken_name* raise, bypassing the fallback."""
    original = os.rename

    def picky(source, target):
        if os.path.basename(source) == broken_name:
            raise OSError("disk full")
        return original(source, target)

    monkeypatch.setattr(os, "rename", picky)
    monkeypatch.setattr(shutil, "move", picky)


def test_execute_reports_a_failed_move(photo_root, monkeypatch):
    plan = sorted_photo(photo_root)
    fail_on(monkeypatch, "b.JPG")
    result = execute(plan, stamp="20200101T000000")
    assert len(result.failed) == 1
    assert result.failed[0].error == "disk full"
    assert len(result.moved) == 2


def test_journal_records_survive_a_partial_run(photo_root, monkeypatch):
    plan = sorted_photo(photo_root)
    fail_on(monkeypatch, "c.jpeg")
    result = execute(plan, stamp="20200101T000000")
    assert len(read_journal(result.journal)) == 2


def test_journal_lines_are_json(photo_root):
    plan = sorted_photo(photo_root)
    result = execute(plan, stamp="20200101T000000")
    with open(result.journal, encoding="utf-8") as handle:
        for line in handle:
            assert set(json.loads(line)) == {"source", "target"}


def test_prune_journals_keeps_the_newest(photo_root):
    plan = sorted_photo(photo_root)
    for day in range(1, 6):
        execute(build_plan(photo_root), stamp="2020010%dT000000" % day)
    stale = prune_journals(plan.root, keep=2)
    assert len(stale) == 3
    assert len(list_journals(plan.root)) == 2


def test_execute_prunes_old_journals_itself(photo_root):
    for day in range(1, 5):
        execute(build_plan(photo_root), stamp="2020010%dT000000" % day, keep_journals=2)
    assert len(list_journals(build_plan(photo_root).root)) == 2


def test_prune_journals_with_no_journals(tmp_path):
    assert prune_journals(str(tmp_path), keep=3) == []


def test_prune_journals_keep_zero_removes_everything(photo_root):
    execute(build_plan(photo_root), stamp="20200101T000000")
    prune_journals(build_plan(photo_root).root, keep=0)
    assert list_journals(build_plan(photo_root).root) == []


def test_undo_deletes_the_journal_it_replayed(photo_root):
    plan = sorted_photo(photo_root)
    result = execute(plan, stamp="20200101T000000")
    undo(plan.root)
    assert not os.path.exists(result.journal)


def test_a_second_undo_reaches_the_earlier_run(photo_root):
    plan = sorted_photo(photo_root)
    execute(plan, stamp="20200101T000000")
    undo(plan.root)
    os.unlink(os.path.join(plan.root, "incoming", "a.jpg"))
    execute(build_plan(plan.root), stamp="20200102T000000")
    undo(plan.root)
    assert sorted(os.listdir(os.path.join(plan.root, "incoming"))) == [
        "b.JPG",
        "c.jpeg",
        "notes.txt",
        "undated.jpg",
    ]


def test_a_failed_undo_keeps_its_journal(photo_root):
    plan = sorted_photo(photo_root)
    result = execute(plan, stamp="20200101T000000")
    os.unlink(plan.moves[0].target)
    undo(plan.root)
    assert os.path.exists(result.journal)


def test_undo_crosses_a_filesystem_via_a_copy(photo_root, monkeypatch):
    plan = sorted_photo(photo_root)
    execute(plan, stamp="20200101T000000")
    real_rename = os.rename
