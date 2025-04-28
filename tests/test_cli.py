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
    assert code == 0
    assert "move 3 file(s), 0 failed" in out
    assert os.path.exists(os.path.join(photo_root, "2019", "03", "a.jpg"))


def test_run_reports_the_journal_it_wrote(photo_root):
    _, out = run([photo_root, "--run"])
    journal = [line for line in out.splitlines() if line.startswith("journal ")][0]
    assert len(read_journal(journal.split(" ", 1)[1])) == 3


def test_undo_puts_the_files_back(photo_root):
    run([photo_root, "--run"])
    code, out = run([photo_root, "--undo"])
    assert code == 0
    assert "restore 3 file(s), 0 failed" in out
    assert os.path.exists(os.path.join(photo_root, "incoming", "a.jpg"))


def test_undo_without_a_previous_run_explains_itself(tmp_path):
    code, out = run([str(tmp_path), "--undo"])
    assert code == 1
    assert "no journal to undo" in out


def test_duplicates_flag_reports_and_skips_the_copy(photo_root):
    copy = os.path.join(photo_root, "incoming", "a-copy.jpg")
    with open(os.path.join(photo_root, "incoming", "a.jpg"), "rb") as handle:
        payload = handle.read()
    with open(copy, "wb") as handle:
        handle.write(payload)
    code, out = run([photo_root, "--duplicates"])
    assert code == 0
    assert "dup    incoming/a.jpg = incoming/a-copy.jpg" in out
    assert "duplicate of a.jpg" in out
    assert "3 to move, 2 skipped" in out


def test_ext_flag_adds_an_extension(tmp_path):
    (tmp_path / "shot.raw").write_bytes(b"raw bytes")
    code, out = run([str(tmp_path), "--ext", "raw", "--mtime"])
    assert code == 0
    assert "1 to move, 0 skipped" in out


def test_mtime_flag_files_undated_photos(tmp_path, make_jpeg):
    make_jpeg("undated.jpg")
    code, out = run([str(tmp_path), "--mtime"])
    assert code == 0
    assert "1 to move, 0 skipped" in out


def test_version_flag_prints_the_version():
    out = io.StringIO()
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--version"], out=out)
    assert excinfo.value.code == 0


def test_missing_directory_is_a_usage_error(tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        run([str(tmp_path / "nope")])
    assert excinfo.value.code == 2


def test_no_arguments_is_a_usage_error():
    with pytest.raises(SystemExit) as excinfo:
        run([])
    assert excinfo.value.code == 2


def test_script_entry_point_delegates_to_the_cli():
    import photo_tidy

    assert photo_tidy.main is cli.main


def test_summary_counts_each_skip_reason(photo_root):
    _, out = run([photo_root])
    assert "1 no capture date" in out


def test_keep_journals_limits_how_many_survive(photo_root):
    from phototidy.run import list_journals

    for _ in range(3):
        cli.main([photo_root, "--run", "--keep-journals", "1"], out=io.StringIO())
        for move in ("2019/03/a.jpg", "2020/12/b.JPG", "2020/12/c.jpeg"):
            target = os.path.join(photo_root, move)
            if os.path.exists(target):
                os.unlink(target)
    assert len(list_journals(photo_root)) == 1


def test_keep_journals_rejects_a_non_number(photo_root):
    with pytest.raises(SystemExit) as excinfo:
        run([photo_root, "--keep-journals", "lots"])
    assert excinfo.value.code == 2


def test_undo_deletes_the_journal_so_it_cannot_replay(photo_root):
    from phototidy.run import list_journals

    cli.main([photo_root, "--run"], out=io.StringIO())
    cli.main([photo_root, "--undo"], out=io.StringIO())
    assert list_journals(photo_root) == []


def test_a_second_undo_after_a_fresh_run_restores_it(photo_root):
    cli.main([photo_root, "--run"], out=io.StringIO())
    cli.main([photo_root, "--undo"], out=io.StringIO())
    cli.main([photo_root, "--run"], out=io.StringIO())
    code, _ = run([photo_root, "--undo"])
    assert code == 0
    assert os.path.exists(os.path.join(photo_root, "incoming", "a.jpg"))
