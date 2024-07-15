"""ClusterSubmission implementation for running on the local machine."""

from __future__ import annotations

import concurrent.futures
import logging
import os
import random
from copy import copy
from multiprocessing import cpu_count
from subprocess import PIPE, run
from typing import Any, Sequence

from .cluster_system import ClusterJobId, ClusterSubmission
from .job import Job

LOCAL_RUN_SCRIPT = """#!/bin/bash
# %(id)d

error="%(run_script_file_path)s.err"
output="%(run_script_file_path)s.out"

# Close standard output and error file descriptors
exec 1<&-
exec 2<&-

# Redirect output and error streams to files from here on
exec 1>>"$output"
exec 2>>"$error"

%(cmd)s
rc=$?

if [[ $rc != 0 ]]; then
    echo "Failed with exit code $rc"
    # add an indicator file to more easily identify failed jobs
    echo "$rc" > "%(run_script_file_path)s.FAILED"
fi

exit $rc
"""


class DummyClusterSubmission(ClusterSubmission):
    def __init__(
        self,
        requirements: dict[str, Any],
        paths: dict[str, str],
        remove_jobs_dir: bool = True,
    ) -> None:
        super().__init__(paths, remove_jobs_dir)
        self._process_requirements(requirements)
        self.available_cpus = range(cpu_count())
        self.futures_tuple: list[tuple[ClusterJobId, concurrent.futures.Future]] = []
        self.executor = concurrent.futures.ProcessPoolExecutor(self.concurrent_jobs)
        self.next_cluster_id = 0

    def generate_cluster_id(self) -> ClusterJobId:
        cluster_id = ClusterJobId(f"local-{self.next_cluster_id}")
        self.next_cluster_id += 1
        return cluster_id

    def submit_fn(self, job: Job) -> ClusterJobId:
        # only generate run script for jobs that are submitted the first time
        if not job.waiting_for_resume:
            self.generate_job_spec_file(job)

        free_cpus = random.sample(self.available_cpus, self.cpus_per_job)
        free_cpus_str = ",".join(map(str, free_cpus))
        cmd = "taskset --cpu-list {} bash {}".format(free_cpus_str, job.run_script_path)
        cluster_id = self.generate_cluster_id()
        new_futures_tuple = (
            cluster_id,
            self.executor.submit(
                run,
                cmd,
                stdout=PIPE,
                stderr=PIPE,
                shell=True,  # type:ignore
            ),
        )
        job.futures_object = new_futures_tuple[1]
        self.futures_tuple.append(new_futures_tuple)

        return cluster_id

    def stop_fn(self, job_id: ClusterJobId) -> None:
        for cluster_id, future in self.futures_tuple:
            if cluster_id == job_id:
                future.cancel()
        concurrent.futures.wait(self.futures)

    def is_ready_to_check_for_failed_jobs(self) -> bool:
        # no need to throttle checks locally
        return True

    def mark_failed_jobs(self, jobs: Sequence[Job]) -> None:
        for job in jobs:
            assert job.futures_object is not None
            if (
                job.futures_object.done()
                and job.futures_object.result().returncode == 1
            ):
                msg = job.futures_object.result().stderr.decode()
                job.mark_failed(msg)

    def generate_job_spec_file(self, job: Job) -> None:
        logger = logging.getLogger("cluster_utils")
        logger.debug("Generate run script for job %d.", job.id)

        job_file_name = "{}_{}.sh".format(job.iteration, job.id)
        run_script_file_path = os.path.join(self.submission_dir, job_file_name)
        cmd = job.generate_execution_cmd(self.paths)
        # Prepare namespace for string formatting (class vars + locals)
        namespace = copy(vars(self))
        namespace.update(vars(job))
        namespace.update(locals())

        with open(run_script_file_path, "w") as script_file:
            script_file.write(LOCAL_RUN_SCRIPT % namespace)
        os.chmod(run_script_file_path, 0o755)  # Make executable

        job.run_script_path = run_script_file_path

    def status(self, job: Job) -> int:  # FIXME unused?
        futures = [
            future
            for cluster_id, future in self.futures_tuple
            if cluster_id == job.cluster_id
        ]
        if len(futures) == 0:
            return 0
        future = futures[0]
        if future.running():
            return 2
        else:
            if future.done():
                if future.result().__dict__["returncode"] == 1:
                    return 4
                return 3
            return 1

    @property
    def futures(self):
        return [future for _, future in self.futures_tuple]

    def _process_requirements(self, requirements: dict[str, Any]) -> None:
        logger = logging.getLogger("cluster_utils")
        self.cpus_per_job = requirements["request_cpus"]
        self.max_cpus = requirements.get("max_cpus", cpu_count())
        if self.max_cpus <= 0:
            raise ValueError(
                "CPU limit must be positive. Not {}.".format(self.max_cpus)
            )
        self.available_cpus = min(self.max_cpus, cpu_count())
        self.concurrent_jobs = self.available_cpus // self.cpus_per_job
        if self.concurrent_jobs == 0:
            logger.warning(
                "Total number of CPUs is smaller than requested CPUs per job. Resorting"
                " to 1 CPU per job"
            )
            self.concurrent_jobs = self.available_cpus
        assert self.concurrent_jobs > 0
