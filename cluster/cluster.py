import os
from collections import namedtuple, Counter
from copy import copy
from random import shuffle
from subprocess import run, PIPE
from warnings import warn

from .constants import *


class ClusterSubmission(object):
  def __init__(self):
    self.submitted = False
    self.finished = False

  def submit(self):
    """ Submit jobs """
    raise NotImplementedError('submit not provided')

  def __enter__(self):
    try:
      self.submit()
    except:
      self.close()
      print('Emergency cleanup! Check manually!')
      raise

  def close(self):
    """ Submission cleanup """
    raise NotImplementedError('close not provided')

  def __exit__(self, *args):
    self.close()

  def get_status(self):
    """ Submission status """
    raise NotImplementedError('get_submission_status not provided')

  def check_error_msgs(self):
    """ Submission status """
    raise NotImplementedError('print_error_msgs not provided')


CondorRecord = namedtuple('CondorRecord',
                          ['ID', 'owner', 'sub_date', 'sub_time', 'run_time', 'status', 'priority', 'size', 'cmd'])


class Condor_ClusterSubmission(ClusterSubmission):
  def __init__(self, job_commands, submission_dir, requirements, name, project_dir):
    super().__init__()
    self.cmds = job_commands
    self.submission_dir = submission_dir
    self._process_requirements(requirements)
    self.name = name
    self.project_dir = project_dir
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

  def _process_requirements(self, requirements):
    # Job requirements
    self.mem = requirements['memory_in_mb']
    self.cpus = requirements['request_cpus']
    self.gpus = requirements['request_gpus']
    self.bid = requirements['bid']

    if self.gpus > 0 and requirements['cuda_requirement'] is not None:
      self.cuda_line = 'Requirements=CUDACapability>={}'.format(requirements['cuda_requirement'])
    else:
      self.cuda_line = ''

  def submit(self):
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
      run(['condor_rm {}'.format(id)], shell=True, stdout=PIPE, stderr=PIPE)
    print('Remaining jobs killed')
    self.finished = True

  def get_status(self):
    parsed_condor = self._parse_condor_info()
    if not parsed_condor:
      return None
    id_set = set(self.id_nums)
    my_submissions = [sub for sub in parsed_condor if sub.ID.split('.')[0] in id_set]
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
    if len(condor_parsed_lines) == 0:
      warn('Condor_q currently unavailable')
      return None

    stripped_db = [[item.strip() for item in line] for line in condor_parsed_lines]
    concat_last = [line[:8] + [' '.join(line[8:])] for line in stripped_db]
    fully_parsed = [CondorRecord(*line) for line in concat_last]
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