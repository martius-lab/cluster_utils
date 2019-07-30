from concurrent.futures import Future
import os
from copy import copy
from .constants import *
from subprocess import run, PIPE
from copy import deepcopy
from warnings import warn
from .utils import dict_to_dirname
import pandas as pd

class Job():
  def __init__(self, id_number, settings, paths):
    self.paths = paths
    self.id_number = id_number
    self.settings = settings
    self.submission_name = None
    self.cluster_id = None
    self.results_accessed = False
    self.job_spec_file_path = False

  def generate_execution_cmd(self, paths):
    current_setting = deepcopy(self.settings)
    current_setting['id'] = self.id_number
    job_res_dir = dict_to_dirname(current_setting, self.id_number, smart_naming=False)
    current_setting['model_dir'] = os.path.join(paths['result_dir'], job_res_dir)

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
    print('Execution command start')
    print(res)
    print('Execution command end')
    return res

  def load_dirs_containing_cluster_output(self, base_path):
    job_output_files = (CLUSTER_PARAM_FILE, CLUSTER_METRIC_FILE)
    print('still here')
    for _ in os.walk(base_path):
      print(_)
    for root, dirs, files in os.walk(base_path):
      print('#####################')
      print(root)
      print(dirs)
      print(files)
      print('#####################')
      if all([filename in files for filename in job_output_files]):
        param_df, metric_df = (pd.read_csv(os.path.join(root, filename)) for filename in job_output_files)
        resulting_df = pd.concat([param_df, metric_df], axis=1)
        yield resulting_df, tuple(sorted(param_df.columns)), tuple(sorted(metric_df.columns))

  def get_results(self):
    self.results_accessed = True
    base_path = self.paths['result_dir']
    print(base_path)
    output = list(zip(*self.load_dirs_containing_cluster_output(base_path)))

    if not output:
      return [], [], []

    all_dfs, all_params, all_metrics = output

    if not len(set(all_params)) == 1:
      warn("Two files had non-identical parameters. Missing data?")

    if not len(set(all_metrics)) == 1:
      warn("Two files had non-identical metrics. Missing data?")

    return pd.concat(all_dfs, ignore_index=True), all_params[0], all_metrics[0]
