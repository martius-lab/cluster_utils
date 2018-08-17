import os
from .cluster_system import ClusterSubmission
from collections import namedtuple
from copy import copy
from random import shuffle
from subprocess import run, PIPE
from warnings import warn
import numpy as np
from .constants import *

SlurmRecord = namedtuple('SlurmRecord',
                          ['ID', 'partition', 'name', 'owner', 'status', 'run_time', 'nodes', 'node_list'])

class Slurm_ClusterSubmissionParallel(ClusterSubmission):
  def __init__(self, job_commands, submission_dir, requirements, name, git_conn=None):
    super().__init__(git_conn=git_conn)
    self.njobs = len(job_commands)
    self.cmds = job_commands
    self.submission_dir = submission_dir
    self._process_requirements(requirements)
    self.name = name
    self.exceptions_seen = set({})
    self.expected_log_files = []


    RUN_SCRIPT = SLURM_PARALLEL_CLUSTER_RUN_SCRIPT
    JOB_SPEC_FILE_START = SLURM_PARALLEL_CLUSTER_JOB_SPEC_FILE_START
    TASK_SPEC_FILE = SLURM_PARALLEL_CLUSTER_TASK_SPEC_FILE
    JOB_SPEC_FILE_END = SLURM_PARALLEL_CLUSTER_JOB_SPEC_FILE_END
    self.tasks_per_submission = self.nnodes_per_submit * self.jobs_per_node

    # Prepare all submission files

    self.submit_all_file = os.path.join(self.submission_dir, 'submit_{}.sh'.format(self.name))
    self.submission_cmds = []
    with open(self.submit_all_file, 'w') as submit_file:
      submit_file.write('#/bin/bash\n')
      cmd_enum = enumerate(self.cmds)
      for id, cmd in cmd_enum:
        job_file_name = '{}_{}.sh'.format(self.name, id)
        run_script_file_path = os.path.join(self.submission_dir, job_file_name)
        job_spec_file_path = os.path.join(self.submission_dir, 'submission_' + job_file_name)



        # Prepare namespace for string formatting (class vars + locals)
        namespace = copy(vars(self))
        namespace.update(locals())
        with open(job_spec_file_path, 'w') as spec_file:
          spec_file.write(JOB_SPEC_FILE_START % namespace)
          for idPerSubmission in range(self.tasks_per_submission):
            with open(run_script_file_path, 'w') as script_file:
              script_file.write(RUN_SCRIPT % namespace)
            os.chmod(run_script_file_path, 0O755)  # Make executable
            spec_file.write(TASK_SPEC_FILE % namespace)
            self.expected_log_files.append(run_script_file_path+'.err')
            if idPerSubmission < self.tasks_per_submission-1:
              cmd = next(cmd_enum, None)
              id += 1
            if not cmd:
              break
            cmd=cmd[1]
            job_file_name = '{}_{}.sh'.format(self.name, id)
            run_script_file_path = os.path.join(self.submission_dir, job_file_name)
            namespace.update(locals())

          spec_file.write(JOB_SPEC_FILE_END % namespace)

        submit_cmd = 'sbatch {}\n'.format(job_spec_file_path)
        submit_file.write(submit_cmd)
        self.submission_cmds.append(submit_cmd)

    # shuffle submission commands so that restarts of the same setting are spread
    shuffle(self.submission_cmds)

    os.chmod(self.submit_all_file, 0O755)  # Make executable

  @property
  def total_jobs(self):
    return (self.njobs)

  def _process_requirements(self, requirements):
    # Job requirements
    self.mem = requirements['memory_in_mb']
    self.cpus = requirements['request_cpus']
    self.gpus = requirements['request_gpus']

    if self.gpus > 0 and requirements['cuda_requirement'] is not None:
      warn('you requested a GPU -> no parallel execution possible - this is likely/certain to crash')
    else:
      self.cuda_line = ''
      self.partition = 'general'
      self.constraint = ''

      self.mem_per_cpu = int(self.mem / self.cpus)
      cpu_scaling_due_to_mem_restrictions = (self.mem_per_cpu / 1900)
      if cpu_scaling_due_to_mem_restrictions>1:
        self.cpus = int(np.ceil(self.cpus*cpu_scaling_due_to_mem_restrictions))
        self.mem_per_cpu = int(self.mem / self.cpus)
        warn('Number of CPUs increased to overcome RAM per CPU restrictions')
      self.jobs_per_node = int(np.minimum(np.floor(32.0/self.cpus), np.floor(32000.0/self.mem)))
      self.nnodes = int(np.ceil(self.njobs/self.jobs_per_node))
      self.nnodes_per_submit = int(np.ceil(self.nnodes/15))
      self.ntasks = self.nnodes_per_submit*self.jobs_per_node


      self.nodeMem = self.mem_per_cpu*self.cpus*self.jobs_per_node
  def submit(self):
    if self.submitted:
      raise RuntimeError('Attempt for second submission!')
    self.submitted = True
    self.id_nums = []
    for submit_cmd in self.submission_cmds:
      result = run([submit_cmd], cwd=str(self.submission_dir), shell=True, stdout=PIPE).stdout.decode('utf-8')
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

    for id in self.id_nums:
      run(['scancel {}'.format(id)], shell=True, stdout=PIPE, stderr=PIPE)
    print('Remaining jobs killed')
    self.finished = True

  def get_status(self):
    running_tasks = 0
    finished_tasks = 0
    broken_tasks = 0
    for log_file in self.expected_log_files:
      path_to_log_file = os.path.join(self.submission_dir, log_file)
      if os.path.isfile(path_to_log_file):
        running_tasks += 1
        finished = False
        broken = False
        with open(path_to_log_file) as log:
          for line in log:
            line = line.rstrip()
            if 'exit code' in line:
              returnValue = int(line.split('exit code')[1].split('.')[0])
              #line = line[1]
              #line = line.split('.')
              #line = int(line[0])
              if returnValue == 0:
                finished = True
              else:
                broken = True
        if finished:
          finished_tasks += 1
          running_tasks -= 1
        if broken:
          broken_tasks += 1
          running_tasks -= 1
    return running_tasks, self.njobs-running_tasks - finished_tasks - broken_tasks, 0


  def check_error_msgs(self):
    found_err = False
    log_files = [filename for filename in os.listdir(self.submission_dir) if filename[-3:] == 'err']
    for log_file in log_files:
      with open(os.path.join(self.submission_dir, log_file)) as f:
        content = f.read()
      _, __, after = content.rpartition('exit code ')
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
