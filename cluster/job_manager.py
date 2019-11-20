import numpy as np
import os
import shutil
from copy import deepcopy

from .analyze_results import Metaoptimizer
from .cluster_system import get_cluster_type
from .constants import *
from .settings import update_recursive
from .submission import execute_submission
from .utils import get_sample_generator, process_other_params, get_caller_file, rm_dir_full
from .git_utils import ClusterSubmissionGitHook
from .dummy_cluster_system import Dummy_ClusterSubmission
from warnings import warn

def ensure_empty_dir(dir_name, defensive=False):
  if os.path.exists(dir_name):
    if defensive:
        print(f"Directory {dir_name} exists. Delete everything? (y/N)")
        ans = input()
        if ans.lower() == 'y':
            shutil.rmtree(dir_name, ignore_errors=True)
            os.makedirs(dir_name)
    else:
        shutil.rmtree(dir_name, ignore_errors=True)
        os.makedirs(dir_name)
  else:
      os.makedirs(dir_name)


def dict_to_dirname(setting, id, smart_naming=True):
  vals = ['{}={}'.format(str(key)[:3], str(value)[:6]) for key, value in setting.items() if not isinstance(value, dict)]
  res = '{}_{}'.format(id, '_'.join(vals))
  if len(res) < 35 and smart_naming:
    return res
  return str(id)


def cluster_run(submission_name, paths, submission_requirements, other_params, hyperparam_dict=None,
                samples=None, distribution_list=None, restarts_per_setting=1,
                smart_naming=True, remove_jobs_dir=True, git_params=None, run_local=None, extra_settings=None):
  # Directories and filenames
  ensure_empty_dir(paths['result_dir'], defensive=True)
  ensure_empty_dir(paths['jobs_dir'])

  setting_generator = get_sample_generator(samples, hyperparam_dict, distribution_list, extra_settings)
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
        if 'virtual_env_path' in paths:
            virtual_env_activate = 'source {}'.format(os.path.join(paths['virtual_env_path'], 'bin/activate'))
        else:
            virtual_env_activate = ''

        if 'custom_pythonpaths' in paths:
            raise NotImplementedError('Setting custom pythonpath was deprecated. Set \"virtual_env_path\" instead.')

        if 'custom_python_executable_path' in paths:
            warn('Setting custom_python_executable_path not recommended. Better set \"virtual_env_path\" instead.')

        python_executor = paths.get('custom_python_executable_path', 'python3')
        is_python_script = paths.get('is_python_script', True)

        if is_python_script:
            run_script_as_module_main = paths.get('run_script_as_module_main', False)
            setting_string = '\"' + str(current_setting) + '\"'
            if run_script_as_module_main:
                exec_cmd = f"{python_executor} -m {os.path.basename(paths['script_to_run'])} {setting_string}"
            else:
                base_exec_cmd = '{}'.format(python_executor) + ' {} {}'
                exec_cmd = base_exec_cmd.format(paths['script_to_run'], setting_string)
        else:
          base_exec_cmd = '{} {}'
          exec_cmd = base_exec_cmd.format(paths['script_to_run'], '\"' + str(current_setting) + '\"')

        yield '\n'.join([setting_cwd, virtual_env_activate, exec_cmd])
        generate_commands.id_number += 1

  generate_commands.id_number = 0

  cluster_type = get_cluster_type(requirements=submission_requirements, run_local=run_local)
  if cluster_type is None:
      raise OSError('Neither CONDOR nor SLURM was found. Not running locally')
  submission = cluster_type(job_commands=generate_commands(),
                                        submission_dir=paths['jobs_dir'],
                                        requirements=submission_requirements,
                                        name=submission_name,
                                        remove_jobs_dir=remove_jobs_dir)

  submission.register_submission_hook(ClusterSubmissionGitHook(git_params, paths))

  print('Jobs created:', generate_commands.id_number)
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


