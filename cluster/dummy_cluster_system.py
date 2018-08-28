import os
from random import shuffle
from copy import copy
from .cluster_system import ClusterSubmission
from multiprocessing import cpu_count
import concurrent.futures
from subprocess import run, PIPE
from .constants import *

class Dummy_ClusterSubmission(ClusterSubmission):
  def __init__(self, job_commands, submission_dir, requirements, name, remove_jobs_dir=True):
    super().__init__(submission_dir, remove_jobs_dir)
    self.cmds = job_commands
    self._process_requirements(requirements)
    self.name = name
    self.exceptions_seen = set({})

    self.submission_cmds = []
    for id, cmd in enumerate(self.cmds):
      job_file_name = '{}_{}.sh'.format(self.name, id)
      run_script_file_path = os.path.join(self.submission_dir, job_file_name)

      # Prepare namespace for string formatting (class vars + locals)
      namespace = copy(vars(self))
      namespace.update(locals())

      with open(run_script_file_path, 'w') as script_file:
        script_file.write(LOCAL_RUN_SCRIPT % namespace)
      os.chmod(run_script_file_path, 0O755)  # Make executable

      self.submission_cmds.append(run_script_file_path)

    # shuffle submission commands so that restarts of the same setting are spread
    shuffle(self.submission_cmds)

  @property
  def total_jobs(self):
    return len(self.submission_cmds)

  def _process_requirements(self, requirements):
    self.cpus_per_job = requirements['request_cpus']
    self.max_cpus = requirements.get('max_cpus', 1)
    self.available_cpus =  min(self.max_cpus, cpu_count())
    self.concurrent_jobs = self.available_cpus // self.cpus_per_job

  def submit(self):
    if self.submitted:
      raise RuntimeError('Attempt for second submission!')
    self.submitted = True

    self.executor = concurrent.futures.ProcessPoolExecutor(self.concurrent_jobs)
    self.futures = [self.executor.submit(run, ['bash', submit_cmd], stdout=PIPE, stderr=PIPE) for submit_cmd in self.submission_cmds]

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
    found_err = False
    return found_err
