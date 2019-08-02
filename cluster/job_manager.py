import numpy as np
import os
import shutil
from copy import deepcopy

from .cluster_system import get_cluster_type
from .constants import *
from .settings import update_recursive, optimizer_dict
from .utils import get_sample_generator, process_other_params, get_caller_file, rm_dir_full, get_submission_name
from .git_utils import ClusterSubmissionGitHook
from .job import Job
from .errors import OneTimeExceptionHandler
import time
import pandas as pd


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


global T
T = time.time()
delta_t = 60


def time_to_print():
  global T
  if time.time() - T > 60:
    T = time.time()
    return True
  return False


def pre_opt(base_paths_and_files, submission_requirements, optimized_params, number_of_samples, metric_to_optimize,
            minimize, optimizer_str, remove_jobs_dir, git_params, run_local, report_hooks, optimizer_settings,
            submission_name):
  delta_t = 60
  ensure_empty_dir(base_paths_and_files['result_dir'])
  ensure_empty_dir(base_paths_and_files['jobs_dir'])

  hp_optimizer = initialize_hp_optimizer(base_paths_and_files['result_dir'], optimizer_str, optimized_params,
                                         metric_to_optimize, minimize, report_hooks, number_of_samples,
                                         **optimizer_settings)

  cluster_type = get_cluster_type(requirements=submission_requirements, run_local=run_local)

  cluster_interface = cluster_type(paths=base_paths_and_files,
                                   requirements=submission_requirements,
                                   name=submission_name,
                                   remove_jobs_dir=remove_jobs_dir)
  cluster_interface.register_submission_hook(
    ClusterSubmissionGitHook(git_params, base_paths_and_files['script_to_run']))
  error_handler = OneTimeExceptionHandler(ignore_errors=True)
  return delta_t, hp_optimizer, cluster_interface, error_handler


def post_opt(cluster_interface, hp_optimizer, num_best_jobs_whose_data_is_kept, base_paths_and_files):
  pdf_output = os.path.join(base_paths_and_files['result_dir'], 'result.pdf')
  current_result_path = os.path.join(base_paths_and_files['result_dir'], cluster_interface.name)
  calling_script = get_caller_file(depth=2)
  submission_hook_stats = cluster_interface.collect_stats_from_hooks()

  #hp_optimizer.save_pdf_report(pdf_output, calling_script, submission_hook_stats, current_result_path)

  if num_best_jobs_whose_data_is_kept > 0:
    best_model_dirs = hp_optimizer.best_jobs_model_dirs(how_many=num_best_jobs_whose_data_is_kept)
    update_best_job_datadirs(base_paths_and_files['result_dir'], best_model_dirs)

  rm_dir_full(current_result_path)
  print('Intermediate results deleted...')
  cluster_interface.close()
  print('Procedure successfully finished')


