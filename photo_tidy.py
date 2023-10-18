#!/usr/bin/env python3
"""Plan how a folder of photos would be sorted into year/month folders."""

import argparse
import os
import sys

from phototidy.plan import build_plan, display


def main(argv=None):
    parser = argparse.ArgumentParser(prog="photo_tidy", description=__doc__)
    parser.add_argument("directory", help="folder to scan")
    args = parser.parse_args(argv)
    if not os.path.isdir(args.directory):
        parser.error("%s is not a directory" % args.directory)

    plan = build_plan(args.directory)
    for move in plan.moves:
        print("move   %s -> %s" % (display(move.source, plan.root), display(move.target, plan.root)))
    for skip in plan.skipped:
        print("skip   %s (%s)" % (display(skip.path, plan.root), skip.reason))
    print("\n%d to move, %d skipped" % (len(plan.moves), len(plan.skipped)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
