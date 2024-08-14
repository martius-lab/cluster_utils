#!/usr/bin/env python3
"""Plot job execution timeline from a cluster_run.log file.

Reads a cluster_utils log file ("cluster_run.log") and generates a timeline plot with
start/interruptions/end of all jobs.
"""
from __future__ import annotations

import argparse
import collections
import datetime
import enum
import logging
import re
import sys
import typing

import matplotlib.pyplot as plt
import matplotlib.ticker
from matplotlib.lines import Line2D

if typing.TYPE_CHECKING:
    import os


class JobStatus(enum.Enum):
    """The different statuses a job can have."""

    FINISHED = 0
    EXIT_FOR_RESUME = 1
    FAILED = 2
    RUNNING = 3
    SUBMITTED = 4
    CLUSTER_UTILS_EXIT = 5


class JobRun(typing.NamedTuple):
    """Represents one run of a job."""

    #: Time when the job starts running.
    start_time: datetime.datetime
    #: Time when the job stops or current time, if it is still running.
    end_time: datetime.datetime
    #: Status of the job at end_time.
    end_status: JobStatus


def parse_cluster_run_log(
    log_file_path: typing.Union[str, os.PathLike], cap_running_jobs_length: bool = False
) -> typing.DefaultDict[int, typing.List[JobRun]]:
    """Parse job submission/start/end-times from log.

    Args:
        log_file_path:  Path to the "cluster_run.log" file.
        cap_running_jobs_length:  If false the end point of jobs that are still running
            is set to the current time. If true, it is limited to not increase the plot
            period too much.  This is useful when viewing old logs where the timestamps
            are far away from now.

    Returns:
        Dictionary mapping job id to a list of runs of that job.
        There is one entry for when the job was submitted to the cluster (with start and
        end time being the same) followed by an entry for the actual run (or multiple
        entries if "exit_for_resume" is used).
    """
    jobs: typing.DefaultDict[int, typing.List[JobRun]] = collections.defaultdict(list)
    job_start = {}
    end_time = None

    first_timestamp = None
    timestamp = None

    with open(log_file_path, "r") as f:
        for i, line in enumerate(f):
            end_reason = None
            if "started on hostname" in line:
                pass  # nothing to do here
            elif line.endswith("finished successfully.\n") or line.endswith(
                "now sent results after concluding earlier."
            ):
                end_reason = JobStatus.FINISHED
            elif line.endswith("exited to be resumed.\n"):
                end_reason = JobStatus.EXIT_FOR_RESUME
            elif line.endswith("Considering job failed.\n") or line.endswith(
                # Keeping this line for backwards compability
                "announced it end but no results were sent.\n"
            ):
                end_reason = JobStatus.FAILED
            elif line.endswith("submitted.\n"):
                end_reason = JobStatus.SUBMITTED
            elif line.endswith("INFO - Exiting now\n"):
                # this is not about a specific job, just get the timestamp and continue
                date_str = line.split(" - ", 1)[0]
                # the log uses "," instead of "." which datetime doesn't expect
                date_str = date_str.replace(",", ".")
                end_time = datetime.datetime.fromisoformat(date_str)
                continue
            else:
                # ignore this line
                continue

            m = re.match("(.*) - cluster_utils - INFO - Job (with id )?([0-9]+) ", line)
            if m is None:
                raise RuntimeError("Failed to parse the following line: %s" % line)

            job_id = int(m.group(3))
            # the log uses "," instead of "." which datetime doesn't expect
            datetime_str = m.group(1).replace(",", ".")
            timestamp = datetime.datetime.fromisoformat(datetime_str)
            if end_reason is None:
                job_start[job_id] = timestamp

                # get start of first job (use it as start of the whole run)
                if first_timestamp is None:
                    first_timestamp = timestamp
            else:
                # special handling for 'SUBMITTED' which starts and ends here
                if end_reason == JobStatus.SUBMITTED:
                    job_start[job_id] = timestamp

                try:
                    jobs[job_id].append(
                        JobRun(job_start[job_id], timestamp, end_reason)
                    )
                    del job_start[job_id]
                except KeyError as e:
                    logging.error(
                        "Job %s ended but no start was detected [line %d: %s]",
                        e,
                        i,
                        line.strip(),
                    )

    # handle jobs that are not listed as ended in the log
    if job_start:
        if end_time is None:
            logging.warning(
                "The following jobs have start times without end: %s", job_start.keys()
            )

            end_time = datetime.datetime.now()

            if cap_running_jobs_length:
                # get difference between last and first timestamp that was read from the
                # log to get the time span of the plot
                assert first_timestamp is not None
                assert timestamp is not None
                log_duration = timestamp - first_timestamp

                # Set the end time of running jobs to now, but cap it if it exceeds the
                # log duration by more than 40%
                max_end_time = timestamp + 0.4 * log_duration
                if end_time > max_end_time:
                    end_time = max_end_time

            job_status = JobStatus.RUNNING
        else:
            job_status = JobStatus.CLUSTER_UTILS_EXIT

        for job_id, start_time in job_start.items():
            jobs[job_id].append(JobRun(start_time, end_time, job_status))

    return jobs


def plot_timeline(
    jobs: typing.Dict[int, typing.List[JobRun]],
    save_to_file: typing.Optional[str] = None,
) -> None:
    fig, ax = plt.subplots()
    ax.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(1))
    prop_cycle = plt.rcParams["axes.prop_cycle"]
    colors = prop_cycle.by_key()["color"]
    markers = {
        JobStatus.SUBMITTED: "o",
        JobStatus.EXIT_FOR_RESUME: "v",
        JobStatus.FINISHED: "s",
        JobStatus.FAILED: "X",
        JobStatus.RUNNING: ">",
        JobStatus.CLUSTER_UTILS_EXIT: "|",
    }
    for job_id, intervals in jobs.items():
        color = colors[job_id % len(colors)]
        for interval in intervals:
            ax.plot(
                [interval.start_time, interval.end_time],  # type: ignore
                [job_id, job_id],
                "-",
                lw=3,
                color=color,
                marker=markers[interval.end_status],
                markevery=[1],
            )

    legend_elements = [
        Line2D(
            [0],
            [0],
            marker=marker,
            color="black",
            linestyle="none",
            label=reason.name,
            markersize=7,
        )
        for reason, marker in markers.items()
    ]
    ax.legend(handles=legend_elements)
    ax.set_title("cluster_utils job execution flow")
    ax.set_xlabel("Time")
    ax.set_ylabel("Job ID")

    yticks_len = len(ax.get_yticks())
    xticks_len = len(ax.get_xticks())
    size = plt.gcf().get_size_inches()
    if xticks_len > 3 and yticks_len > 20:
        plt.gcf().set_size_inches(
            size[0] * int(xticks_len // 3), size[1] * int(yticks_len // 20)
        )

    if save_to_file:
        plt.savefig(save_to_file)
    else:
        plt.show()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "cluster_utils_log_file", type=str, help="Path to the cluster_run.log file."
    )
    parser.add_argument(
        "--cap-running-jobs",
        action="store_true",
        help="""If set, limit the end point of running jobs in the plot.  Useful for
            older logs.
        """,
    )
    parser.add_argument(
        "--save",
        type=str,
        metavar="FILE",
        help="Do not show plot but save to the specified file.",
    )
    args = parser.parse_args()

    try:
        jobs = parse_cluster_run_log(
            args.cluster_utils_log_file, cap_running_jobs_length=args.cap_running_jobs
        )
    except Exception as e:
        logging.fatal(e)
        return 1

    plot_timeline(jobs, save_to_file=args.save)

    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
