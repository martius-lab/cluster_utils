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

CondorRecord = namedtuple('CondorRecord',
                          ['ID', 'owner', 'sub_date', 'sub_time', 'run_time', 'status', 'priority', 'size', 'cmd'])

class Condor_ClusterSubmission(ClusterSubmission):
  def __init__(self, job_commands, submission_dir, requirements, name, remove_jobs_dir=True):
    super().__init__(submission_dir, remove_jobs_dir)

    os.environ["MPLBACKEND"] = 'agg'
    self.cmds = list(job_commands)
    self._process_requirements(requirements)
    self.name = name
    self.exceptions_seen = set({})

    # Prepare all submission files

    self.submit_all_file = os.path.join(self.submission_dir, 'submit_{}.sh'.format(self.name))
    self.submission_cmds = []
    with open(self.submit_all_file, 'w') as submit_file:
      submit_file.write('#/bin/bash\n')

      for id, cmd in enumerate(self.cmds):
        job_file_name = '{}_{}.sh'.format(self.name, id)
        run_script_file_path = os.path.join(self.submission_dir, job_file_name)
        job_spec_file_path = os.path.join(self.submission_dir, job_file_name + '.sub')

        # Prepare namespace for string formatting (class vars + locals)
        namespace = copy(vars(self))
        namespace.update(locals())

        with open(run_script_file_path, 'w') as script_file:
          script_file.write(MPI_CLUSTER_RUN_SCRIPT % namespace)
        os.chmod(run_script_file_path, 0O755)  # Make executable

        with open(job_spec_file_path, 'w') as spec_file:
          spec_file.write(MPI_CLUSTER_JOB_SPEC_FILE % namespace)

        submit_cmd = 'condor_submit_bid {} {}\n'.format(self.bid, job_spec_file_path)
        submit_file.write(submit_cmd)
        self.submission_cmds.append(submit_cmd)

    # shuffle submission commands so that restarts of the same setting are spread
    shuffle(self.submission_cmds)

    os.chmod(self.submit_all_file, 0O755)  # Make executable

  @property
  def total_jobs(self):
    return len(self.submission_cmds)

  def _process_requirements(self, requirements):
    # Job requirements
    self.mem = requirements['memory_in_mb']
    self.cpus = requirements['request_cpus']
    self.gpus = requirements['request_gpus']
    self.bid = requirements['bid']

    other_requirements = []

    if self.gpus > 0 and requirements['cuda_requirement'] is not None:
      self.cuda_line = 'Requirements=CUDACapability>={}'.format(requirements['cuda_requirement'])
      self.partition = 'gpu'
      self.constraint = 'gpu'
    else:
      self.cuda_line = ''
      self.partition = 'general'
      self.constraint = ''

    if self.gpus > 0 and 'gpu_memory_mb' in requirements:
      other_requirements.append('TARGET.CUDAGlobalMemoryMb>{}'.format(requirements['gpu_memory_mb']))


    def hostnames_to_requirement(hostnames):
      single_reqs = [f'UtsnameNodename =?= \"{hostname}\"' for hostname in hostnames]
      return '(' + ' || '.join(single_reqs) + ')'

    hostname_list = requirements.get('hostname_list', [])
    if hostname_list:
      other_requirements.append(hostnames_to_requirement(hostname_list))

    if other_requirements:
      concat_requirements = ' && '.join(other_requirements)
      self.requirements_line = f"requirements={concat_requirements}"
    else:
      self.requirements_line = ''

  def submit(self):
    if self.submitted:
      raise RuntimeError('Attempt for second submission!')
    self.submitted = True
    self.id_nums = []
    for submit_cmd in self.submission_cmds:
      result = run([submit_cmd], cwd=str(self.submission_dir), shell=True, stdout=PIPE).stdout.decode('utf-8')
      good_lines = [line for line in result.split('\n') if 'submitted' in line]
      bad_lines = [line for line in result.split('\n') if 'WARNING' in line or 'ERROR' in line]
      if not good_lines or bad_lines:
        self.close()
        raise RuntimeError('Cluster submission failed')
      assert len(good_lines) == 1
      self.id_nums.append(good_lines[0].split(' ')[-1][:-1])
    self.submitted = True
    print('Jobs submitted successfully')

  def close(self):
    print('Killing remaining jobs...')
    if not self.submitted:
      raise RuntimeError('Submission cleanup called before submission completed')
    for id in self.id_nums:
      run(['condor_rm {}'.format(id)], shell=True, stderr=PIPE, stdout=PIPE)
    print('Remaining jobs killed')
    self.finished = True
    super().close()

  def get_status(self):
    parsed_condor = self._parse_condor_info()
    if not parsed_condor:
      return None
    id_set = set(self.id_nums)
    my_submissions = [sub for sub in parsed_condor if sub.ID.split('.')[0] in id_set]
    self.id_nums = [sub.ID.split('.')[0] for sub in my_submissions]
    nums = Counter([sub.status for sub in my_submissions])
    return nums['R'], nums['I'], nums['H']

  @staticmethod
  def _parse_condor_info():
    result = run(['condor_q'], shell=True, stdout=PIPE, stderr=PIPE)
    raw = result.stdout.decode('utf-8')
    err = result.stderr.decode('utf-8')
    if 'Failed' in err:
      warn('Condor_q currently unavailable')
      return None
    condor_lines = raw.split('\n')
    condor_parsed_lines = [[item for item in line.split(' ') if item] for line in condor_lines]
    condor_parsed_lines = [line for line in condor_parsed_lines if len(line) > 8]
    if len(condor_parsed_lines) == 0 or 'SUBMITTED' not in raw:
      warn('Condor_q currently unavailable')
      return None

    stripped_db = [[item.strip() for item in line] for line in condor_parsed_lines]
    concat_last = [line[:8] + [' '.join(line[8:])] for line in stripped_db]
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


