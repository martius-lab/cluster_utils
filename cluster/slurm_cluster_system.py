import os
from collections import namedtuple, Counter
from copy import copy
from random import shuffle
from subprocess import run, PIPE
from warnings import warn

from .cluster_system import ClusterSubmission
from .constants import *

SlurmRecord = namedtuple('SlurmRecord',
                         ['ID', 'partition', 'name', 'owner', 'status', 'run_time', 'nodes', 'node_list'])

RUN_SCRIPT = SLURM_CLUSTER_RUN_SCRIPT
JOB_SPEC_FILE = SLURM_CLUSTER_JOB_SPEC_FILE

class Slurm_ClusterSubmission(ClusterSubmission):
  def __init__(self, requirements, jobs, submission_dir, name, remove_jobs_dir=True):
    super().__init__(jobs, name, submission_dir, remove_jobs_dir)
    self.njobs = len(jobs)
    self._process_requirements(requirements)
    self.exceptions_seen = set({})

  def get_submit_cmd(self, job_spec_file_path):
    return 'sbatch {}\n'.format(job_spec_file_path)

  def get_close_cmd(self, cluster_id):
    return 'scancel {}'.format(cluster_id)

  @property
  def total_jobs(self):
    return len(self.submission_cmds)

  def _process_requirements(self, requirements):
    # Job requirements
    self.mem = requirements['memory_in_mb']
    self.cpus = requirements['request_cpus']
    self.gpus = requirements['request_gpus']

    if self.gpus > 0 and requirements['cuda_requirement'] is not None:
      self.cuda_line = 'Requirements=CUDACapability>={}'.format(requirements['cuda_requirement'])
      self.partition = 'gpu'
      self.constraint = 'gpu'
      if not self.cpus == 32:
        self.cpus = 32
        warn('you requested a GPU -> no parallel execution on node. requested CPU count increased to 32')
    else:
      self.cuda_line = ''
      self.partition = 'general'
      self.constraint = ''

  def submit(self):
    if self.submitted:
      raise RuntimeError('Attempt for second submission!')
    self.submitted = True
    self.id_nums = []
    for idx, job in enumerate(self.jobs):
      result = job.submit(self, idx)
      good_lines = [line for line in result.split('\n') if 'Submitted' in line]
      bad_lines = [line for line in result.split('\n') if 'warning' in line or 'error' in line]
      if not good_lines or bad_lines:
        self.close()
        raise RuntimeError('Cluster submission failed')
      assert len(good_lines) == 1
      self.id_nums.append(good_lines[0].split(' ')[-1][:])
    self.submitted = True
    print('Jobs submitted successfully')

  def close(self):
    print('Killing remaining jobs...')
    if not self.submitted:
      raise RuntimeError('Submission cleanup called before submission completed')
    for job in self.jobs:
      job.close(self)
    print('Remaining jobs killed')
    self.finished = True
    super().close()

  def get_status(self):
    parsed_slurm = self._parse_slurm_info()
    if not parsed_slurm:
      return None
    id_set = set(self.id_nums)
    my_submissions = [sub for sub in parsed_slurm if sub.ID in id_set]
    stati = [sub.status for sub in my_submissions]
    nums = Counter(stati)
    return nums['R'], nums['PD'], nums['TO'] + nums['S'] + nums['ST']

  @staticmethod
  def _parse_slurm_info():
    result = run(['squeue'], shell=True, stdout=PIPE, stderr=PIPE)
    raw = result.stdout.decode('utf-8')
    err = result.stderr.decode('utf-8')
    if 'Failed' in err:
      warn('squeue currently unavailable')
      print(err)
      return None
    slurm_lines = raw.split('\n')
    slurm_parsed_lines = [[item for item in line.split(' ') if item] for line in slurm_lines]
    slurm_parsed_lines = [line for line in slurm_parsed_lines if len(line) > 7]
    if len(slurm_parsed_lines) == 0:
      warn('squeue currently unavailable (no lines returned)')
      return None

    stripped_db = [[item.strip() for item in line] for line in slurm_parsed_lines]

    fully_parsed = [SlurmRecord(*line) for line in stripped_db]
    return fully_parsed

  def check_error_msgs(self):
    found_err = False
    log_files = [filename for filename in os.listdir(self.submission_dir) if filename[-3:] == 'log']
    for log_file in log_files:
      with open(os.path.join(self.submission_dir, log_file)) as f:
        content = f.read()
      _, __, after = content.rpartition('return value ')
      if after and after[0] == '1':
        err_filename = log_file[:-3] + 'err'
        with open(os.path.join(self.submission_dir, err_filename)) as f_err:
          all_err = f_err.read()
        _, tb, error_log = all_err.rpartition('Traceback')
        exception = '{}{}'.format(tb, error_log)
        if exception and exception not in self.exceptions_seen:
          warn('Exception encountered -- see file {}!'.format(err_filename))
          warn(exception)
          self.exceptions_seen.add(exception)
          found_err = True
    return found_err
