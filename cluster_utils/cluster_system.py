from __future__ import annotations

import logging
import shutil
from abc import ABC, abstractmethod
from collections import deque
from typing import TYPE_CHECKING, NewType, Optional, Sequence

import colorama

from .job import Job, JobStatus
from .utils import rm_dir_full, styled

if TYPE_CHECKING:
    from .condor_cluster_system import CondorClusterSubmission
    from .dummy_cluster_system import DummyClusterSubmission
    from .slurm_cluster_system import SlurmClusterSubmission

# use a dedicated type for cluster job ids instead of 'str' (this makes function
# signatures easier to understand).  ClusterJobId will behave like a subclass of str.
ClusterJobId = NewType("ClusterJobId", str)


class ClusterSubmission(ABC):
    """Base class for cluster system interfaces.

    Provides the logic for submitting jobs to the cluster system and tracking their
    status.  Cluster system specific classes should be derived from this base class,
    implementing the abstract methods.

    How to submit a job
    -------------------

    First, a new job needs to be registered with :meth:`add_jobs`.  By default (with
    `enqueue=True`), this automatically adds the job to the *submission queue*, a queue
    which contains the jobs that are about to be submitted to the cluster.
    Alternatively, `enqueue` can be set to False in which case in which case the job has
    to be explicitly enqueued by calling :meth:`enqueue_job_for_submission`.

    By calling :meth:`submit_next` you can then submit jobs from the queue one by one in
    FIFO order.
    """

    def __init__(self, paths: dict[str, str], remove_jobs_dir: bool = True) -> None:
        #: List of all jobs that have been registered via :meth:`add_jobs`.
        self.jobs: list[Job] = []
        #: Queue of jobs that are waiting to be submitted.
        self.submission_queue: deque[Job] = deque()
        self.remove_jobs_dir = remove_jobs_dir
        self.paths = paths
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

    def add_jobs(self, jobs: Job | list[Job], enqueue: bool = True) -> None:
        """Register a new job.

        Args:
            jobs: Either a single Job instance or a list of jobs.
            enqueue: If true, the added job is automatically appended to the submission
                queue.
        """
        if not isinstance(jobs, list):
            jobs = [jobs]
        self.jobs = self.jobs + jobs

        if enqueue:
            self.submission_queue.extend(jobs)

    def enqueue_job_for_submission(self, job: Job) -> None:
        """Add job to the submission queue."""
        self.submission_queue.append(job)

    def has_unsubmitted_jobs(self) -> bool:
        """Check if there are jobs in the submission queue, waiting to be submitted."""
        return bool(self.submission_queue)

    def submit_next(self) -> None:
        """Submit the next job from the submission queue.

        Raises:
            IndexError: if the submission queue is empty.  See also
                :meth:`has_unsubmitted_jobs`.
        """
        logger = logging.getLogger("cluster_utils")
        logger.debug("Submit next job from queue.")
        try:
            job = self.submission_queue.popleft()
        except IndexError as e:
            # provide more understandable error message
            raise IndexError("No job to submit, queue is empty.") from e

        self._submit(job)

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
                self._submit(job)

    def _submit(self, job: Job) -> None:
        logger = logging.getLogger("cluster_utils")
        if job.cluster_id is not None and not job.waiting_for_resume:
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

        if job.waiting_for_resume:
            logger.info(
                "Job with id %d re-submitted with cluster id %s", job.id, job.cluster_id
            )
        else:
            logger.info(
                "Job with id %d submitted with cluster id %s", job.id, job.cluster_id
            )

    def resume(self, job: Job) -> None:
        """Resume a job that was terminated with :func:`~cluster_utils.exit_for_resume`."""
        job.waiting_for_resume = True
        self.resume_fn(job)

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

    def resume_fn(self, job: Job) -> None:
        # Default behaviour is to simply re-enqueue it.  Overwrite this method for
        # cluster systems where resuming should be handled differently.
        self.enqueue_job_for_submission(job)

    @abstractmethod
    def submit_fn(self, job: Job) -> ClusterJobId:
        raise NotImplementedError

    @abstractmethod
    def stop_fn(self, cluster_id: ClusterJobId) -> None:
        raise NotImplementedError

    @abstractmethod
    def is_ready_to_check_for_failed_jobs(self) -> bool:
        """Return if it's okay to call :meth:`check_for_failed_jobs`.

        Can be used to reduce the amount of polling on systems where this is a concern,
        e.g. by only returning True if the last check was more than a minute ago.
        """
        raise NotImplementedError

    @abstractmethod
    def mark_failed_jobs(self, jobs: Sequence[Job]) -> None:
        """Check if the given jobs failed on the cluster.

        Implementations of this method shall check all given jobs and call
        :meth:`Job.mark_failed` for jobs that failed.
        """
        raise NotImplementedError

    def close(self) -> None:
        logger = logging.getLogger("cluster_utils")
        self.stop_all()

        if self.remove_jobs_dir:
            logger.info("Removing jobs directory %s", self.submission_dir)
            rm_dir_full(self.submission_dir)
        else:
            # repeat the path to the jobs directory at the end, so it is easier to find
            print(
                "Output/logs of individual jobs are kept in %s"
                % styled(self.submission_dir, colorama.Fore.BLUE)
            )

        print(
            "Results are stored in %s"
            % styled(self.paths["result_dir"], colorama.Fore.BLUE)
        )

    def check_for_failed_jobs(self) -> None:
        """Check if the cluster system reported failing jobs.

        The status of failed jobs will be changed to JobStatus.FAILED and the reported
        error message will be stored in job.error_info.
        """
        jobs = [
            job
            for job in self.submitted_jobs
            if job.status == JobStatus.SUBMITTED or job.waiting_for_resume
        ]
        if jobs:
            self.mark_failed_jobs(jobs)

            # potentially print error messages
            self._check_error_msgs()

    def _check_error_msgs(self) -> None:
        logger = logging.getLogger("cluster_utils")
        for job in self.failed_jobs:
            assert job.error_info is not None, "Failed job has no error_info."
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
) -> (
    type[CondorClusterSubmission]
    | type[SlurmClusterSubmission]
    | type[DummyClusterSubmission]
):
    from .condor_cluster_system import CondorClusterSubmission
    from .dummy_cluster_system import DummyClusterSubmission
    from .slurm_cluster_system import SlurmClusterSubmission

    logger = logging.getLogger("cluster_utils")

    if is_command_available("condor_q"):
        logger.info("CONDOR detected, running CONDOR job submission")
        return CondorClusterSubmission
    elif is_command_available("sbatch"):
        logger.info("Slurm detected, running Slurm job submission")
        return SlurmClusterSubmission
    else:
        if run_local is None:
            answer = input("No cluster detected. Do you want to run locally? [Y/n]: ")
            if answer.lower() == "n":
                run_local = False
            else:
                run_local = True

        if run_local:
            logger.info("No cluster detected, running locally")
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


class SubmissionError(Exception):
    """Indicates an error during job submission."""

    pass
