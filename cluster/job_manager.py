import os
import shutil
from copy import deepcopy

from .analyze_results import Metaoptimizer
from .cluster import Slurm_ClusterSubmission as ClusterSubmission
from .constants import *
from .settings import update_recursive
from .submission import execute_submission
from .utils import get_sample_generator, process_other_params, get_caller_file


def ensure_empty_dir(dir_name):
  if os.path.exists(dir_name):
    shutil.rmtree(dir_name, ignore_errors=True)
  os.makedirs(dir_name)


def rm_dir_full(dir_name):
  if os.path.exists(dir_name):
    shutil.rmtree(dir_name, ignore_errors=True)


def dict_to_dirname(setting, id, smart_naming=True):
  vals = ['{}={}'.format(str(key)[:3], str(value)[:6]) for key, value in setting.items() if not isinstance(value, dict)]
  res = '{}_{}'.format(id, '_'.join(vals))
  if len(res) < 35 and smart_naming:
    return res
  return str(id)


def cluster_run(submission_name, paths, submission_requirements, other_params, hyperparam_dict=None,
                samples=None, distribution_list=None, restarts_per_setting=1,
                smart_naming=True):
  # Directories and filenames
  ensure_empty_dir(paths['result_dir'])
  ensure_empty_dir(paths['jobs_dir'])

  setting_generator = get_sample_generator(samples, hyperparam_dict, distribution_list)
  processed_other_params = process_other_params(other_params, hyperparam_dict, distribution_list)

  def generate_commands():
    for setting in setting_generator:
      for iteration in range(restarts_per_setting):
        current_setting = deepcopy(setting)
        local_other_params = deepcopy(processed_other_params)

        local_other_params['id'] = generate_commands.id_number
        job_res_dir = dict_to_dirname(current_setting, generate_commands.id_number, smart_naming)
        local_other_params['model_dir'] = os.path.join(paths['result_dir'], job_res_dir)

        update_recursive(current_setting, local_other_params)
        setting_cwd = 'cd {}'.format(os.path.dirname(paths['script_to_run']))
        setting_pythonpath = 'export PYTHONPATH={}:$PYTHONPATH'.format(os.path.dirname(paths['script_to_run']))
        base_exec_cmd = 'python3 {} {}'
        exec_cmd = base_exec_cmd.format(paths['script_to_run'], '\"' + str(current_setting) + '\"')
        yield '\n'.join([setting_cwd, setting_pythonpath, exec_cmd])
        generate_commands.id_number += 1

  generate_commands.id_number = 0

  submission = ClusterSubmission(job_commands=generate_commands(),
                                        submission_dir=paths['jobs_dir'],
                                        requirements=submission_requirements,
                                        name=submission_name)

  print('Jobs created:', generate_commands.id_number)
  return submission


def hyperparameter_optimization(base_paths_and_files, submission_requirements, distribution_list, other_params,
                                number_of_samples, number_of_restarts, total_rounds, fraction_that_need_to_finish,
                                best_fraction_to_use_for_update, metric_to_optimize, minimize):
  def produce_cluster_run_all_args(distributions, iteration):
    submission_name = 'iteration_{}'.format(iteration + 1)
    return dict(submission_name=submission_name,
                paths={'script_to_run': base_paths_and_files['script_to_run'],
                       'result_dir': os.path.join(base_paths_and_files['result_dir'], submission_name),
                       'jobs_dir': os.path.join(base_paths_and_files['jobs_dir'], submission_name)},
                submission_requirements=submission_requirements,
                distribution_list=distributions,
                other_params=other_params,
                samples=number_of_samples,
                restarts_per_setting=number_of_restarts,
                smart_naming=False)

  calling_script = get_caller_file(depth=2)
  print(calling_script)

  best_jobs_to_take = int(number_of_samples * best_fraction_to_use_for_update)

  possible_pickle = os.path.join(base_paths_and_files['result_dir'], STATUS_PICKLE_FILE)
  meta_opt = Metaoptimizer.try_load_from_pickle(possible_pickle, distribution_list, metric_to_optimize,
                                                best_jobs_to_take, minimize)
  if meta_opt is None:
    meta_opt = Metaoptimizer(distribution_list, metric_to_optimize, best_jobs_to_take, minimize)

  for i in range(total_rounds):
    print('Iteration {} started.'.format(meta_opt.iteration + 1))
    all_args = produce_cluster_run_all_args(distribution_list, meta_opt.iteration)
    submission = cluster_run(**all_args)
    current_result_path = os.path.join(base_paths_and_files['result_dir'], all_args['submission_name'])

    print(meta_opt.get_best())

    df, params, metrics = execute_submission(submission, current_result_path,
                                             fraction_need_to_finish=fraction_that_need_to_finish,
                                             min_fraction_to_finish=best_fraction_to_use_for_update,
                                             ignore_errors=True)
    meta_opt.process_new_df(df)
    df.to_csv(os.path.join(base_paths_and_files['result_dir'],
                           'full_df_iter_{}.csv'.format(meta_opt.iteration + 1)))
    meta_opt.save_data_and_self(base_paths_and_files['result_dir'])
    pdf_output = os.path.join(base_paths_and_files['result_dir'], 'result.pdf')
    meta_opt.save_pdf_report(pdf_output, calling_script)
    rm_dir_full(current_result_path)
    print('Intermediate results deleted...')

  print('Procedure successfully finished')