def asynchronous_optimization(base_paths_and_files, submission_requirements, optimized_params, other_params,
                              number_of_samples, metric_to_optimize, minimize, optimizer_str='cem_metaoptimizer',
                              remove_jobs_dir=True, git_params=None, run_local=None, num_best_jobs_whose_data_is_kept=0,
                              report_hooks=None, optimizer_settings={}, min_n_jobs=5):
  base_paths_and_files['result_dir'] = os.path.join(base_paths_and_files['result_dir'], 'asynch_opt')
  # todo: check where other_params went
  delta_t, hp_optimizer, cluster_interface, error_handler = pre_opt(base_paths_and_files, submission_requirements,
                                                                    optimized_params,
                                                                    number_of_samples, metric_to_optimize,
                                                                    minimize, optimizer_str, remove_jobs_dir,
                                                                    git_params, run_local,
                                                                    report_hooks, optimizer_settings, 'asynch_opt')
  n_completed_jobs = 0

  while n_completed_jobs <= number_of_samples:
    n_queuing_or_running_jobs = cluster_interface.get_n_submitted_jobs() - cluster_interface.get_n_completed_jobs()
    completed_jobs = cluster_interface.get_completed_jobs()
    for completed_job in completed_jobs:
      if not completed_job.results_accessed:
        results = completed_job.get_results()
        if not results is None:
          df, params, metrics = results
          hp_optimizer.tell(df)
    while (n_queuing_or_running_jobs < min_n_jobs) or not cluster_interface.is_blocked():
      for new_settings in hp_optimizer.ask(1):
        new_job = Job(id_number=cluster_interface.inc_job_id, settings=new_settings, paths=base_paths_and_files)
        cluster_interface.add_jobs(new_job)
        cluster_interface.submit(new_job)
        time.sleep(0.1)
      n_queuing_or_running_jobs = cluster_interface.get_n_submitted_jobs() - cluster_interface.get_n_completed_jobs()
    n_queuing_or_running_jobs = cluster_interface.get_n_submitted_jobs() - cluster_interface.get_n_completed_jobs()
    n_completed_jobs = cluster_interface.get_n_completed_jobs()

    any_errors = cluster_interface.check_error_msgs()
    if any_errors:
      error_handler.maybe_raise('Some jobs had errors!')

    if time_to_print():
      print('Number of successfully ran jobs:', str(n_completed_jobs))
      all_results = [job.get_results()[0] for job in cluster_interface.get_completed_jobs() if
                     not job.get_results() is None]
      print('Finished with output:', str(len(all_results)))
      total_df = pd.concat(all_results, ignore_index=True)
      df = total_df.sort_values(metric_to_optimize)
      print(df[:min(10, df.shape[0])])
    time.sleep(1)

  post_opt(cluster_interface, hp_optimizer, num_best_jobs_whose_data_is_kept, base_paths_and_files)


def hyperparameter_optimization(base_paths_and_files, submission_requirements, optimized_params, other_params,
                                    number_of_samples, metric_to_optimize, minimize, total_rounds,
                                    fraction_that_need_to_finish,
                                    optimizer_str='cem_metaoptimizer', remove_jobs_dir=True, git_params=None,
                                    run_local=None, num_best_jobs_whose_data_is_kept=0, report_hooks=None,
                                    optimizer_settings={}):
  delta_t, hp_optimizer, cluster_interface = pre_opt(base_paths_and_files, submission_requirements, optimized_params,
                                                     number_of_samples, metric_to_optimize, minimize, optimizer_str,
                                                     remove_jobs_dir, git_params, run_local, report_hooks,
                                                     optimizer_settings, 'TODO')

  for i in range(total_rounds):
    submission_name = 'iteration_{}'.format(i + 1)
    base_paths_and_files['results_dir'] = os.path.join(base_paths_and_files['result_dir'], submission_name)
    print('Iteration {} started.'.format(hp_optimizer.iteration + 1))
    n_successful_jobs = 0
    settings = [setting for setting in hp_optimizer.ask(number_of_samples)]
    jobs = [Job(id_number=cluster_interface.inc_job_id, settings=setting, paths=base_paths_and_files)
            for setting in settings]

    cluster_interface.add_jobs(jobs)
    cluster_interface.submit_all()
    while n_successful_jobs / number_of_samples < fraction_that_need_to_finish:
      n_successful_jobs = cluster_interface.get_n_successful_jobs()
      if time_to_print():
        print('Number of successfully ran jobs:', str(n_successful_jobs))
      time.sleep(1)

    for completed_job in cluster_interface.get_completed_jobs():
      print('************************************************************************************************')
      hp_optimizer.tell(completed_job)
    cluster_interface.stop_all()

    # meta_opt.save_data_and_self(base_paths_and_files['result_dir'])
    #
    # meta_opt.save_pdf_report(pdf_output, calling_script, submission_hook_stats, current_result_path)
    # if num_best_jobs_whose_data_is_kept > 0:
    #  best_model_dirs = meta_opt.best_jobs_model_dirs(how_many=num_best_jobs_whose_data_is_kept)
    #  update_best_job_datadirs(base_paths_and_files['result_dir'], best_model_dirs)

    # rm_dir_full(current_result_path)

  post_opt(cluster_interface)
