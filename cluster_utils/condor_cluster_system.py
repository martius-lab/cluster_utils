"""ClusterSubmission implementation for HTCondor."""

from __future__ import annotations

import logging
import os
import subprocess
from collections import namedtuple
from contextlib import suppress
from copy import copy
from subprocess import PIPE, run
from typing import Any, Sequence

from cluster_utils.base.constants import RETURN_CODE_FOR_RESUME

from .cluster_system import ClusterJobId, ClusterSubmission
from .job import Job

MPI_CLUSTER_MAX_NUM_TOKENS = 10000

MPI_CLUSTER_RUN_SCRIPT = f"""#!/bin/bash
# Submission ID %(id)d

%(cmd)s
rc=$?
if [[ $rc == 0 ]]; then
    rm -f %(run_script_file_path)s
    rm -f %(job_spec_file_path)s
elif [[ $rc == {RETURN_CODE_FOR_RESUME} ]]; then
    echo "exit with code {RETURN_CODE_FOR_RESUME} for resume"
    exit {RETURN_CODE_FOR_RESUME}
elif [[ $rc != 0 ]]; then
    echo "Failed with exit code $rc"
    # add an indicator file to more easily identify failed jobs
    echo "$rc" > "%(run_script_file_path)s.FAILED"
    exit $rc
fi
"""
# TODO: the MPI_CLUSTER_RUN_SCRIPT above does not forward errorcodes other than 1 and 3.
# Could this be a problem?

MPI_CLUSTER_JOB_SPEC_FILE = f"""# Submission ID %(id)d
JobBatchName=%(opt_procedure_name)s
executable = %(run_script_file_path)s

error = %(run_script_file_path)s.err
output = %(run_script_file_path)s.out
log = %(run_script_file_path)s.log

request_cpus=%(cpus)s
request_gpus=%(gpus)s
request_memory=%(mem)s

%(requirements_line)s

on_exit_hold = (ExitCode =?= {RETURN_CODE_FOR_RESUME})
on_exit_hold_reason = "Checkpointed, will resume"
on_exit_hold_subcode = 2
periodic_release = ( (JobStatus =?= 5) && (HoldReasonCode =?= {RETURN_CODE_FOR_RESUME}) && (HoldReasonSubCode =?= 2) )

# Inherit environment variables at submission time in job script
getenv=True

%(concurrent_line)s

%(extra_submission_lines)s

queue
"""


CondorRecord = namedtuple(
    "CondorRecord",
    [
        "ID",
        "owner",
        "sub_date",
        "sub_time",
        "run_time",
        "status",
        "priority",
        "size",
        "cmd",
    ],
)


