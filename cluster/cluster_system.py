import os
from abc import ABC, abstractmethod
from subprocess import run, DEVNULL
from warnings import warn


class ClusterSubmission(ABC):
  def __init__(self):
    self.submitted = False
    self.finished = False
    self.submission_hooks = dict()

  def register_submission_hook(self, hook):
    assert isinstance(hook, ClusterSubmissionHook)
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


def get_cluster_type(requirements):
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
    answere = input('No cluster detected. Do you want to run locally? [y/N]: ')
    if answere.lower() == 'y':
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
    self.status = None
    self.manager = None

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
