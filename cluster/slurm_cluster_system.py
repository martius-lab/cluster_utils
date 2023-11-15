"""ClusterSubmission implementation for Slurm."""
from __future__ import annotations

import logging
import pathlib
import subprocess
from subprocess import PIPE, run
from typing import Any, NamedTuple

from cluster import settings
from cluster.cluster_system import ClusterJobId, ClusterSubmission, SubmissionError
from cluster.job import Job

# TODO: handle return codes != 0,1,3 ?
# TODO: exit for resume probably needs different handling here
_SLURM_RUN_SCRIPT_TEMPLATE = """#!/bin/bash
#SBATCH --job-name={job_name}_{id}
#SBATCH --output={output_file}
#SBATCH --error={error_file}

#SBATCH --partition={partition}
#SBATCH --cpus-per-task={cpus_per_task:d}
#SBATCH --gpus-per-task={gpus_per_task:d}
#SBATCH --mem={mem}
#SBATCH --time={time}
#SBATCH --nodes={nodes}
#SBATCH --ntasks={ntasks}


# Submission ID {id}

{cmd}
rc=$?
if [[ $rc == 3 ]]; then
    echo "exit with code 3 for resume"
    exit 3
elif [[ $rc == 1 ]]; then
    # add an indicator file to more easily identify failed jobs
    touch "{run_script_file_path}.FAILED"
    exit 1
fi
"""


class SlurmJobRequirements(NamedTuple):
    # names here correspond to options of sbatch

    partition: str
    cpus_per_task: int
    gpus_per_task: int
    mem: str
    time: str

    # keep nodes and ntasks at 1 (use a separate job for each task
    nodes: int = 1
    ntasks: int = 1

    @classmethod
    def from_settings_dict(cls, requirements: dict[str, Any]) -> SlurmJobRequirements:
        logger = logging.getLogger("cluster_utils")

        # create copy so we can pop processed items
        req = dict(requirements)

        try:
            obj = cls(
                partition=req.pop("partition"),
                cpus_per_task=req.pop("request_cpus"),
                gpus_per_task=req.pop("request_gpus", 0),
                mem="{}M".format(req.pop("memory_in_mb")),
                time=req.pop("request_time"),
            )
        except KeyError as e:
            raise settings.SettingsError(
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


class SlurmClusterSubmission(ClusterSubmission):
    def __init__(
        self,
        requirements: dict[str, Any],
        paths: dict[str, str],
        remove_jobs_dir: bool = True,
    ):
        super().__init__(paths, remove_jobs_dir)

        self.requirements = SlurmJobRequirements.from_settings_dict(requirements)

    def submit_fn(self, job: Job) -> ClusterJobId:
        logger = logging.getLogger("cluster_utils")

        runs_script_name = "job_{}_{}.sh".format(job.iteration, job.id)
        submission_dir = pathlib.Path(self.submission_dir)
        run_script_file_path = submission_dir / runs_script_name
        cmd = job.generate_execution_cmd(self.paths)

        stdout_file = run_script_file_path.with_suffix(".out")
        stderr_file = run_script_file_path.with_suffix(".err")
        template_vars = {
            "job_name": job.opt_procedure_name,
            "output_file": stdout_file,
            "error_file": stderr_file,
            "id": job.id,
            "cmd": cmd,
            "run_script_file_path": run_script_file_path,
            **self.requirements._asdict(),
        }

        run_script_file_path.write_text(
            _SLURM_RUN_SCRIPT_TEMPLATE.format(**template_vars)
        )
        run_script_file_path.chmod(0o755)  # Make executable

        job.run_script_path = str(run_script_file_path)

        sbatch_cmd = [
            "sbatch",
            str(run_script_file_path),
        ]
        # TODO: in condor, there are additional `requirement_lines` (see template).
        # What are they used for?  Can (at least some of) its functionality be
        # implemented here as well?

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

        logger.info(
            "Job with id %d submitted to Slurm cluster with cluster id %s.",
            job.id,
            cluster_job_id,
        )

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
