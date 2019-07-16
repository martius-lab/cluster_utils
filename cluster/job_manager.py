import numpy as np
import os
import shutil
from copy import deepcopy

from .optimizers import Metaoptimizer
from .cluster_system import get_cluster_type
from .constants import *
from .settings import update_recursive, optimizer_dict
from .submission import execute_iterated_submission
from .utils import get_sample_generator, process_other_params, get_caller_file, rm_dir_full
from .git_utils import ClusterSubmissionGitHook
from .job import Job
from .dummy_cluster_system import Dummy_ClusterSubmission
from warnings import warn
import nevergrad as ng
import pickle


def ensure_empty_dir(dir_name):
  if os.path.exists(dir_name):
    shutil.rmtree(dir_name, ignore_errors=True)
  os.makedirs(dir_name)


def dict_to_dirname(setting, id, smart_naming=True):
  vals = ['{}={}'.format(str(key)[:3], str(value)[:6]) for key, value in setting.items() if
          not isinstance(value, dict)]
  res = '{}_{}'.format(id, '_'.join(vals))
  if len(res) < 35 and smart_naming:
    return res
  return str(id)


def cluster_run(submission_name, paths, submission_requirements, other_params, optimizer, hyperparam_dict=None,
                num_samples=None, optimized_params=None, restarts_per_setting=1,
                smart_naming=True, remove_jobs_dir=True, git_params=None, run_local=None, extra_settings=None):
  # Directories and filenames
  ensure_empty_dir(paths['result_dir'])
  ensure_empty_dir(paths['jobs_dir'])

  setting_generator = get_sample_generator(num_samples, hyperparam_dict, optimizer)
  processed_other_params = process_other_params(other_params, hyperparam_dict, optimizer.optimized_params)

  def generate_jobs():
    for setting in setting_generator:
      for iteration in range(restarts_per_setting):
        current_setting = deepcopy(setting)
        local_other_params = deepcopy(processed_other_params)

        local_other_params['id'] = generate_jobs.id_number
        job_res_dir = dict_to_dirname(current_setting, generate_jobs.id_number, smart_naming)
        local_other_params['model_dir'] = os.path.join(paths['result_dir'], job_res_dir)

        update_recursive(current_setting, local_other_params)
        setting_cwd = 'cd {}'.format(os.path.dirname(paths['script_to_run']))
        if 'virtual_env_path' in paths:
          virtual_env_activate = 'source {}'.format(os.path.join(paths['virtual_env_path'], 'bin/activate'))
        else:
          virtual_env_activate = ''

        if 'custom_pythonpaths' in paths:
          raise NotImplementedError(
            'Setting custom pythonpath was deprecated. Set \"virtual_env_path\" instead.')

        if 'custom_python_executable_path' in paths:
          warn(
            'Setting custom_python_executable_path not recommended. Better set \"virtual_env_path\" instead.')

        base_exec_cmd = '{}'.format(paths.get('custom_python_executable_path', 'python3')) + ' {} {}'
        exec_cmd = base_exec_cmd.format(paths['script_to_run'], '\"' + str(current_setting) + '\"')
        execution_command = '\n'.join([setting_cwd, virtual_env_activate, exec_cmd])
        job = Job(execution_cmd=execution_command, id_number=generate_jobs.id_number, settings=current_setting)
        yield job
        generate_jobs.id_number += 1

  generate_jobs.id_number = 0

  cluster_type = get_cluster_type(requirements=submission_requirements, run_local=run_local)
  if cluster_type is None:
    raise OSError('Neither CONDOR nor SLURM was found. Not running locally')
  submission = cluster_type(jobs=generate_jobs(),
                            submission_dir=paths['jobs_dir'],
                            requirements=submission_requirements,
                            name=submission_name,
                            remove_jobs_dir=remove_jobs_dir)

  submission.register_submission_hook(ClusterSubmissionGitHook(git_params, paths))

  print('Jobs created:', generate_jobs.id_number)
  return submission


def update_best_job_datadirs(result_dir, model_dirs):
  datadir = os.path.join(result_dir, 'best_jobs')
  os.makedirs(datadir, exist_ok=True)

  short_names = [model_dir.split('_')[-1].replace('/', '_') for model_dir in model_dirs]

  # Copy over new best directories
  for model_dir in model_dirs:
    if os.path.exists(model_dir):
      new_dir_name = model_dir.split('_')[-1].replace('/', '_')
      new_dir_full = os.path.join(datadir, new_dir_name)
      shutil.copytree(model_dir, new_dir_full)
      rm_dir_full(model_dir)

  # Delete old best directories if outdated
  for dir_or_file in os.listdir(datadir):
    full_path = os.path.join(datadir, dir_or_file)
    if os.path.isfile(full_path):
      continue
    if dir_or_file not in short_names:
      rm_dir_full(full_path)


