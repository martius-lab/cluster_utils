"""ClusterSubmission implementation for running on the local machine."""
from __future__ import annotations

import concurrent.futures
import logging
import os
import random
from copy import copy
from multiprocessing import cpu_count
from subprocess import PIPE, run
from typing import Any

import numpy as np

from cluster import constants
from cluster.cluster_system import ClusterJobId, ClusterSubmission
from cluster.job import Job


class DummyClusterSubmission(ClusterSubmission):
    def __init__(
        self,
        requirements: dict[str, Any],
        paths: dict[str, str],
        remove_jobs_dir: bool = True,
    ) -> None:
        super().__init__(paths, remove_jobs_dir)
        self._process_requirements(requirements)
        self.exceptions_seen = set({})  # FIXME unused?
        self.available_cpus = range(cpu_count())
        self.futures_tuple: list[tuple[ClusterJobId, concurrent.futures.Future]] = []
        self.executor = concurrent.futures.ProcessPoolExecutor(self.concurrent_jobs)

    def generate_cluster_id(self) -> ClusterJobId:
        cluster_id = np.random.randint(1e10)
        while cluster_id in [c_id for c_id, future in self.futures_tuple]:
            cluster_id = np.random.randint(1e10)
        return ClusterJobId(cluster_id)

    def submit_fn(self, job: Job) -> ClusterJobId:
        logger = logging.getLogger("cluster_utils")
        self.generate_job_spec_file(job)
        free_cpus = random.sample(self.available_cpus, self.cpus_per_job)
        free_cpus_str = ",".join(map(str, free_cpus))
        cmd = "taskset --cpu-list {} bash {}".format(free_cpus_str, job.run_script_path)
        cluster_id = self.generate_cluster_id()
        new_futures_tuple = (
            cluster_id,
            self.executor.submit(run, cmd, stdout=PIPE, stderr=PIPE, shell=True),
        )
        logger.info(f"Job with id {job.id} submitted locally.")
        job.futures_object = new_futures_tuple[1]
        self.futures_tuple.append(new_futures_tuple)
        return cluster_id

    def stop_fn(self, job_id: ClusterJobId) -> None:
        for cluster_id, future in self.futures_tuple:
            if cluster_id == job_id:
                future.cancel()
        concurrent.futures.wait(self.futures)

    def generate_job_spec_file(self, job: Job) -> None:
        job_file_name = "{}_{}.sh".format(job.iteration, job.id)
        run_script_file_path = os.path.join(self.submission_dir, job_file_name)
        cmd = job.generate_execution_cmd(self.paths)
        # Prepare namespace for string formatting (class vars + locals)
        namespace = copy(vars(self))
        namespace.update(vars(job))
        namespace.update(locals())

        with open(run_script_file_path, "w") as script_file:
            script_file.write(constants.LOCAL_RUN_SCRIPT % namespace)
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

    def is_blocked(self) -> bool:
        return True

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
