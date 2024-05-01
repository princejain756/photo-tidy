"""Command line entry point for photo-tidy."""

import argparse
import os
import sys

from . import __version__
from .plan import build_plan, display
from .run import execute, undo


def build_parser():
    parser = argparse.ArgumentParser(
        prog="photo-tidy",
        description="File photos into year/month folders using their EXIF dates.",
    )
    parser.add_argument("directory", help="folder to scan")
    parser.add_argument(
        "--run",
        action="store_true",
        help="actually move the files instead of only printing the plan",
    )
    parser.add_argument(
        "--ext",
        action="append",
        metavar="EXT",
        help="extra file extension to treat as a photo (repeatable)",
    )
    parser.add_argument(
        "--duplicates",
        action="store_true",
        help="report files with identical contents and keep only the oldest",
    )
    parser.add_argument(
        "--mtime",
        action="store_true",
        help="fall back to the file modification time when EXIF has no date",
    )
    parser.add_argument(
        "--undo",
        action="store_true",
        help="move the files from the last run back where they came from",
    )
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def report_plan(plan, out):
    for duplicate in plan.duplicates:
        out.write(
            "dup    %s = %s\n"
            % (display(duplicate.source, plan.root), display(duplicate.duplicate, plan.root))
        )
    for move in plan.moves:
        out.write(
            "move   %s -> %s\n"
            % (display(move.source, plan.root), display(move.target, plan.root))
        )
    for skip in plan.skipped:
        out.write("skip   %s (%s)\n" % (display(skip.path, plan.root), skip.reason))
    out.write("\n%d to move, %d skipped\n" % (len(plan.moves), len(plan.skipped)))


def report_result(result, mode, out, root):
    for outcome in result.failed:
        out.write("failed %s (%s)\n" % (display(outcome.source, root), outcome.error))
    done = len(result.moved) if mode == "move" else len(result.restored)
    out.write("\n%s %d file(s), %d failed\n" % (mode, done, len(result.failed)))
    out.write("journal %s\n" % result.journal)


def main(argv=None, out=None):
    out = out or sys.stdout
    parser = build_parser()
    args = parser.parse_args(argv)

    if not os.path.isdir(args.directory):
        parser.error("%s is not a directory" % args.directory)
    root = os.path.abspath(args.directory)

    if args.undo:
        try:
            result = undo(root)
        except FileNotFoundError as exc:
            out.write("%s\n" % exc)
            return 1
        report_result(result, "restore", out, root)
        return 0 if not result.failed else 1

    plan = build_plan(
        root,
        extensions=args.ext,
        fallback_mtime=args.mtime,
        collapse_duplicates=args.duplicates,
    )
    report_plan(plan, out)
    if not args.run:
        return 0

    result = execute(plan)
    report_result(result, "move", out, root)
    return 0 if not result.failed else 1


if __name__ == "__main__":
    sys.exit(main())