def initialize_hp_optimizer(result_dir, optimizer_str, optimized_params, metric_to_optimize, minimize, report_hooks,
                            number_of_samples, **optimizer_settings):
  possible_pickle = os.path.join(result_dir, STATUS_PICKLE_FILE)
  assert optimizer_str in optimizer_dict.keys()
  hp_optimizer = optimizer_dict[optimizer_str].try_load_from_pickle(possible_pickle, optimized_params,
                                                                    metric_to_optimize,
                                                                    minimize, report_hooks, **optimizer_settings)
  if hp_optimizer is None:
    hp_optimizer = optimizer_dict[optimizer_str](optimized_params=optimized_params,
                                                 metric_to_optimize=metric_to_optimize,
                                                 minimize=minimize, number_of_samples=number_of_samples,
                                                 report_hooks=report_hooks,
                                                 iteration_mode=True, **optimizer_settings)
  return hp_optimizer


def produce_cluster_run_all_args(optimizer, iteration, num_samples, base_paths_and_files, submission_requirements,
                                 other_params, remove_jobs_dir, git_params, run_local):
  submission_name = 'iteration_{}'.format(iteration + 1)
  new_paths = {key: value for key, value in base_paths_and_files.items()}
  new_paths['result_dir'] = os.path.join(new_paths['result_dir'], submission_name)

  return dict(submission_name=submission_name,
              paths=new_paths,
              submission_requirements=submission_requirements,
              optimizer=optimizer,
              other_params=other_params,
              restarts_per_setting=1,
              smart_naming=False,
              remove_jobs_dir=remove_jobs_dir,
              git_params=git_params,
              run_local=run_local,
              num_samples=num_samples)


def asynchronous_optimization(base_paths_and_files, submission_requirements, optimized_params, other_params,
                              number_of_samples, metric_to_optimize, minimize, optimizer_str='cem_metaoptimizer',
                              remove_jobs_dir=True, git_params=None, run_local=None, num_best_jobs_whose_data_is_kept=0,
                              report_hooks=None, optimizer_settings={}):
  hp_optimizer = initialize_hp_optimizer(base_paths_and_files['result_dir'], optimizer_str, optimized_params,
                                         metric_to_optimize, minimize, report_hooks, number_of_samples,
                                         **optimizer_settings)
  all_args = produce_cluster_run_all_args(hp_optimizer, hp_optimizer.iteration, number_of_samples)
  submission = cluster_run(**all_args, )
  n_successful_jobs = 0
  while n_successful_jobs < number_of_samples:
    submission.submit()
    n_successful_jobs = submission.get_n_successful_jobs()


def hyperparameter_optimization(base_paths_and_files, submission_requirements, optimized_params, other_params,
                                number_of_samples, metric_to_optimize, minimize, total_rounds,
                                fraction_that_need_to_finish,
                                optimizer_str='cem_metaoptimizer', remove_jobs_dir=True, git_params=None,
                                run_local=None, num_best_jobs_whose_data_is_kept=0, report_hooks=None,
                                optimizer_settings={}):
  calling_script = get_caller_file(depth=2)

  hp_optimizer = initialize_hp_optimizer(base_paths_and_files['result_dir'], optimizer_str, optimized_params,
                                         metric_to_optimize, minimize, report_hooks, number_of_samples,
                                         **optimizer_settings)

  if git_params and 'url' in git_params:
    git_params['remove_local_copy'] = True  # always remove git repo copy in case of hyperparameter optimization

  for i in range(total_rounds):
    print('Iteration {} started.'.format(hp_optimizer.iteration + 1))

    all_args = produce_cluster_run_all_args(hp_optimizer, hp_optimizer.iteration, number_of_samples)
    submission = cluster_run(**all_args, )

    # run_local = isinstance(submission, Dummy_ClusterSubmission)

    current_result_path = os.path.join(base_paths_and_files['result_dir'], all_args['submission_name'])

    print(hp_optimizer.get_best())

    df, params, metrics, submission_hook_stats = execute_iterated_submission(submission, current_result_path,
                                                                             fraction_need_to_finish=fraction_that_need_to_finish,
                                                                             min_fraction_to_finish=hp_optimizer.min_fraction_to_finish(),
                                                                             ignore_errors=True)
    if metric_to_optimize not in metrics:
      raise ValueError('Optimized metric \'{}\' not found in output'.format(metric_to_optimize))
    if not np.issubdtype(df[metric_to_optimize].dtype, np.number):
      raise ValueError('Optimized metric \'{}\' is not a numerical type'.format(metric_to_optimize))

    hp_optimizer.tell(df)
    hp_optimizer.save_data_and_self(base_paths_and_files['result_dir'])
    pdf_output = os.path.join(base_paths_and_files['result_dir'], 'result.pdf')

    hp_optimizer.save_pdf_report(pdf_output, calling_script, submission_hook_stats, current_result_path)

    if num_best_jobs_whose_data_is_kept > 0:
      best_model_dirs = hp_optimizer.best_jobs_model_dirs(how_many=num_best_jobs_whose_data_is_kept)
      update_best_job_datadirs(base_paths_and_files['result_dir'], best_model_dirs)

    rm_dir_full(current_result_path)
    print('Intermediate results deleted...')

  print('Procedure successfully finished')
