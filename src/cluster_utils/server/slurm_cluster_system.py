"""ClusterSubmission implementation for Slurm."""

from __future__ import annotations

import logging
import pathlib
import subprocess
import time
from collections import deque
from subprocess import PIPE, run
from typing import Any, NamedTuple, Optional, Sequence

from cluster_utils.base.constants import RETURN_CODE_FOR_RESUME
from cluster_utils.base.settings import SettingsError

from .cluster_system import ClusterJobId, ClusterSubmission, SubmissionError
from .job import Job

# TODO: handle return codes != 0,1,3 ?
_SLURM_RUN_SCRIPT_TEMPLATE = """#!/bin/bash
{sbatch_arg_lines}

# Submission ID {id}

echo "==== Start execution. ===="
echo "Job id: {id}, cluster id: ${{SLURM_JOB_ID}}, hostname: $(hostname), time: $(date)"
echo

{cmd}
rc=$?

echo "==== Finished execution. ===="
if [[ $rc == %(RETURN_CODE_FOR_RESUME)d ]]; then
    echo "Exit with code %(RETURN_CODE_FOR_RESUME)d for resume"
    # do not forward the exit code, as otherwise Slurm will think there was an error
    exit 0
elif [[ $rc != 0 ]]; then
    echo "Failed with exit code $rc"
    # add an indicator file to more easily identify failed jobs
    echo "$rc" > "{run_script_file_path}.FAILED"
    exit $rc
fi
""" % {
    "RETURN_CODE_FOR_RESUME": RETURN_CODE_FOR_RESUME
}


# Possible job State values (according to `man sacct`)
#
#  BF  BOOT_FAIL       Job terminated due to launch failure, typically due to a
#                      hardware failure (e.g. unable to boot the node or block
#                      and the job can not be requeued).
#  CA  CANCELLED       Job was explicitly cancelled by the user or system
#                      administrator.  The job may or may not have been
#                      initiated.
#  CD  COMPLETED       Job has terminated all processes on all nodes with an
#                      exit code of zero.
#  DL  DEADLINE        Job terminated on deadline.
#  F   FAILED          Job terminated with non-zero exit code or other failure
#                      condition.
#  NF  NODE_FAIL       Job terminated due to failure of one or more allocated
#                      nodes.
#  OOM OUT_OF_MEMORY   Job experienced out of memory error.
#  PD  PENDING         Job is awaiting resource allocation.
#  PR  PREEMPTED       Job terminated due to preemption.
#  R   RUNNING         Job currently has an allocation.
#  RQ  REQUEUED        Job was requeued.
#  RS  RESIZING        Job is about to change size.
#  RV  REVOKED         Sibling was removed from cluster due to other cluster
#                      starting the job.
#  S   SUSPENDED       Job has an allocation, but execution has been suspended
#                      and CPUs have been released for other jobs.
#  TO  TIMEOUT         Job terminated upon reaching its time limit.
#
# job_state_good maps state names to a boolean indicating if the state indicates
# that the job failed for some reason (False) or if it either succeeded or is still
# running (True)
#
# TODO: I assigned True/False on what I thought makes sense based on the
# description.  This should be reviewed by someone who is more familiar with Slurm.
SLURM_JOB_STATE_IS_GOOD = {
    "BOOT_FAIL": False,
    "CANCELLED": False,
    "COMPLETED": True,
    "DEADLINE": False,
    "FAILED": False,
    "NODE_FAIL": False,
    "OUT_OF_MEMORY": False,
    "PENDING": True,
    "PREEMPTED": False,
    "RUNNING": True,
    "REQUEUED": True,
    "RESIZING": True,
    "REVOKED": False,
    "SUSPENDED": True,
    "TIMEOUT": False,
}