class CondorClusterSubmission(ClusterSubmission):
    def __init__(
        self,
        requirements: dict[str, Any],  # TODO can this be more specific than Any?
        paths: dict[str, str],
        remove_jobs_dir: bool = True,
    ) -> None:
        super().__init__(paths, remove_jobs_dir)

        os.environ["MPLBACKEND"] = "agg"
        self._process_requirements(requirements)

    def submit_fn(self, job: Job) -> ClusterJobId:
        logger = logging.getLogger("cluster_utils")
        self.generate_job_spec_file(job)
        submit_cmd = "condor_submit_bid {} {}\n".format(
            self.bid, job.job_spec_file_path
        )
        for try_number in range(10):
            if try_number == 9:
                logging.exception("Job aborted, cluster unstable.")
                raise Exception(
                    "Too many submission timeouts, cluster seems to be too unstable to"
                    " submit jobs"
                )
            try:
                result = run(
                    [submit_cmd],
                    cwd=str(self.submission_dir),
                    shell=True,
                    stdout=PIPE,
                    timeout=15.0,
                )
                submit_output = result.stdout.decode("utf-8")
                break
            except subprocess.TimeoutExpired:
                logger.warning(f"Job submission for id {job.id} hangs. Retrying...")

        good_lines = [line for line in submit_output.split("\n") if "submitted" in line]
        bad_lines = [
            line
            for line in submit_output.split("\n")
            if "WARNING" in line or "ERROR" in line
        ]
        if not good_lines or bad_lines:
            logger.error(
                f"Job with id {job.id} submitted to condor cluster, but job submission"
                f" failed. Submission output:\n{submit_output}"
            )
            print(bad_lines)
            self.close()
            raise RuntimeError("Cluster submission failed")

        assert len(good_lines) == 1
        new_cluster_id = good_lines[0].split(" ")[-1][:-1]

        return ClusterJobId(new_cluster_id)

    def stop_fn(self, cluster_id: ClusterJobId) -> None:
        cmd = "condor_rm {}".format(cluster_id)
        run([cmd], shell=True, stderr=PIPE, stdout=PIPE)

    def resume_fn(self, job: Job) -> None:
        # On HTCondor the restarting is handled by the scheduler itself (due to
        # special handling of return code RETURN_CODE_FOR_RESUME in the submission
        # file), so nothing to do here.
        pass

    def is_ready_to_check_for_failed_jobs(self) -> bool:
        # TODO: should we throttle this a bit?  Probably doesn't need to be checked
        # multiple times per second
        return True

    def mark_failed_jobs(self, jobs: Sequence[Job]) -> None:
        for job in jobs:
            assert job.run_script_path is not None

            # read condor log file to check the return code
            log_file = f"{job.run_script_path}.log"
            with suppress(FileNotFoundError):
                with open(log_file) as f:
                    content = f.read()
                _, __, after = content.rpartition("return value ")

                if after and after[0] == "1":
                    _, __, hostname = content.rpartition(
                        "Job executing on host: <172.22."
                    )
                    hostname = f"?0{hostname[2:].split(':')[0]}"
                    job.hostname = hostname

                    # read error message from the stderr output file
                    err_file = f"{job.run_script_path}.err"
                    with open(err_file) as f_err:
                        error_output = f_err.read()

                    job.mark_failed(error_output)

    def generate_job_spec_file(self, job: Job) -> None:
        job_file_name = "job_{}_{}.sh".format(job.iteration, job.id)
        run_script_file_path = os.path.join(self.submission_dir, job_file_name)
        job_spec_file_path = os.path.join(self.submission_dir, job_file_name + ".sub")
        cmd = job.generate_execution_cmd(self.paths)
        # Prepare namespace for string formatting (class vars + locals)
        namespace = copy(vars(self))
        namespace.update(vars(job))
        namespace.update(locals())

        with open(run_script_file_path, "w") as script_file:
            script_file.write(MPI_CLUSTER_RUN_SCRIPT % namespace)
        os.chmod(run_script_file_path, 0o755)  # Make executable

        with open(job_spec_file_path, "w") as spec_file:
            spec_file.write(MPI_CLUSTER_JOB_SPEC_FILE % namespace)

        job.job_spec_file_path = job_spec_file_path
        job.run_script_path = run_script_file_path

    # TODO: Check that two simultaneous HPOs dont collide

    def _process_requirements(self, requirements: dict[str, Any]) -> None:
        # Job requirements
        self.mem = requirements["memory_in_mb"]
        self.cpus = requirements["request_cpus"]
        self.gpus = requirements["request_gpus"]
        self.bid = requirements["bid"]

        condor_requirements = []
        if self.gpus > 0:
            self.partition = "gpu"
            self.constraint = "gpu"

            if requirements["cuda_requirement"] is not None:
                cuda_req = requirements["cuda_requirement"]
                try:
                    float(cuda_req)
                    requirement_is_float = True
                except ValueError:
                    requirement_is_float = False

                if cuda_req.startswith("<") or cuda_req.startswith(">"):
                    cuda_line = "TARGET.CUDACapability{}".format(cuda_req)
                elif requirement_is_float:
                    cuda_line = "TARGET.CUDACapability>={}".format(cuda_req)
                else:
                    cuda_line = "{}".format(cuda_req)

                condor_requirements.append(cuda_line)
        else:
            self.partition = "general"
            self.constraint = ""

        if self.gpus > 0 and "gpu_memory_mb" in requirements:
            condor_requirements.append(
                "TARGET.CUDAGlobalMemoryMb>={}".format(requirements["gpu_memory_mb"])
            )

        def hostnames_to_requirement(hostnames):
            single_reqs = [
                f'UtsnameNodename =?= "{hostname}"' for hostname in hostnames
            ]
            return "(" + " || ".join(single_reqs) + ")"

        hostname_list = requirements.get("hostname_list", [])
        if hostname_list:
            condor_requirements.append(hostnames_to_requirement(hostname_list))

        forbidden_hostnames = requirements.get("forbidden_hostnames", [])
        if forbidden_hostnames:
            single_reqs = [
                f'UtsnameNodename =!= "{hostname}"' for hostname in forbidden_hostnames
            ]
            condor_requirements.extend(single_reqs)

        if len(condor_requirements) > 0:
            concat_requirements = " && ".join(condor_requirements)
            self.requirements_line = f"requirements={concat_requirements}"
        else:
            self.requirements_line = ""

        concurrency_limit_tag = requirements.get("concurrency_limit_tag", None)
        concurrency_limit = requirements.get("concurrency_limit", None)

        self.concurrent_line = ""
        if concurrency_limit_tag is not None and concurrency_limit is not None:
            concurrency_limit = MPI_CLUSTER_MAX_NUM_TOKENS // concurrency_limit
            self.concurrent_line = (
                f"concurrency_limits=user.{concurrency_limit_tag}:{concurrency_limit}"
            )

        if "extra_submission_options" in requirements:
            extra_options = requirements["extra_submission_options"]
            if isinstance(extra_options, dict):
                extra_options = [
                    f"{key}={value}" for key, value in extra_options.items()
                ]
            if isinstance(extra_options, list):
                extra_options = "\n".join(extra_options)
            self.extra_submission_lines = f"# Extra options\n{extra_options}"
        else:
            self.extra_submission_lines = ""
