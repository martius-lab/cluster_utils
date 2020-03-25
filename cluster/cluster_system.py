import logging

from .condor_cluster_system import Condor_ClusterSubmission
from .dummy_cluster_system import Dummy_ClusterSubmission
import os
from .utils import rm_dir_full
from abc import ABC, abstractmethod
from warnings import warn
from subprocess import run, DEVNULL
from .job import JobStatus, Job

logger = logging.getLogger('cluster_utils')

class ClusterSubmission(ABC):
    def __init__(self, paths, remove_jobs_dir=True, iteration_mode=True):
        self.jobs = []
        self.remove_jobs_dir = remove_jobs_dir
        self.paths = paths
        self.submitted = False
        self.finished = False
        self.submission_hooks = dict()
        self._inc_job_id = -1
        self.iteration_mode = iteration_mode
        self.error_msgs = set()

    @property
    def current_jobs(self):
        if not self.iteration_mode:
            return self.jobs
        if len(self.jobs) == 0:
            return []
        max_it = max([job.iteration for job in self.jobs])
        return [job for job in self.jobs if job.iteration == max_it]

    @property
    def submission_dir(self):
        return self.paths['jobs_dir']

    @property
    def inc_job_id(self):
        self._inc_job_id += 1
        return self._inc_job_id

    def register_submission_hook(self, hook):
        assert isinstance(hook, ClusterSubmissionHook)
        if hook.state > 0:
            return

        logger.info('Register submission hook {}'.format(hook.identifier))
        self.submission_hooks[hook.identifier] = hook
        hook.manager = self

    def unregister_submission_hook(self, identifier):
        if identifier in self.submission_hooks:
            logger.info('Unregister submission hook {}'.format(identifier))
            self.submission_hooks.manager = None
            self.submission_hooks.pop(identifier)
        else:
            raise HookNotFoundException('Hook not found. Can not unregister')

    def exec_pre_run_routines(self):
        for hook in self.submission_hooks.values():
            hook.pre_run_routine()

    def exec_post_run_routines(self):
        for hook in self.submission_hooks.values():
            hook.post_run_routine()

    def collect_stats_from_hooks(self):
        stats = {hook.identifier: hook.status for hook in self.submission_hooks.values()}
        return stats

    def save_job_info(self, result_dir):
        return False

    def get_job(self, id):
        for job in self.jobs:
            if job.id == id:
                return job
        return None

    def add_jobs(self, jobs):
        if not isinstance(jobs, list):
            jobs = [jobs]
        self.jobs = self.jobs + jobs

    @property
    def submitted_jobs(self):
        return [job for job in self.current_jobs if not job.cluster_id is None]

    @property
    def n_submitted_jobs(self):
        return len(self.submitted_jobs)

    @property
    def running_jobs(self):
        running_jobs = [job for job in self.current_jobs if job.status == JobStatus.RUNNING]
        return running_jobs

    @property
    def n_running_jobs(self):
        return len(self.running_jobs)

    @property
    def completed_jobs(self):
        completed_jobs = [job for job in self.current_jobs if
                          job.status == JobStatus.CONCLUDED or job.status == JobStatus.FAILED]
        return completed_jobs

    @property
    def n_completed_jobs(self):
        return len(self.completed_jobs)

    @property
    def idle_jobs(self):
        idle_jobs = [job for job in self.current_jobs if job.status in [JobStatus.SUBMITTED, JobStatus.INITIAL_STATUS]]
        return idle_jobs

    @property
    def n_idle_jobs(self):
        return len(self.idle_jobs)

    @property
    def successful_jobs(self):
        return [job for job in self.current_jobs if job.status == JobStatus.CONCLUDED and not job.get_results() is None]

    @property
    def n_successful_jobs(self):
        return len(self.successful_jobs)

    @property
    def failed_jobs(self):
        return [job for job in self.completed_jobs if job.status == JobStatus.FAILED or job.get_results() is None]

    @property
    def n_failed_jobs(self):
        return len(self.failed_jobs)

    @property
    def n_total_jobs(self):
        return len(self.current_jobs)

    def submit_all(self):
        for job in self.current_jobs:
            if job.cluster_id is None:
                self.submit(job)

    def submit(self, job):
        self._submit(job)
        # t = Thread(target=self._submit, args=(job,), daemon=True)
        # self.exec_pre_submission_routines()
        # t.start()

    def _submit(self, job):
        if not job.cluster_id is None:
            raise RuntimeError('Can not run a job that already ran')
        if not job in self.jobs:
            warn('Submitting job that was not yet added to the cluster system interface, will add it now')
            self.add_jobs(job)
        cluster_id = self.submit_fn(job)
        job.cluster_id = cluster_id
        job.status = JobStatus.SUBMITTED

    def stop(self, job):
        if job.cluster_id is None:
            raise RuntimeError('Can not close a job unless its cluster_id got specified')
        self.stop_fn(job.cluster_id)

    def stop_all(self):
        print('Killing remaining jobs...')
        for job in self.jobs:
            if job.cluster_id is not None and job.status in [JobStatus.SUBMITTED, JobStatus.RUNNING, JobStatus.SENT_RESULTS]:
                self.stop(job)
                # TODO: Add check all are gone

    @property
    def median_time_left(self):
        times_left = [job.time_left for job in self.running_jobs]
        times_left_known = [x for x in times_left if x is not None]
        if not times_left_known:
            return ""

        median = sorted(times_left_known)[len(times_left_known) // 2]
        return Job.time_left_to_str(median)

    def get_best_seen_value_of_main_metric(self, minimize):
        jobs_with_results = [job.reported_metric_values for job in self.running_jobs if job.reported_metric_values]
        latest = [item[-1] for item in jobs_with_results]
        if not latest:
            return None
        if minimize:
            return min(latest)
        else:
            return max(latest)

    '''
  @abstractmethod
  def status(self, job):
    # 0: not submitted (could also mean its done)
    # 1: submitted
    # 2: running
    raise NotImplementedError
  '''

    @abstractmethod
    def submit_fn(self, job_spec_file_path):
        raise NotImplementedError

    @abstractmethod
    def stop_fn(self, cluster_id):
        raise NotImplementedError

    @abstractmethod
    def generate_job_spec_file(self, job):
        raise NotImplementedError

    @abstractmethod
    def is_blocked(self):
        raise NotImplementedError

    def __enter__(self):
        # TODO: take emergency cleanup to new implementation
        try:
            self.exec_pre_submission_routines()
            self.submit()
        except:
            self.close()
            logger.warning('Job killed in emergency mode! Check condor_q!')
            raise

    def close(self):
        self.stop_all()
        if self.remove_jobs_dir:
            logger.info('Removing jobs dir {}'.format(self.submission_dir))
            rm_dir_full(self.submission_dir)


    def check_error_msgs(self):
        for job in self.failed_jobs:
            if job.error_info not in self.error_msgs:
                warn_string = f'\x1b[1;31m Job: {job.id} on hostname {job.hostname} failed with error:\x1b[0m\n'
                warn(f"{warn_string}{''.join(job.error_info or '')}")
                self.error_msgs.add(job.error_info)

    def __repr__(self):
        return ('Total: {.n_total_jobs}, Submitted: {.n_submitted_jobs}, Completed with output: {.n_successful_jobs}, '
                'Failed: {.n_failed_jobs}, Running: {.n_running_jobs}, Idle: {.n_idle_jobs}').format(*(6 * [self]))


def get_cluster_type(requirements, run_local=None):
    if is_command_available('condor_q'):
        logger.info('CONDOR detected, running CONDOR job submission')
        return Condor_ClusterSubmission
    else:
        if run_local is None:
            answer = input('No cluster detected. Do you want to run locally? [Y/n]: ')
            if answer.lower() == 'n':
                run_local = False
            else:
                run_local = True

        if run_local:
            return Dummy_ClusterSubmission
        else:
            raise OSError('Neither CONDOR nor SLURM was found. Not running locally')


def is_command_available(cmd):
    try:
        run(cmd, stderr=DEVNULL, stdout=DEVNULL)
    except OSError as e:
        if e.errno == os.errno.ENOENT:
            return False
        else:
            warn('Found command, but ' + cmd + ' could not be executed')
            return True
    return True


class ClusterSubmissionHook(ABC):
    def __init__(self, identifier):
        self.identifier = identifier
        self.state = None  # 0: everything is fine
        # 1: errors encountered
        self.status = None
        self.manager = None

        self.determine_state()

    @abstractmethod
    def determine_state(self):
        pass

    @abstractmethod
    def pre_run_routine(self):
        pass

    def post_run_routine(self):
        self.update_status()

    @abstractmethod
    def update_status(self):
        pass


class HookNotFoundException(Exception):
    pass