class SlurmJobRequirements(NamedTuple):
    # names here correspond to options of sbatch

    partition: str
    cpus_per_task: int
    gpus_per_task: int
    mem: str
    time: str

    # exclude specific list of hosts
    exclude: list[str]

    signal: Optional[str]

    # list of arbitrary sbatch options for things that are not covered by the settings
    # above (e.g. something like "--gpu-freq=high")
    extra_submission_options: list[str]

    # keep nodes and ntasks at 1 (use a separate job for each task
    nodes: int = 1
    ntasks: int = 1

    @classmethod
    def from_settings_dict(cls, requirements: dict[str, Any]) -> SlurmJobRequirements:
        logger = logging.getLogger("cluster_utils")

        # create copy so we can pop processed items
        req = dict(requirements)

        try:
            signal_time = req.pop("signal_seconds_to_timeout", None)
            if signal_time:
                signal = f"USR1@{signal_time:d}"
            else:
                signal = None

            obj = cls(
                partition=req.pop("partition"),
                cpus_per_task=req.pop("request_cpus"),
                gpus_per_task=req.pop("request_gpus", 0),
                mem="{}M".format(req.pop("memory_in_mb")),
                time=req.pop("request_time"),
                exclude=req.pop("forbidden_hostnames", []),
                signal=signal,
                extra_submission_options=req.pop("extra_submission_options", []),
            )
        except KeyError as e:
            raise SettingsError(
                f"'cluster_requirements' settings for Slurm require a value for {e}"
                " but none is provided."
            ) from e

        # notify the user of any unused entries in the requirement settings
        for unexpected_key in req:
            logger.error(
                "Settings: cluster_requirements contained entry '%s' which is not"
                " supported by Slurm.  It will be ignored.",
                unexpected_key,
            )

        return obj


class SlurmJobStatus(NamedTuple):
    """Represents the status of Slurm job.

    Attributes:
        state: State of the job as reported by ``sacct`` (COMPLETED, FAILED, ...).
        exit_code: The exit code of the job (undefined if in a non-finished state).
        node_list: Hostname on which the job is executed.
    """

    state: str
    exit_code: int
    node_list: str

    def is_okay(self) -> bool:
        """Check if the state is good or if there was a failure.

        Returns:
            False if in a state that indicates an issue, otherwise True.
        """
        return (
            self.exit_code == 0
            and self.state in SLURM_JOB_STATE_IS_GOOD
            and SLURM_JOB_STATE_IS_GOOD[self.state]
        )


class SBatchArgumentBuilder:
    """Construct an sbatch argument comment block.

    The argument block consists of lines that each start with ``#SBATCH``, followed by
    an argument.
    """

    def __init__(self) -> None:
        self.args: list[str] = []

    def add(self, name: str, value: Any) -> None:
        """Add an argument (will be added as "--name=value")."""
        self.args.append(f"--{name}={value}")

    def extend_raw(self, raw_args: list[str]) -> None:
        """Add list of 'raw' arguments (i.e. already in the form '--name=value')."""
        self.args.extend(raw_args)

    def construct_argument_comment_block(self) -> str:
        """Construct block of #SBATCH comments for use in a sbatch run script."""
        return "\n".join((f"#SBATCH {arg}" for arg in self.args))


def tail(filename, n=10):
    "Return the last n lines of a file"
    # taken from https://docs.python.org/3/library/collections.html#deque-recipes
    with open(filename) as f:
        return deque(f, n)


def extract_job_id_from_sbatch_output(sbatch_output: str) -> ClusterJobId:
    """Extract the cluster job id from the stdout output of sbatch.

    Args:
        sbatch_output:  The complete stdout output of sbatch.

    Returns:
        The extracted job id.

    Raises:
        ValueError:  if job id can not be found in the output.
    """
    # Output of successful sbatch looks like this:
    # > Submitted batch job 4575177

    for line in sbatch_output.splitlines():
        if line.startswith("Submitted batch job "):
            return ClusterJobId(line[20:])

    raise ValueError(
        f"Could not find job id in output \n------\n{sbatch_output}\n------\n"
    )


