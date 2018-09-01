import os
import shutil
from abc import ABC, abstractmethod
from subprocess import run, DEVNULL
from warnings import warn


class ClusterSubmission(ABC):
  def __init__(self, submission_dir, remove_jobs_dir=True):
    self.remove_jobs_dir = remove_jobs_dir
    self.submission_dir = submission_dir
    self.submitted = False
    self.finished = False
    self.submission_hooks = dict()

  def register_submission_hook(self, hook):
    assert isinstance(hook, ClusterSubmissionHook)
    if hook.state > 0: return
    print('Register submission hook {}'.format(hook.identifier))
    self.submission_hooks[hook.identifier] = hook
    hook.manager = self

  def unregister_submission_hook(self, identifier):
    if identifier in self.submission_hooks:
      print('Unregister submission hook {}'.format(identifier))
      self.submission_hooks.manager = None
      self.submission_hooks.pop(identifier)
    else:
      raise HookNotFoundException('Hook not found. Can not unregister')

  def exec_pre_submission_routines(self):
    for hook in self.submission_hooks.values():
      hook.pre_submission_routine()

  def exec_post_submission_routines(self):
    for hook in self.submission_hooks.values():
      hook.post_submission_routine()

  def collect_stats_from_hooks(self):
    stats = {hook.identifier: hook.status for hook in self.submission_hooks.values()}
    return stats

  @abstractmethod
  def submit(self):
    pass

  def __enter__(self):
    try:
      self.exec_pre_submission_routines()
      self.submit()
    except:
      self.close()
      print('Emergency cleanup! Check manually!')
      raise

  def close(self):
    self.exec_post_submission_routines()
    if self.remove_jobs_dir:
      print('Removing jobs dir {} ... '.format(self.submission_dir), end='')
      shutil.rmtree(self.submission_dir, ignore_errors=True)
      print('Done')

  def __exit__(self, *args):
    self.close()

  @abstractmethod
  def get_status(self):
    pass

  @abstractmethod
  def check_error_msgs(self):
    pass


from .dummy_cluster_system import Dummy_ClusterSubmission
from .condor_cluster_system import Condor_ClusterSubmission
from .slurm_cluster_system import Slurm_ClusterSubmission
from .slurm_parallel_cluster_system import Slurm_ClusterSubmissionParallel


def get_cluster_type(requirements, run_local=None):
  if is_command_available('condor_q'):
    print('CONDOR detected, running CONDOR job submission')
    return Condor_ClusterSubmission
  elif is_command_available('squeue'):
    print('SLURM detected, running SLURM job submission')
    gpus = requirements['request_gpus']
    if gpus > 0:
      print('GPU requested, on-node parallelisation impossible')
      return Slurm_ClusterSubmission
    else:
      print('No GPU requested, on-node parallelisation used')
      return Slurm_ClusterSubmissionParallel
  else:
    if run_local is None:
      answer = input('No cluster detected. Do you want to run locally? [y/N]: ')
      if answer.lower() == 'y':
        run_local = True
      else:
        run_local = False

    if run_local:
      return Dummy_ClusterSubmission
    else:
        return None


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
    self.state = None # 0: everything is fine
                      # 1: errors encountered
    self.status = None
    self.manager = None

    self.determine_state()

  @abstractmethod
  def determine_state(self):
    pass

  @abstractmethod
  def pre_submission_routine(self):
    pass

  def post_submission_routine(self):
    self.update_status()

  @abstractmethod
  def update_status(self):
    pass

class HookNotFoundException(Exception):
  pass
