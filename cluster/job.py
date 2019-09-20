from concurrent.futures import Future
import os
from copy import copy
from .constants import *
from subprocess import run, PIPE
from copy import deepcopy
from warnings import warn
from .utils import dict_to_dirname
from .settings import update_recursive
import pandas as pd

class Job():
  def __init__(self, id_number, candidate, settings, other_params, paths, iteration):
    self.paths = paths
    self.id_number = id_number
    self.candidate = candidate
    self.settings = settings
    self.other_params = other_params
    self.submission_name = None
    self.cluster_id = None
    self.results_accessed = False
    self.job_spec_file_path = False
    self.iteration = iteration

  def generate_execution_cmd(self, paths):
    current_setting = deepcopy(self.settings)
    update_recursive(current_setting, self.other_params)
    current_setting['id'] = self.id_number
    job_res_dir = dict_to_dirname(current_setting, self.id_number, smart_naming=False)
    current_setting['model_dir'] = os.path.join(paths['current_result_dir'], job_res_dir)


    setting_cwd = 'cd {}'.format(os.path.dirname(paths['script_to_run']))
    if 'virtual_env_path' in paths:
      virtual_env_activate = 'source {}'.format(os.path.join(paths['virtual_env_path'], 'bin/activate'))
    else:
      virtual_env_activate = ''

    if 'custom_pythonpaths' in paths:
      raise NotImplementedError('Setting custom pythonpath was deprecated. Set \"virtual_env_path\" instead.')

    if 'custom_python_executable_path' in paths:
      warn('Setting custom_python_executable_path not recommended. Better set \"virtual_env_path\" instead.')

    base_exec_cmd = '{}'.format(paths.get('custom_python_executable_path', 'python3')) + ' {} {}'
    exec_cmd = base_exec_cmd.format(paths['script_to_run'], '\"' + str(current_setting) + '\"')

    res = '\n'.join([setting_cwd, virtual_env_activate, exec_cmd])
    return res

  def get_results(self, remember=True):
    base_path = self.paths['current_result_dir']
    job_output_files = (CLUSTER_PARAM_FILE, CLUSTER_METRIC_FILE)
    path = os.path.join(base_path, str(self.id_number))
    if os.path.isdir(path) and all([filename in os.listdir(path) for filename in job_output_files]):
      try:
        param_df, metric_df = (pd.read_csv(os.path.join(path, filename)) for filename in job_output_files)
        resulting_df = pd.concat([param_df, metric_df], axis=1)
        if remember:
          self.results_accessed = True
        return resulting_df, tuple(sorted(param_df.columns)), tuple(sorted(metric_df.columns))
      except pd.errors.EmptyDataError:
        return None
    return None
