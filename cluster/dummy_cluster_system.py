import os
from random import shuffle
from copy import copy
from .cluster_system import ClusterSubmission
from multiprocessing import cpu_count
import concurrent.futures
from subprocess import run, PIPE
from .constants import *
from warnings import warn
import random
from time import sleep

class Dummy_ClusterSubmission(ClusterSubmission):
  def __init__(self, requirements, jobs, submission_dir, name, remove_jobs_dir=True):
    super().__init__(jobs, name, submission_dir, remove_jobs_dir)
    self._process_requirements(requirements)
    self.exceptions_seen = set({})
    self.available_cpus = range(cpu_count())

  def get_submit_cmd(self, job_spec_file_path):
    raise NotImplementedError

  def get_close_cmd(self, cluster_id):
    raise NotImplementedError

  @property
  def total_jobs(self):
    return len(self.jobs)

  def _process_requirements(self, requirements):
    self.cpus_per_job = requirements['request_cpus']
    self.max_cpus = requirements.get('max_cpus', cpu_count())
    if self.max_cpus <= 0:
      raise ValueError('CPU limit must be positive. Not {}.'.format(self.max_cpus))
    self.available_cpus =  min(self.max_cpus, cpu_count())
    self.concurrent_jobs = self.available_cpus // self.cpus_per_job
    if self.concurrent_jobs == 0:
      warn('Total number of CPUs is smaller than requested CPUs per job. Resorting to 1 CPU per job')
      self.concurrent_jobs = self.available_cpus
    assert self.concurrent_jobs > 0

  def submit(self):
    if self.submitted:
      raise RuntimeError('Attempt for second submission!')
    self.submitted = True

    self.executor = concurrent.futures.ProcessPoolExecutor(self.concurrent_jobs)
    self.futures = []
    for job in self.jobs:
      free_cpus = random.sample(self.available_cpus, self.cpus_per_job)
      free_cpus_str = ','.join(map(str, free_cpus))


      cmd = 'taskset --cpu-list {} bash {}'.format(free_cpus_str, job.execution_cmd)
      self.futures.append(self.executor.submit(run, cmd, stdout=PIPE, stderr=PIPE, shell=True))

    print('Jobs submitted successfully.')

  def close(self):
    print('Killing remaining jobs...')
    if not self.submitted:
      raise RuntimeError('Submission cleanup called before submission completed')
    for future in self.futures:
      future.cancel()
    concurrent.futures.wait(self.futures)
    print('Remaining jobs killed')
    self.finished = True

    super().close()

  def get_status(self):
    running = min(sum([future.running() for future in self.futures]),
                  self.concurrent_jobs)
    done = sum([future.done() for future in self.futures])
    idle = self.total_jobs - (done + running)
    failed = len([future for future in self.futures if future.done() and future.result().__dict__['returncode'] == 1])
    held = failed

    return min(running, self.concurrent_jobs), idle, held

  def check_error_msgs(self):

    failed = [future for future in self.futures if future.done() and future.result().__dict__['returncode'] == 1]
    errs = set([future.result().stderr.decode() for future in failed])
    for err in errs:
      if err not in self.exceptions_seen:
        self.exceptions_seen.add(err)
        warn(err)
    return len(errs) > 0
