import os
import ast
from .cluster_system import ClusterSubmission
from collections import namedtuple, Counter
from copy import copy
from random import shuffle
from subprocess import run, PIPE
from warnings import warn
from .constants import *
from contextlib import suppress
import pandas as pd
from threading import Thread
import time

CondorRecord = namedtuple('CondorRecord',
                          ['ID', 'owner', 'sub_date', 'sub_time', 'run_time', 'status', 'priority', 'size', 'cmd'])

class Condor_ClusterSubmission(ClusterSubmission):
  def __init__(self, requirements, paths, name, remove_jobs_dir=True, iteration_mode=True):
    super().__init__(name, paths, remove_jobs_dir, iteration_mode)

    os.environ["MPLBACKEND"] = 'agg'
    self._process_requirements(requirements)
    self.name = name
    self.exceptions_seen = set({})
    user_name = run('whoami', shell=True, stdout=PIPE, stderr=PIPE).stdout.decode('utf-8').rstrip('\n')
    self.condor_q_cmd = 'condor_q {}\n'.format(user_name)
    print('condor_q_cmd: ', self.condor_q_cmd)
    condor_q_info = run([self.condor_q_cmd], shell=True, stdout=PIPE, stderr=PIPE)
    self.condor_q_info_raw = condor_q_info.stdout.decode('utf-8')
    self.condor_q_info_err = condor_q_info.stderr.decode('utf-8')
    t = Thread(target=self.update_condor_q_info, args=())
    self.exec_pre_submission_routines()
    t.start()

  def submit_fn(self, job):
    self.generate_job_spec_file(job)
    submit_cmd = 'condor_submit_bid {} {}\n'.format(self.bid, job.job_spec_file_path)
    result = run([submit_cmd], cwd=str(self.submission_dir), shell=True, stdout=PIPE).stdout.decode('utf-8')
    good_lines = [line for line in result.split('\n') if 'submitted' in line]
    bad_lines = [line for line in result.split('\n') if 'WARNING' in line or 'ERROR' in line]
    if not good_lines or bad_lines:
      self.close()
      print('########################\n',result,'########################\n')
      raise RuntimeError('Cluster submission failed')
    assert len(good_lines) == 1
    new_cluster_id = good_lines[0].split(' ')[-1][:-1]
    return new_cluster_id

  def stop_fn(self, cluster_id):
    cmd = 'condor_rm {}'.format(cluster_id)
    return run([cmd], shell=True, stderr=PIPE, stdout=PIPE)

  def generate_job_spec_file(self, job):
    job_file_name = '{}_{}.sh'.format(self.name, job.id_number)
    run_script_file_path = os.path.join(self.submission_dir, job_file_name)
    job_spec_file_path = os.path.join(self.submission_dir, job_file_name + '.sub')
    cmd = job.generate_execution_cmd(self.paths)
    # Prepare namespace for string formatting (class vars + locals)
    namespace = copy(vars(self))
    namespace.update(vars(job))
    namespace.update(locals())

    with open(run_script_file_path, 'w') as script_file:
      script_file.write(MPI_CLUSTER_RUN_SCRIPT % namespace)
    os.chmod(run_script_file_path, 0O755)  # Make executable

    with open(job_spec_file_path, 'w') as spec_file:
      spec_file.write(MPI_CLUSTER_JOB_SPEC_FILE % namespace)

    job.job_spec_file_path = job_spec_file_path

  def status(self, job):
    parsed_info = self._parse_condor_info(job.cluster_id)
    if parsed_info is None:
      if job.cluster_id is None:
        return 0
      else:
        return 10
    parsed_info = parsed_info[0]
    status = parsed_info.status
    if status == 'R':
      return 2
    if status == 'H':
      return 4
    if status == 'I':
      return 1
    if status == 'C':
      return 3
    print(parsed_info)

  def is_blocked(self):
    for job in self.jobs:
      if self.status(job) == 1:
        return True
    return False

  #TODO: Check that two simultaneous HPOs dont collide

  def _process_requirements(self, requirements):
    # Job requirements
    self.mem = requirements['memory_in_mb']
    self.cpus = requirements['request_cpus']
    self.gpus = requirements['request_gpus']
    self.bid = requirements['bid']

    if self.gpus > 0 and requirements['cuda_requirement'] is not None:
      self.cuda_line = 'Requirements=CUDACapability>={}'.format(requirements['cuda_requirement'])
      self.partition = 'gpu'
      self.constraint = 'gpu'
    else:
      self.cuda_line = ''
      self.partition = 'general'
      self.constraint = ''

    if self.gpus > 0 and 'gpu_memory_mb' in requirements:
      self.gpu_memory_line = 'Requirements=TARGET.CUDAGlobalMemoryMb>{}'.format(requirements['gpu_memory_mb'])
    else:
      self.gpu_memory_line = ''

  '''
  def submit_fn(self, job, idx):
    submit_cmd = self.get_submit_cmd(job.generate_job_spec_file(idx))
    result = run([submit_cmd], cwd=str(self.submission_dir), shell=True, stdout=PIPE).stdout.decode('utf-8')

    good_lines = [line for line in result.split('\n') if 'submitted' in line]
    bad_lines = [line for line in result.split('\n') if 'WARNING' in line or 'ERROR' in line]
    if not good_lines or bad_lines:
      self.close()
      raise RuntimeError('Cluster submission failed')
    assert len(good_lines) == 1
    job.cluster_id = good_lines[0].split(' ')[-1][:-1]
  '''


  def update_condor_q_info(self):
    #TODO: update only if new results make sense
    while(True):
      condor_q_info = run([self.condor_q_cmd], shell=True, stdout=PIPE, stderr=PIPE)
      self.condor_q_info_raw = condor_q_info.stdout.decode('utf-8')
      self.condor_q_info_err = condor_q_info.stderr.decode('utf-8')
      time.sleep(5)
    #regression has limited depth self.update_condor_q_info()

  '''
  def get_status(self):
    parsed_condor = self._parse_condor_info()
    if not parsed_condor:
      return None
    id_set = set(self.id_nums)
    my_submissions = [sub for sub in parsed_condor if sub.ID.split('.')[0] in id_set]
    self.id_nums = [sub.ID.split('.')[0] for sub in my_submissions]
    nums = Counter([sub.status for sub in my_submissions])
    return nums['R'], nums['I'], nums['H']
  '''

  def _parse_condor_info(self, cluster_id=None):
    raw = self.condor_q_info_raw
    err = self.condor_q_info_err
    if 'Failed' in err:
      warn('Condor_q currently unavailable')
      return None
    condor_lines = raw.split('\n')
    condor_parsed_lines = [[item for item in line.split(' ') if item] for line in condor_lines[:-2]]
    condor_parsed_lines = [line for line in condor_parsed_lines if len(line) > 8]
    if len(condor_parsed_lines) == 0 or 'SUBMITTED' not in raw:
      return None
    stripped_db = [[item.strip() for item in line] for line in condor_parsed_lines]
    concat_last = [line[:8] + [' '.join(line[8:])] for line in stripped_db]
    if not cluster_id is None:
      concat_last = [line for line in concat_last if str(int(float(line[0]))) == cluster_id]
      if len(concat_last) == 0:
        return None
      if len(concat_last) > 1:
        raise ValueError('Found two jobs with same cluster ID')
    fully_parsed = [CondorRecord(*line) for line in concat_last]
    return fully_parsed

  def check_error_msgs(self):
    found_err = False
    log_files = [filename for filename in os.listdir(self.submission_dir) if filename[-3:] == 'log']
    with suppress(FileNotFoundError):  # Cluster file system is unreliable. Unavailability should NOT kill the whole run
      for log_file in log_files:
        content = ''  # Default value if file open (silently!) fails
        with open(os.path.join(self.submission_dir, log_file)) as f:
          content = f.read()
        _, __, after = content.rpartition('return value ')
        if after and after[0] == '1':
          err_filename = log_file[:-3] + 'err'
          all_err = ''  # Default value if file open (silently!) fails
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




'''
  def save_job_info(self, result_dir):

    def extract_dict_from_cmd(cmd_string):
      # Detecting dict by '{' '}' in cmd_string (gross, I know, but is allowed to fail)
      if '{' not in cmd_string:
        return None
      index = cmd_string.find('{')
      try:
        return ast.literal_eval(cmd_string[index: -1])   # string ends with " so it is ignored 
      except SyntaxError:
        return None
      except ValueError:
        return None


    cmd_dicts = [extract_dict_from_cmd(dct) for dct in self.cmds]

    if cmd_dicts is None:
      return False

    for dct, id_num in zip(cmd_dicts, self.id_nums):
      if dct is not None:
        dct['cluster_job_id'] = id_num

        for key in dct:   # Turn all to one element lists
          dct[key] = [dct[key]]

    dfs = [pd.DataFrame.from_dict(dct) for dct in cmd_dicts if dct is not None]
    big_df = pd.concat(dfs)
    big_df = big_df.sort_values(['cluster_job_id'], ascending=True)
    big_df.to_csv(os.path.join(result_dir, JOB_INFO_FILE))
    return True
'''
