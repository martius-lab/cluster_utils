from __future__ import annotations

import logging
import shutil
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, NewType, Optional

from cluster.job import Job, JobStatus
from cluster.utils import rm_dir_full

if TYPE_CHECKING:
    from cluster.condor_cluster_system import CondorClusterSubmission
    from cluster.dummy_cluster_system import DummyClusterSubmission

# use a dedicated type for cluster job ids instead of 'str' (this makes function
# signatures easier to understand).  ClusterJobId will behave like a subclass of str.
ClusterJobId = NewType("ClusterJobId", str)


class ClusterSubmission(ABC):
    def __init__(self, paths: dict[str, str], remove_jobs_dir: bool = True) -> None:
        self.jobs: list[Job] = []
        self.remove_jobs_dir = remove_jobs_dir
        self.paths = paths
        self.submitted = False
        self.finished = False
        self.submission_hooks: dict[str, ClusterSubmissionHook] = dict()
        self._inc_job_id = -1
        self.error_msgs: set[str] = set()

    @property
    def current_jobs(self) -> list[Job]:
        return self.jobs

    @property
    def submission_dir(self) -> str:
        return self.paths["jobs_dir"]

    @property
    def inc_job_id(self) -> int:
        self._inc_job_id += 1
        return self._inc_job_id

    def register_submission_hook(self, hook: ClusterSubmissionHook) -> None:
        assert isinstance(hook, ClusterSubmissionHook)
        if hook.state > 0:
            return

        logger = logging.getLogger("cluster_utils")
        logger.info("Register submission hook {}".format(hook.identifier))
        self.submission_hooks[hook.identifier] = hook
        hook.manager = self

    def unregister_submission_hook(self, identifier: str) -> None:
        logger = logging.getLogger("cluster_utils")
        if identifier in self.submission_hooks:
            logger.info("Unregister submission hook {}".format(identifier))
            self.submission_hooks[identifier].manager = None
            self.submission_hooks.pop(identifier)
        else:
            raise HookNotFoundError("Hook not found. Can not unregister")

    def exec_pre_run_routines(self) -> None:
        for hook in self.submission_hooks.values():
            hook.pre_run_routine()

    def exec_post_run_routines(self) -> None:
        for hook in self.submission_hooks.values():
            hook.post_run_routine()

    def collect_stats_from_hooks(self):
        stats = {
            hook.identifier: hook.status for hook in self.submission_hooks.values()
        }
        return stats

    def save_job_info(self, result_dir: str) -> bool:
        return False

    def get_job(self, job_id):
        for job in self.jobs:
            if job.id == job_id:
                return job
        return None

    def add_jobs(self, jobs: Job | list[Job]):
        if not isinstance(jobs, list):
            jobs = [jobs]
        self.jobs = self.jobs + jobs

    @property
    def submitted_jobs(self) -> list[Job]:
        return [job for job in self.current_jobs if job.cluster_id is not None]

    @property
    def n_submitted_jobs(self) -> int:
        return len(self.submitted_jobs)

    @property
    def running_jobs(self) -> list[Job]:
        running_jobs = [
            job for job in self.current_jobs if job.status == JobStatus.RUNNING
        ]
        return running_jobs

    @property
    def n_running_jobs(self) -> int:
        return len(self.running_jobs)

    @property
    def completed_jobs(self) -> list[Job]:
        completed_jobs = [
            job
            for job in self.current_jobs
            if job.status == JobStatus.CONCLUDED or job.status == JobStatus.FAILED
        ]
        return completed_jobs

    @property
    def n_completed_jobs(self) -> int:
        return len(self.completed_jobs)

    @property
    def idle_jobs(self) -> list[Job]:
        idle_jobs = [
            job
            for job in self.current_jobs
            if job.status in [JobStatus.SUBMITTED, JobStatus.INITIAL_STATUS]
        ]
        return idle_jobs

    @property
    def n_idle_jobs(self) -> int:
        return len(self.idle_jobs)

    @property
    def successful_jobs(self) -> list[Job]:
        return [
            job
            for job in self.current_jobs
            if job.status == JobStatus.CONCLUDED and job.get_results() is not None
        ]

    @property
    def n_successful_jobs(self) -> int:
        return len(self.successful_jobs)

    @property
    def failed_jobs(self) -> list[Job]:
        return [
            job
            for job in self.completed_jobs
            if job.status == JobStatus.FAILED
            or (
                job.get_results() is None
                and job.status != JobStatus.CONCLUDED_WITHOUT_RESULTS
            )
        ]

    @property
    def n_failed_jobs(self) -> int:
        return len(self.failed_jobs)

    @property
    def n_total_jobs(self) -> int:
        return len(self.current_jobs)

    def submit_all(self) -> None:
        for job in self.current_jobs:
            if job.cluster_id is None:
                self.submit(job)

    def submit(self, job: Job) -> None:
        self._submit(job)
        # t = Thread(target=self._submit, args=(job,), daemon=True)
        # self.exec_pre_submission_routines()
        # t.start()

    def _submit(self, job: Job) -> None:
        logger = logging.getLogger("cluster_utils")
        if job.cluster_id is not None:
            raise RuntimeError("Can not run a job that already ran")
        if job not in self.jobs:
            logger.warning(
                "Submitting job that was not yet added to the cluster system interface,"
                " will add it now"
            )
            self.add_jobs(job)
        cluster_id = self.submit_fn(job)
        job.cluster_id = cluster_id
        job.status = JobStatus.SUBMITTED

    def stop(self, job: Job) -> None:
        if job.cluster_id is None:
            raise RuntimeError(
                "Can not close a job unless its cluster_id got specified"
            )
        self.stop_fn(job.cluster_id)

    def stop_all(self) -> None:
        print("Killing remaining jobs...")
        statuses_for_stopping = (
            JobStatus.SUBMITTED,
            JobStatus.RUNNING,
            JobStatus.SENT_RESULTS,
        )
        for job in self.jobs:
            if job.cluster_id is not None and job.status in statuses_for_stopping:
                self.stop(job)
                # TODO: Add check all are gone

    @property
    def median_time_left(self) -> str:
        times_left = [job.time_left for job in self.running_jobs]
        times_left_known = [x for x in times_left if x is not None]
        if not times_left_known:
            return ""

        median = sorted(times_left_known)[len(times_left_known) // 2]
        return Job.time_left_to_str(median)

    def get_best_seen_value_of_main_metric(self, minimize: bool) -> Optional[float]:
        jobs_with_results = [
            job.reported_metric_values
            for job in self.running_jobs
            if job.reported_metric_values
        ]
        latest = [item[-1] for item in jobs_with_results]
        if not latest:
            return None
        if minimize:
            return min(latest)
        else:
            return max(latest)

    @abstractmethod
    def submit_fn(self, job: Job) -> ClusterJobId:
        raise NotImplementedError

    @abstractmethod
    def stop_fn(self, cluster_id: ClusterJobId) -> None:
        raise NotImplementedError

    def close(self) -> None:
        logger = logging.getLogger("cluster_utils")
        self.stop_all()
        if self.remove_jobs_dir:
            logger.info("Removing jobs dir {}".format(self.submission_dir))
            rm_dir_full(self.submission_dir)

    def check_error_msgs(self) -> None:
        logger = logging.getLogger("cluster_utils")
        for job in self.failed_jobs:
            if job.error_info not in self.error_msgs:
                warn_string = (
                    f"\x1b[1;31m Job {job.id} on hostname {job.hostname} failed with"
                    " error:\x1b[0m\n"
                )
                full_warning = f"{warn_string}{''.join(job.error_info or '')}"
                logger.warning(full_warning)
                print(full_warning)
                self.error_msgs.add(job.error_info)

    def __repr__(self) -> str:
        return (
            "Total: {.n_total_jobs}, Submitted: {.n_submitted_jobs}, Completed with"
            " output: {.n_successful_jobs}, Failed: {.n_failed_jobs}, Running:"
            " {.n_running_jobs}, Idle: {.n_idle_jobs}"
        ).format(*(6 * [self]))


def get_cluster_type(
    requirements, run_local=None
) -> type[CondorClusterSubmission] | type[DummyClusterSubmission]:
    from cluster.condor_cluster_system import CondorClusterSubmission
    from cluster.dummy_cluster_system import DummyClusterSubmission

    logger = logging.getLogger("cluster_utils")

    if is_command_available("condor_q"):
        logger.info("CONDOR detected, running CONDOR job submission")
        return CondorClusterSubmission
    else:
        if run_local is None:
            answer = input("No cluster detected. Do you want to run locally? [Y/n]: ")
            if answer.lower() == "n":
                run_local = False
            else:
                run_local = True

        if run_local:
            return DummyClusterSubmission
        else:
            raise OSError("Neither CONDOR nor SLURM was found. Not running locally")


def is_command_available(cmd: str) -> bool:
    """Check if the command 'cmd' is available."""
    return shutil.which(cmd) is not None


class ClusterSubmissionHook(ABC):
    def __init__(self, identifier: str):
        self.identifier = identifier
        # TODO use a bool or enum for this?
        self.state: int = 1  # 0: everything is fine
        # 1: errors encountered
        self.status: Optional[str] = None
        self.manager: Optional[ClusterSubmission] = None

        self.determine_state()

    @abstractmethod
    def determine_state(self) -> None:
        """Check the state and write it to :attr:`state`."""
        pass

    @abstractmethod
    def pre_run_routine(self) -> None:
        pass

    def post_run_routine(self) -> None:
        self.update_status()

    @abstractmethod
    def update_status(self) -> None:
        """Update the status stored in :attr:`status`."""
        pass


class HookNotFoundError(Exception):
    pass
