import os
from abc import ABC, abstractmethod
from collections import namedtuple, Counter
from copy import copy
from random import shuffle
from subprocess import run, PIPE, DEVNULL
from warnings import warn
import numpy as np


class ClusterSubmission(ABC):
  def __init__(self):
    self.submitted = False
    self.finished = False

  @abstractmethod
  def submit(self):
    pass

  def __enter__(self):
    try:
      self.submit()
    except:
      self.close()
      print('Emergency cleanup! Check manually!')
      raise

  @abstractmethod
  def close(self):
    pass

  def __exit__(self, *args):
    self.close()

  @abstractmethod
  def get_status(self):
    pass

  @abstractmethod
  def check_error_msgs(self):
    pass

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
    return None

def is_command_available(cmd):
  try:
    run(cmd, stderr=DEVNULL, stdout=DEVNULL)
  except OSError as e:
    if e.errno == os.errno.ENOENT:
      return False
    else:
      warn('Found command, but '+cmd+' could not be executed')
      return True
  return True