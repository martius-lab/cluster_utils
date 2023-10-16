#!/usr/bin/env python3
"""Generate PDF report of a cluster run.

As input it expects the path to a results directory containing a "status.pickle" file
that is automatically saved at the end of very iteration.
"""
import argparse
import contextlib
import logging
import pathlib
import pickle
import sys

from cluster.constants import STATUS_PICKLE_FILE, SUBMISSION_HOOK_STATS_FILE
from cluster.optimizers import Optimizer


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "results_dir",
        type=pathlib.Path,
        help="Directory containing the generated files.",
        metavar="<DIRECTORY>",
    )
    parser.add_argument(
        "output",
        type=pathlib.Path,
        help="Where to save the report.",
        metavar="<FILE>",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output file without asking.",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output."
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[%(asctime)s] [%(name)s | %(levelname)s] %(message)s",
    )

    if not args.results_dir.is_dir():
        logging.fatal("'%s' does not exist or is not a directory", args.results_dir)
        return 1

    status_file = args.results_dir / STATUS_PICKLE_FILE
    if not status_file.exists():
        logging.fatal("Status file '%s' does not exist", status_file)
        return 1

    if not args.force and args.output.exists():
        val = input(f"{args.output} already exists.  Overwrite it? [y/N]: ")
        if val.lower() not in ["y", "yes"]:
            print("Do not overwrite existing file.  Abort.")
            return 1

    with open(status_file, "rb") as f:
        optimizer: Optimizer = pickle.load(f)

    # if submission hook stats are missing (e.g. because this is from an old run, where
    # they haven't been saved yet), simply
    submission_hook_stats_file = args.results_dir / SUBMISSION_HOOK_STATS_FILE
    try:
        with open(submission_hook_stats_file, "rb") as f:
            submission_hook_stats = pickle.load(f)
    except Exception as e:
        logging.error(
            "Failed to load submission hook stats from '%s': %s",
            submission_hook_stats_file,
            e,
        )
        submission_hook_stats = {}

    if not isinstance(optimizer, Optimizer):
        logging.warning("Object loaded from '%s' is not of type Optimizer", status_file)

    # TODO: does this write anything to results_dir?
    optimizer.save_pdf_report(args.output, submission_hook_stats, args.results_dir)

    return 0


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        sys.exit(main())
