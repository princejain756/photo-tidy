"""Carry out a plan, recording every move so the last run can be undone.

A run appends one JSON line per completed move to a journal file under
``<root>/.phototidy``.  The journal is written as the run progresses, so a
crash part way through still leaves a truthful record of what moved, and
undo replays the newest journal backwards.
"""

import json
import os
import shutil
import time
from typing import List, NamedTuple

from .plan import display

JOURNAL_DIRECTORY = ".phototidy"
JOURNAL_PREFIX = "journal-"


class Outcome(NamedTuple):
    source: str
    target: str
    error: str


class Result(NamedTuple):
    moved: List[str]
    failed: List[Outcome]
    journal: str


class UndoResult(NamedTuple):
    restored: List[str]
    failed: List[Outcome]
    journal: str


class Transfer(NamedTuple):
    source: str
    target: str


def journal_folder(root):
    return os.path.join(root, JOURNAL_DIRECTORY)


def journal_path(root, stamp=None):
    """Path of a new journal, named so a lexical sort is chronological."""
    stamp = stamp or time.strftime("%Y%m%dT%H%M%S")
    return os.path.join(journal_folder(root), "%s%s.jsonl" % (JOURNAL_PREFIX, stamp))


def list_journals(root):
    """Every journal for *root*, newest last."""
    folder = journal_folder(root)
    if not os.path.isdir(folder):
        return []
    names = [name for name in os.listdir(folder) if name.startswith(JOURNAL_PREFIX)]
    return [os.path.join(folder, name) for name in sorted(names)]


def latest_journal(root):
    journals = list_journals(root)
    return journals[-1] if journals else None


def read_journal(path):
    """The move records stored in *path*, oldest first."""
    records = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except ValueError:
                continue
    return records


def _record(handle, source, target):
    handle.write(json.dumps({"source": source, "target": target}) + "\n")
    handle.flush()
    os.fsync(handle.fileno())


def _move_one(move):
    """Rename, falling back to a copy for a different filesystem."""
    folder = os.path.dirname(move.target)
    if folder:
        os.makedirs(folder, exist_ok=True)
    try:
        os.rename(move.source, move.target)
    except OSError:
        shutil.move(move.source, move.target)


def execute(plan, stamp=None):
    """Perform every move in *plan*, journalling as it goes."""
    os.makedirs(journal_folder(plan.root), exist_ok=True)
    path = journal_path(plan.root, stamp)
    moved = []
    failed = []
    with open(path, "w", encoding="utf-8") as handle:
        for move in plan.moves:
            try:
                _move_one(move)
            except OSError as exc:
                failed.append(Outcome(move.source, move.target, str(exc)))
                continue
            _record(handle, move.source, move.target)
            moved.append(display(move.target, plan.root))
    return Result(moved, failed, path)


def _prune(path, root):
    """Remove *path* and its parents while they are empty, stopping at *root*."""
    current = path
    while os.path.abspath(current) != os.path.abspath(root):
        try:
            os.rmdir(current)
        except OSError:
            return
        current = os.path.dirname(current)


def undo(root, journal=None):
    """Move every file named in *journal* back, newest entry first."""
    root = os.path.abspath(root)
    path = journal or latest_journal(root)
    if path is None:
        raise FileNotFoundError("no journal to undo in %s" % root)

    restored = []
    failed = []
    for record in reversed(read_journal(path)):
        source = record["source"]
        target = record["target"]
        if not os.path.exists(target):
            failed.append(Outcome(target, source, "moved file is gone"))
            continue
        folder = os.path.dirname(source)
        if folder:
            os.makedirs(folder, exist_ok=True)
        try:
            _move_one(Transfer(target, source))
        except OSError as exc:
            failed.append(Outcome(target, source, str(exc)))
            continue
        restored.append(display(source, root))
        _prune(os.path.dirname(target), root)
    return UndoResult(restored, failed, path)