def hyperparameter_optimization(base_paths_and_files, submission_requirements, distribution_list, other_params,
                                number_of_samples, with_restarts, total_rounds, fraction_that_need_to_finish,
                                best_fraction_to_use_for_update, metric_to_optimize, minimize, remove_jobs_dir=True,
                                git_params=None, run_local=None, num_best_jobs_whose_data_is_kept=0, report_hooks=None):
  def produce_cluster_run_all_args(distributions, iteration, num_samples, extra_settings):
    submission_name = 'iteration_{}'.format(iteration + 1)
    new_paths = {key: value for key, value in base_paths_and_files.items()}
    new_paths['result_dir'] = os.path.join(new_paths['result_dir'], submission_name)

    return dict(submission_name=submission_name,
                paths=new_paths,
                submission_requirements=submission_requirements,
                distribution_list=distributions,
                other_params=other_params,
                restarts_per_setting=1,
                smart_naming=False,
                remove_jobs_dir=remove_jobs_dir,
                git_params=git_params,
                run_local=run_local,
                samples=num_samples,
                extra_settings=extra_settings)

  calling_script = get_caller_file(depth=2)

  best_jobs_to_take = int(number_of_samples * best_fraction_to_use_for_update)
  if best_jobs_to_take < 2:
    warn('Less than 2 jobs would be taken for distribution update. '
         'Resorting to taking exactly 2 best jobs. '
         'Perhaps choose higher \'best_fraction_to_use_for_update\' ')
    best_jobs_to_take = 2
    best_fraction_to_use_for_update = best_jobs_to_take / number_of_samples


  possible_pickle = os.path.join(base_paths_and_files['result_dir'], STATUS_PICKLE_FILE)
  meta_opt = Metaoptimizer.try_load_from_pickle(possible_pickle, distribution_list, metric_to_optimize,
                                                best_jobs_to_take, minimize, with_restarts, report_hooks)
  if meta_opt is None:
    meta_opt = Metaoptimizer(distribution_list, metric_to_optimize, best_jobs_to_take, minimize,
                             with_restarts, report_hooks)

  if git_params and 'url' in git_params:
      git_params['remove_local_copy'] = True  # always remove git repo copy in case of hyperparameter optimization

  for i in range(total_rounds):
    print('Iteration {} started.'.format(meta_opt.iteration + 1))

    extra_settings = meta_opt.settings_to_restart
    num_samples = number_of_samples if extra_settings is None else number_of_samples - best_jobs_to_take
    all_args = produce_cluster_run_all_args(distribution_list, meta_opt.iteration, num_samples, extra_settings)
    submission = cluster_run(**all_args, )

    run_local = isinstance(submission, Dummy_ClusterSubmission)

    current_result_path = os.path.join(base_paths_and_files['result_dir'], all_args['submission_name'])

    print(meta_opt.get_best())

    df, params, metrics, submission_hook_stats = execute_submission(submission, current_result_path,
                                             fraction_need_to_finish=fraction_that_need_to_finish,
                                             min_fraction_to_finish=best_fraction_to_use_for_update,
                                             ignore_errors=True)
    if metric_to_optimize not in metrics:
      raise ValueError('Optimized metric \'{}\' not found in output'.format(metric_to_optimize))
    if not np.issubdtype(df[metric_to_optimize].dtype, np.number):
      raise ValueError('Optimized metric \'{}\' is not a numerical type'.format(metric_to_optimize))

    meta_opt.process_new_df(df)
    meta_opt.save_data_and_self(base_paths_and_files['result_dir'])
    opt_procedure_name = os.path.dirname(os.path.join(base_paths_and_files['result_dir'], 'dummy.tmp'))
    pdf_output = os.path.join(base_paths_and_files['result_dir'], f'{opt_procedure_name}.pdf')

    meta_opt.save_pdf_report(pdf_output, calling_script, submission_hook_stats, current_result_path)

    if num_best_jobs_whose_data_is_kept > 0:
        best_model_dirs = meta_opt.best_jobs_model_dirs(how_many=num_best_jobs_whose_data_is_kept)
        update_best_job_datadirs(base_paths_and_files['result_dir'], best_model_dirs)

    rm_dir_full(current_result_path)
    print('Intermediate results deleted...')

  print('Procedure successfully finished')
