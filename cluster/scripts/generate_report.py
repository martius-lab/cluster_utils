#!/usr/bin/env python3
"""Generate PDF report of a cluster run.

As input it expects the path to a results directory containing a "status.pickle" file
that is automatically saved at the end of very iteration.
"""
from __future__ import annotations

import argparse
import contextlib
import logging
import pathlib
import pickle
import sys
import typing

import colorama

from cluster import report
from cluster.constants import STATUS_PICKLE_FILE, SUBMISSION_HOOK_STATS_FILE
from cluster.optimizers import Optimizer


def configure_logging(verbose: bool) -> logging.Logger:
    """Configure logger instance."""

    class ColouredFormatter(logging.Formatter):
        STYLES = {
            "WARNING": colorama.Fore.YELLOW,
            "INFO": colorama.Fore.BLUE,
            "DEBUG": colorama.Fore.GREEN,
            "CRITICAL": colorama.Fore.RED + colorama.Style.BRIGHT,
            "ERROR": colorama.Fore.RED,
        }

        def __init__(self, *, fmt):
            logging.Formatter.__init__(self, fmt=fmt)

        def format(self, record: logging.LogRecord) -> str:  # noqa: A003
            msg = super().format(record)
            try:
                return f"{self.STYLES[record.levelname]}{msg}{colorama.Style.RESET_ALL}"
            except KeyError:
                return msg

    log_handler = logging.StreamHandler()
    log_handler.setFormatter(
        ColouredFormatter(fmt="[%(asctime)s] [%(name)s | %(levelname)s] %(message)s")
    )

    logger = logging.getLogger("generate_report")
    logger.addHandler(log_handler)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    return logger


def load_submission_hook_stats(
    results_dir: pathlib.Path, logger: logging.Logger
) -> dict[str, typing.Any]:
    """Load submission hook stats from file.

    Tries to load submission hook stats from the corresponding file in the results
    directory.
    If loading fails (e.g. because the file does not exist) an empty dictionary is
    returned.

    Args:
        results_dir:  Directory containing the file created by cluster utils.
        logger:  Logger instance used for output.

    Returns:
        The loaded submission hook stats or an empty dictionary if loading fails.
    """
    submission_hook_stats_file = results_dir / SUBMISSION_HOOK_STATS_FILE
    try:
        with open(submission_hook_stats_file, "rb") as f:
            submission_hook_stats = pickle.load(f)

        if not isinstance(submission_hook_stats, dict):
            raise TypeError(
                f"Expected dictionary but got {type(submission_hook_stats)}."
            )
    except Exception as e:
        logger.error(
            "Failed to load submission hook stats from '%s': %s",
            submission_hook_stats_file,
            e,
        )
        submission_hook_stats = {}

    return submission_hook_stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "results_dir",
        type=pathlib.Path,
        help="Directory containing the generated files.",
        metavar="RESULTS_DIRECTORY",
    )
    parser.add_argument(
        "output",
        type=pathlib.Path,
        help="Where to save the report.",
        metavar="OUTPUT_FILE",
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

    logger = configure_logging(args.verbose)

    if not args.results_dir.is_dir():
        logger.fatal("'%s' does not exist or is not a directory", args.results_dir)
        return 1

    status_file = args.results_dir / STATUS_PICKLE_FILE
    if not status_file.exists():
        logger.fatal("Status file '%s' does not exist", status_file)
        return 1

    if args.output.exists():
        if args.force:
            logger.warning(
                f"{args.output} already exists but will be overwritten due to --force."
            )
        else:
            val = input(f"{args.output} already exists.  Overwrite it? [y/N]: ")
            if val.lower() not in ["y", "yes"]:
                print("Do not overwrite existing file.  Abort.")
                return 1

    with open(status_file, "rb") as f:
        optimizer: Optimizer = pickle.load(f)

    submission_hook_stats = load_submission_hook_stats(args.results_dir, logger)

    if not isinstance(optimizer, Optimizer):
        logger.warning("Object loaded from '%s' is not of type Optimizer", status_file)

    report.produce_optimization_report(
        optimizer, args.output, submission_hook_stats, args.results_dir
    )
    logger.info("Saved report to %s", args.output)

    return 0


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        sys.exit(main())