def extract_job_status_from_sacct_output(
    sacct_output: str,
) -> dict[ClusterJobId, SlurmJobStatus]:
    """Extract status of jobs from given sacct output.

    This function expects that sacct was run with the following arguments:

        -X --parsable2 --format=JobID,NodeList,State,ExitCode --noheader
    """
    result: dict[ClusterJobId, SlurmJobStatus] = {}

    # Output looks like this: JobID|NodeList|State|ExitCode
    # For a successful job:
    #
    #    239026|galvani-cn001|COMPLETED|0:0
    #
    # For a job with errors:
    #
    #    264162|galvani-cn002|FAILED|1:0
    #
    # The ExitCode field has the format {exit_code}:{signal_that_killed_job_if_any}

    for line in sacct_output.splitlines():
        job_id, node_list, state, exit_code = line.split("|")

        # make sure there are no lines for intermediate steps (having job IDs like
        # `12345.batch`, `12345.0`, ...) in the given sacct output (this would be the
        # case when running sacct without `-X`).
        assert "." not in job_id, f"Unexpected line in sacct output: {line}"

        # extract actual exit code from the ExitCode field
        exit_code = exit_code.partition(":")[0]
        assert exit_code.isdigit()

        result[ClusterJobId(job_id)] = SlurmJobStatus(
            state=state,
            exit_code=int(exit_code),
            node_list=node_list,
        )

    return result


