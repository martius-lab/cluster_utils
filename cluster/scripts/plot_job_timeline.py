#!/usr/bin/env python3
"""Plot job execution timeline from a cluster_run.log file.

Reads a cluster_utils log file ("cluster_run.log") and generates a timeline plot with
start/interruptions/end of all jobs.
"""
import argparse
import collections
import datetime
import enum
import logging
import os
import re
import sys
import typing

import dateutil.parser
import matplotlib.pyplot as plt  # type: ignore
import matplotlib.ticker  # type: ignore
from matplotlib.lines import Line2D  # type: ignore


class JobStatus(enum.Enum):
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
    log_file_path: typing.Union[str, os.PathLike]
) -> typing.DefaultDict[int, typing.List[JobRun]]:
    """Parse job submission/start/end-times from log.

    Args:
        log_file_path: Path to the "cluster_run.log" file.

    Returns:
        Dictionary mapping job id to a list of runs of that job.
        There is one entry for when the job was submitted to the cluster (with start and
        end time being the same) followed by an entry for the actual run (or multiple
        entries if "exit_for_resume" is used).
    """
    jobs: typing.DefaultDict[int, typing.List[JobRun]] = collections.defaultdict(list)
    job_start = {}
    end_time = None

    with open(log_file_path, "r") as f:
        for i, line in enumerate(f):
            end_reason = None
            if "started on hostname" in line:
                pass  # nothing to do here
            elif line.endswith("finished successfully.\n"):
                end_reason = JobStatus.FINISHED
            elif line.endswith("exited to be resumed.\n"):
                end_reason = JobStatus.EXIT_FOR_RESUME
            elif line.endswith("announced it end but no results were sent.\n"):
                end_reason = JobStatus.FAILED
            elif line.endswith("submitted.\n"):
                end_reason = JobStatus.SUBMITTED
            elif line.endswith("INFO - Exiting now\n"):
                # this is not about a specific job, just get the timestamp and continue
                date_str = line.split(" - ", 1)[0]
                end_time = dateutil.parser.parse(date_str)
                continue
            else:
                # ignore this line
                continue

            m = re.match("(.*) - cluster_utils - INFO - Job (with id )?([0-9]+) ", line)
            if m is None:
                raise RuntimeError("Failed to parse the following line: %s" % line)

            job_id = int(m.group(3))
            timestamp = dateutil.parser.parse(m.group(1))
            if end_reason is None:
                job_start[job_id] = timestamp
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
                        "Job {} ended but no start was detected [line {}: {}]".format(
                            e, i, line.strip()
                        )
                    )

    # handle jobs that are not listed as ended in the log
    if job_start:
        if end_time is None:
            logging.warning(
                "The following jobs have start times without end: {}".format(
                    job_start.keys()
                )
            )
            end_time = datetime.datetime.now()
            job_status = JobStatus.RUNNING
        else:
            job_status = JobStatus.CLUSTER_UTILS_EXIT

        for job_id, start_time in job_start.items():
            jobs[job_id].append(JobRun(start_time, end_time, job_status))

    return jobs


def plot_timeline(jobs: typing.Dict[int, typing.List[JobRun]]):
    fig, ax = plt.subplots()
    # ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
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
                [interval.start_time, interval.end_time],
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

    plt.show()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "cluster_utils_log_file", type=str, help="Path to the cluster_run.log file."
    )
    args = parser.parse_args()

    try:
        jobs = parse_cluster_run_log(args.cluster_utils_log_file)
    except Exception as e:
        logging.fatal(e)
        return 1

    plot_timeline(jobs)

    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
