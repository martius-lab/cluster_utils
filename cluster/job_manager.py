import os
import pickle
import shutil
from copy import deepcopy
from time import sleep

from . import utils, export
from .analyze_results import ClusterDataFrame
from .cluster import Condor_ClusterSubmission
from .constants import *
from .errors import OneTimeExceptionHandler
from .submission import SubmissionStatus


def rm_dir_full(dir_name):
  if os.path.exists(dir_name):
    shutil.rmtree(dir_name, ignore_errors=True)


def create_dir(dir_name):
  if not os.path.exists(dir_name):
    os.makedirs(dir_name)


def dict_to_dirname(setting, id, smart_naming=True):
  vals = ['{}={}'.format(str(key)[:3], str(value)[:6]) for key, value in setting.items() if not isinstance(value, dict)]
  res = '{}_{}'.format(id, '_'.join(vals))
  if len(res) < 35 and smart_naming:
    return res
  return str(id)


@export
def cluster_run(submission_name, paths, submission_requirements, other_params, hyperparam_dict=None,
                samples=None, distribution_list=None, restarts_per_setting=1,
                smart_naming=True):
  # Directories and filenames
  project_dir = paths['project_dir']
  script_to_run_name = paths['main_python_script']
  result_dir_abs = os.path.join(paths['result_dir'], submission_name)
  submission_dir_name_abs = os.path.join(paths['jobs_dir'], submission_name)

  rm_dir_full(result_dir_abs)
  rm_dir_full(submission_dir_name_abs)
  create_dir(submission_dir_name_abs)
  create_dir(result_dir_abs)

  if samples is not None:
    if hyperparam_dict is not None:
      setting_generator = utils.hyperparam_dict_samples(hyperparam_dict, samples)
    elif distribution_list is not None:
      setting_generator = utils.distribution_list_sampler(distribution_list, samples)
    else:
      raise ValueError('No hyperparameter dict/distribution list given')
  else:
    setting_generator = utils.hyperparam_dict_product(hyperparam_dict)

  def generate_commands():
    for setting in setting_generator:
      for iteration in range(restarts_per_setting):
        current_setting = deepcopy(setting)
        local_other_params = deepcopy(other_params)
        local_other_params['id'] = generate_commands.id_number
        job_res_dir = dict_to_dirname(current_setting, generate_commands.id_number, smart_naming)
        local_other_params['model_dir'] = os.path.join(result_dir_abs, job_res_dir)
        expected_len = len(current_setting) + len(local_other_params)

        current_setting.update(local_other_params)
        if len(current_setting) != expected_len:
          raise ValueError("Duplicate entries in hyperparam_dict and other_params!")
        base_cmd = 'python3 {} {}'
        cmd = base_cmd.format(script_to_run_name, '\"' + str(current_setting) + '\"')
        yield cmd
        generate_commands.id_number += 1

  generate_commands.id_number = 0

  submission = Condor_ClusterSubmission(job_commands=generate_commands(),
                                        submission_dir=submission_dir_name_abs,
                                        requirements=submission_requirements,
                                        name=submission_name,
                                        project_dir=project_dir)

  print('Jobs created:', generate_commands.id_number)
  return submission


@export
def hyperparameter_optimization(base_paths_and_files, submission_requirements, distribution_list, other_params,
                                number_of_samples, number_of_restarts, total_rounds, percentage_that_need_to_finish,
                                percentage_of_best, metric_to_optimize, check_every_secs, ignore_errors=True):
  def produce_cluster_run_all_args(distributions, iteration):
    return dict(submission_name='iteration_{}'.format(iteration + 1),
                paths=base_paths_and_files,
                submission_requirements=submission_requirements,
                distribution_list=distributions,
                other_params=other_params,
                samples=number_of_samples,
                restarts_per_setting=number_of_restarts,
                smart_naming=False)

  cdf = None
  all_params = [distr.param_name for distr in distribution_list]
  num_jobs = number_of_samples * number_of_restarts

  error_handler = OneTimeExceptionHandler(ignore_errors=ignore_errors)
  submission_status = SubmissionStatus(total_jobs=num_jobs, fraction_to_finish=percentage_that_need_to_finish,
                                       fraction_of_best=percentage_of_best)

  for i in range(total_rounds):
    # Reset all seen exceptions and messgaes
    error_handler.clear()

    all_args = produce_cluster_run_all_args(distribution_list, i)
    submission = cluster_run(**all_args)
    current_result_path = os.path.join(base_paths_and_files['result_dir'], all_args['submission_name'])

    if i > 0:
      print('Last best results:')
      best_df = cdf.best_jobs(metric_to_optimize, 10)[all_params + [metric_to_optimize]]
      print(best_df)

    print('Submitting jobs (iteration {})...'.format(i + 1))
    with submission:
      while True:
        sleep(check_every_secs)
        cdf = ClusterDataFrame(current_result_path, CLUSTER_PARAM_FILE, CLUSTER_METRIC_FILE)
        completed_succesfully = len(cdf.df)

        any_errors = submission.check_error_msgs()
        if any_errors:
          error_handler.maybe_raise('Some jobs had errors!')
        status = submission.get_status()
        submission_status.update(completed_succesfully, status)
        submission_status.do_checks(error_handler)

        if submission_status.finished:
          print('Iteration {} finished ({}/{})'.format(i + 1, submission_status.completed, submission_status.total))
          break

        print(submission_status)

    cdf.set_id_columns(['id', 'model_dir'])
    best_params = cdf.best_params(metric_to_optimize, how_many=int(percentage_of_best * number_of_samples))
    cdf.df.to_csv(os.path.join(base_paths_and_files['result_dir'],
                               'df_from_iter{}.csv'.format(i + 1)))

    best_df = cdf.best_jobs(metric_to_optimize, 10)[all_params + [metric_to_optimize]]

    best_df.to_csv(os.path.join(base_paths_and_files['result_dir'],
                                'best_from_iter{}.csv'.format(i + 1)))

    for distr in distribution_list:
      distr.fit(best_params[distr.param_name])

    with open(os.path.join(base_paths_and_files['result_dir'],
                           'distr_from_iter{}.csv'.format(i + 1)), 'wb') as f:
      pickle.dump(distribution_list, f)
    print('Distributions updated...')
    rm_dir_full(current_result_path)
    print('Intermediate results deleted...')

  print('Procedure finished')