class SlurmClusterSubmission(ClusterSubmission):
    """Interface to submit jobs on a Slurm cluster."""

    #: Minimum duration between checks for failing jobs (to avoid polling the system too
    #: much)
    CHECK_FOR_FAILURES_INTERVAL_SEC = 60

    def __init__(
        self,
        requirements: dict[str, Any],
        paths: dict[str, str],
        remove_jobs_dir: bool = True,
    ):
        super().__init__(paths, remove_jobs_dir)

        self.requirements = SlurmJobRequirements.from_settings_dict(requirements)

        #: Time stamp of the last time checking for errors
        self._last_time_checking_for_failures = 0.0

    def _generate_run_script(self, job: Job):
        """Generate a sbatch run script for the given job and return the path to it.

        The path to the script is written to ``job.runs_script_path``.
        """
        logger = logging.getLogger("cluster_utils")

        runs_script_name = "job_{}_{}.sh".format(job.iteration, job.id)
        submission_dir = pathlib.Path(self.submission_dir)
        run_script_file_path = submission_dir / runs_script_name
        # need to prefix the actual job command with `srun` so that --signal works.
        cmd = job.generate_execution_cmd(self.paths, cmd_prefix="srun")

        stdout_file = run_script_file_path.with_suffix(".out")
        stderr_file = run_script_file_path.with_suffix(".err")

        args = SBatchArgumentBuilder()
        args.add("job-name", f"{job.opt_procedure_name}_{job.id}")
        args.add("output", stdout_file)
        args.add("error", stderr_file)
        args.add("partition", self.requirements.partition)
        args.add("cpus-per-task", self.requirements.cpus_per_task)
        args.add("gpus-per-task", self.requirements.gpus_per_task)
        args.add("mem", self.requirements.mem)
        args.add("time", self.requirements.time)
        args.add("nodes", self.requirements.nodes)
        args.add("ntasks", self.requirements.ntasks)

        if self.requirements.exclude:
            args.add("exclude", ",".join(self.requirements.exclude))

        if self.requirements.signal:
            args.add("signal", self.requirements.signal)

        args.extend_raw(self.requirements.extra_submission_options)

        template_vars = {
            "id": job.id,
            "cmd": cmd,
            "run_script_file_path": run_script_file_path,
            "sbatch_arg_lines": args.construct_argument_comment_block(),
        }

        logger.debug("Write run script to %s", run_script_file_path)
        run_script_file_path.write_text(
            _SLURM_RUN_SCRIPT_TEMPLATE.format(**template_vars)
        )
        run_script_file_path.chmod(0o755)  # Make executable

        job.run_script_path = str(run_script_file_path)

    def submit_fn(self, job: Job) -> ClusterJobId:
        logger = logging.getLogger("cluster_utils")

        # only generate run script for jobs that are submitted the first time
        if not job.waiting_for_resume:
            self._generate_run_script(job)

        assert job.run_script_path is not None

        # use open-mode=append so that output of jobs that are restarted (via
        # exit_for_resume) does not overwrite the output of previous runs
        sbatch_cmd = ["sbatch", "--open-mode=append", job.run_script_path]
        logger.debug("Execute command %s", sbatch_cmd)

        # TODO This timeout/retry-loop is copied from the Condor implementation.  Does
        # it also make sense for Slurm?
        for _ in range(10):
            try:
                result = run(
                    sbatch_cmd,
                    cwd=str(self.submission_dir),
                    stdout=PIPE,
                    timeout=15.0,
                    check=True,
                )
                sbatch_stdout = result.stdout.decode("utf-8")
                break
            except subprocess.TimeoutExpired:
                logger.warning("Job submission for id %d hangs. Retrying...", job.id)
            except subprocess.CalledProcessError as e:
                logger.warning(
                    "Job submission for id %d failed with exit code %d. Retrying...",
                    job.id,
                    e.returncode,
                )
        else:  # executed if loop finishes without break
            msg = (
                "Too many submission failures, cluster seems to be too unstable to"
                " submit jobs (see log for more information)"
            )
            logging.fatal(msg)
            logging.fatal("Command that failed: %s", sbatch_cmd)
            self.close()
            raise SubmissionError(msg)

        if not sbatch_stdout:
            msg = (
                f"[Job #{job.id}] sbatch returned without error but did not print a"
                " cluster job id."
            )
            logger.fatal(msg)
            self.close()
            raise SubmissionError(msg)

        try:
            cluster_job_id = extract_job_id_from_sbatch_output(sbatch_stdout)
        except ValueError as e:
            logger.fatal(e)
            self.close()
            raise SubmissionError(str(e)) from e

        if sbatch_stdout.count("\n") > 1:
            logger.warning(
                "sbatch produced more than one line of output which is unexpected."
                "  Please check the output for potential issues: \n------\n%s\n------",
                sbatch_stdout,
            )

        return cluster_job_id

    def stop_fn(self, cluster_id: ClusterJobId) -> None:
        logger = logging.getLogger("cluster_utils")
        logger.info("Cancel job with cluster id %s", cluster_id)

        cmd = ["scancel", cluster_id]
        run(cmd, stderr=PIPE, stdout=PIPE)

    def is_ready_to_check_for_failed_jobs(self) -> bool:
        time_since_last_check = time.time() - self._last_time_checking_for_failures
        return time_since_last_check >= self.CHECK_FOR_FAILURES_INTERVAL_SEC

    def mark_failed_jobs(self, jobs: Sequence[Job]) -> None:
        logger = logging.getLogger("cluster_utils")
        logger.debug("Check for failed jobs")

        assert all(job.cluster_id is not None for job in jobs)

        # construct lookup table to map cluster id to job
        job_map = {job.cluster_id: job for job in jobs if job.cluster_id}

        job_id_list = ",".join(job_map.keys())
        sacct_cmd = [
            "sacct",
            "--jobs",
            job_id_list,
            "-X",
            "--parsable2",  # fields are separated by `|`
            "--format=JobID,NodeList,State,ExitCode",
            "--noheader",
        ]

        logger.debug("Execute command %s", sacct_cmd)
        proc = run(sacct_cmd, check=True, stdout=PIPE)

        output = proc.stdout.decode()
        logger.debug("Output of sacct:\n%s", output)

        job_statuses = extract_job_status_from_sacct_output(output)

        for job_id, status in job_statuses.items():
            if job_id in job_map and not status.is_okay():
                job = job_map[ClusterJobId(job_id)]
                assert job.run_script_path is not None

                # write hostname to job (it is used in the error message)
                job.hostname = status.node_list

                # read error message from stderr output file (limit to last few lines)
                n_error_lines = 5
                stderr_file = pathlib.Path(job.run_script_path).with_suffix(".err")
                error_output = "".join(tail(stderr_file, n=n_error_lines))

                error_msg = (
                    "Job failed with state {} / exit code {}."
                    " Error output (last {} lines):\n{}"
                ).format(status.state, status.exit_code, n_error_lines, error_output)

                job.mark_failed(error_msg)

        self._last_time_checking_for_failures = time.time()
