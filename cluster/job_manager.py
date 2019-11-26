import numpy as np
import os
import shutil
from copy import deepcopy

from .cluster_system import get_cluster_type
from .constants import *
from .settings import update_recursive, optimizer_dict
from .utils import get_sample_generator, process_other_params, get_caller_file, rm_dir_full, get_submission_name
from .optimizers import Optimizer
from .git_utils import ClusterSubmissionGitHook
from .job import Job
from .errors import OneTimeExceptionHandler
import time
import pandas as pd
import signal
import sys
from warnings import warn
from .communication_server import CommunicationServer
import threading


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
  vals = ['{}={}'.format(str(key)[:3], str(value)[:6]) for key, value in setting.items() if
          not isinstance(value, dict)]
  res = '{}_{}'.format(id, '_'.join(vals))
  if len(res) < 35 and smart_naming:
    return res
  return str(id)

'''
<<<<<<< HEAD
=======
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


>>>>>>> origin/executable_submodules
'''
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
  hp_optimizer = optimizer_dict[optimizer_str].try_load_from_pickle(possible_pickle, optimized_params,
                                                                    metric_to_optimize,
                                                                    minimize, report_hooks, **optimizer_settings)
  if hp_optimizer is None:
    hp_optimizer = optimizer_dict[optimizer_str](optimized_params=optimized_params,
                                                 metric_to_optimize=metric_to_optimize,
                                                 minimize=minimize, number_of_samples=number_of_samples,
                                                 report_hooks=report_hooks,
                                                 iteration_mode=True, **optimizer_settings)
  print('Last iteration: ', hp_optimizer.iteration)
  return hp_optimizer


global T
T = time.time()
delta_t = 3


def time_to_print():
  global T
  if time.time() - T > delta_t:
    T = time.time()
    return True
  return False


def pre_opt(base_paths_and_files, submission_requirements, optimized_params, other_params, number_of_samples,
            metric_to_optimize, minimize, optimizer_str, remove_jobs_dir, git_params, run_local, report_hooks,
            optimizer_settings, submission_name):
  processed_other_params = process_other_params(other_params, None, optimized_params)

  hp_optimizer = initialize_hp_optimizer(base_paths_and_files['result_dir'], optimizer_str, optimized_params,
                                         metric_to_optimize, minimize, report_hooks, number_of_samples,
                                         **optimizer_settings)

  cluster_type = get_cluster_type(requirements=submission_requirements, run_local=run_local)

  cluster_interface = cluster_type(paths=base_paths_and_files,
                                   requirements=submission_requirements,
                                   name=submission_name,
                                   remove_jobs_dir=remove_jobs_dir)
  cluster_interface.register_submission_hook(
    ClusterSubmissionGitHook(git_params, base_paths_and_files))
  cluster_interface.exec_pre_run_routines()
  error_handler = OneTimeExceptionHandler(ignore_errors=True)
  comm_server = CommunicationServer(cluster_interface)

  def signal_handler(sig, frame):
    cluster_interface.close()
    print('Exiting now')
    sys.exit(0)

  signal.signal(signal.SIGINT, signal_handler)

#<<<<<<< HEAD
  return hp_optimizer, cluster_interface, comm_server, error_handler, processed_other_params
#=======
#    meta_opt.process_new_df(df)
#    meta_opt.save_data_and_self(base_paths_and_files['result_dir'])
#    opt_procedure_name = os.path.dirname(os.path.join(base_paths_and_files['result_dir'], 'dummy.tmp'))
#    pdf_output = os.path.join(base_paths_and_files['result_dir'], f'{opt_procedure_name}.pdf')
#>>>>>>> origin/executable_submodules


def post_opt(cluster_interface, hp_optimizer):
  cluster_interface.exec_post_run_routines()
  cluster_interface.close()
  print('Procedure successfully finished')


def pre_iteration_opt(base_paths_and_files):
  print('ensuring empty dir: ', base_paths_and_files['current_result_dir'])
  ensure_empty_dir(base_paths_and_files['current_result_dir'])
  # TODO: Check if this is necessary, somehow cant delete cache dirs ensure_empty_dir(base_paths_and_files['jobs_dir'])


def post_iteration_opt(cluster_interface, hp_optimizer, comm_server, base_paths_and_files, metric_to_optimize,
                       num_best_jobs_whose_data_is_kept):
  pdf_output = os.path.join(base_paths_and_files['result_dir'], 'result.pdf')
  current_result_path = os.path.join(base_paths_and_files['result_dir'], cluster_interface.name)
  calling_script = get_caller_file(depth=3)

  submission_hook_stats = cluster_interface.collect_stats_from_hooks()

  hp_optimizer.tell([job for job in cluster_interface.successful_jobs if not job.results_accessed])

  hp_optimizer.save_pdf_report(pdf_output, calling_script, submission_hook_stats, current_result_path)

  hp_optimizer.iteration += 1

  print(hp_optimizer.full_df[:10])

  hp_optimizer.save_data_and_self(base_paths_and_files['result_dir'])

  comm_server.jobs = []

  if hp_optimizer.iteration_mode:
    cluster_interface.stop_all()

  if num_best_jobs_whose_data_is_kept > 0:
    best_model_dirs = hp_optimizer.best_jobs_model_dirs(how_many=num_best_jobs_whose_data_is_kept)
    update_best_job_datadirs(base_paths_and_files['result_dir'], best_model_dirs)

  rm_dir_full(current_result_path)
  print('Intermediate results deleted...')


def asynchronous_optimization(base_paths_and_files, submission_requirements, optimized_params, other_params,
                              number_of_samples, metric_to_optimize, minimize, optimizer_str='cem_metaoptimizer',
                              remove_jobs_dir=True, git_params=None, run_local=None, num_best_jobs_whose_data_is_kept=0,
                              report_hooks=None, optimizer_settings={}, min_n_jobs=5):
  base_paths_and_files['result_dir'] = os.path.join(base_paths_and_files['result_dir'], 'asynch_opt')
  base_paths_and_files['current_result_dir'] = base_paths_and_files['result_dir']

  # todo: check where other_params went
  hp_optimizer, cluster_interface, error_handler, processed_other_params = pre_opt(base_paths_and_files,
                                                                                   submission_requirements,
                                                                                   optimized_params, other_params,
                                                                                   number_of_samples,
                                                                                   metric_to_optimize,
                                                                                   minimize, optimizer_str,
                                                                                   remove_jobs_dir,
                                                                                   git_params, run_local,
                                                                                   report_hooks, optimizer_settings,
                                                                                   'asynch_opt')
  hp_optimizer.iteration_mode = False
  cluster_interface.iteration_mode = False
  n_successful_jobs = 0

  iteration_offset = hp_optimizer.iteration

  while n_successful_jobs <= number_of_samples:
    successful_jobs = cluster_interface.successful_jobs
    hp_optimizer.tell([job for job in successful_jobs if not job.results_accessed])

    n_queuing_or_running_jobs = cluster_interface.n_submitted_jobs - cluster_interface.n_completed_jobs
    while (n_queuing_or_running_jobs < min_n_jobs):  # or not cluster_interface.is_blocked():
      for new_candidate, new_settings in hp_optimizer.ask(1):
        new_job = Job(id=cluster_interface.inc_job_id, candidate=new_candidate, settings=new_settings,
                      other_params=processed_other_params, paths=base_paths_and_files,
                      iteration=hp_optimizer.iteration + 1)
        cluster_interface.add_jobs(new_job)
        cluster_interface.submit(new_job)
      n_queuing_or_running_jobs = cluster_interface.n_idle_jobs + cluster_interface.n_running_jobs
      n_successful_jobs = cluster_interface.n_successful_jobs
      if n_successful_jobs // optimizer_settings['n_jobs_per_iteration'] + iteration_offset > hp_optimizer.iteration:
        break
    # n_queuing_or_running_jobs = cluster_interface.n_idle_jobs + cluster_interface.n_running_jobs
    if n_successful_jobs // optimizer_settings['n_jobs_per_iteration'] + iteration_offset > hp_optimizer.iteration:
      post_iteration_opt(cluster_interface, hp_optimizer, base_paths_and_files, metric_to_optimize,
                         num_best_jobs_whose_data_is_kept)
      # TODO: After new iteration started, remove old dirs
      hp_optimizer.iteration = n_successful_jobs // optimizer_settings['n_jobs_per_iteration'] + iteration_offset
      print('starting new iteration:', hp_optimizer.iteration)

    any_errors = cluster_interface.check_error_msgs()
    if any_errors:
      error_handler.maybe_raise('Some jobs had errors!')

    if time_to_print():
      print(cluster_interface)
    time.sleep(1)

  post_opt(cluster_interface, hp_optimizer)


def hyperparameter_optimization(base_paths_and_files, submission_requirements, optimized_params, other_params,
                                number_of_samples, metric_to_optimize, minimize, total_rounds,
                                fraction_that_need_to_finish,
                                optimizer_str='cem_metaoptimizer', remove_jobs_dir=True, git_params=None,
                                run_local=None, num_best_jobs_whose_data_is_kept=0, report_hooks=None,
                                optimizer_settings={}):
  submission_name = 'iteration_{}'.format(1)
  hp_optimizer, cluster_interface, comm_server, error_handler, processed_other_params = pre_opt(base_paths_and_files,
                                                                                                submission_requirements,
                                                                                                optimized_params,
                                                                                                other_params,
                                                                                                number_of_samples,
                                                                                                metric_to_optimize,
                                                                                                minimize,
                                                                                                optimizer_str,
                                                                                                remove_jobs_dir,
                                                                                                git_params,
                                                                                                run_local,
                                                                                                report_hooks,
                                                                                                optimizer_settings,
                                                                                                submission_name)
  for i in range(total_rounds):
    time_when_severe_warning_happened = None
    submission_name = 'iteration_{}'.format(hp_optimizer.iteration + 1)
    cluster_interface.name = submission_name
    base_paths_and_files['current_result_dir'] = os.path.join(base_paths_and_files['result_dir'], submission_name)
    pre_iteration_opt(base_paths_and_files)
    print('Iteration {} started.'.format(hp_optimizer.iteration + 1))
    n_confirmed_successful_jobs = 0
    settings = [(candidate, setting) for candidate, setting in hp_optimizer.ask(number_of_samples)]
    jobs = [Job(id=cluster_interface.inc_job_id, candidate=candidate, settings=setting,
                other_params=processed_other_params, paths=base_paths_and_files, iteration=hp_optimizer.iteration + 1,
                connection_info=comm_server.connection_info)
            for candidate, setting in settings]

    cluster_interface.add_jobs(jobs)
    cluster_interface.submit_all()
    while n_confirmed_successful_jobs / number_of_samples < fraction_that_need_to_finish:
      n_confirmed_successful_jobs = cluster_interface.n_successful_jobs
      n_ran_jobs = cluster_interface.n_completed_jobs
      if (n_ran_jobs - n_confirmed_successful_jobs) > number_of_samples * fraction_that_need_to_finish:
        if not time_when_severe_warning_happened is None and time.time() - time_when_severe_warning_happened > 5:
          raise ValueError('Less then fraction_that_need_to_finish jobs can be successful')
        else:
          if time_when_severe_warning_happened is None:
            time_when_severe_warning_happened = time.time()
            warn('Less then fraction_that_need_to_finish jobs can be successful \n if this repeats in 5 seconds it will'
                 'cause an collapse of the procedure.')
      if time_to_print():
        print(cluster_interface)
    post_iteration_opt(cluster_interface, hp_optimizer, comm_server, base_paths_and_files, metric_to_optimize,
                       num_best_jobs_whose_data_is_kept)
  post_opt(cluster_interface, hp_optimizer)


  #cluster = ClusterInterface()
  #job = Job(, comm_server.connection_info)
  #cluster.submit_job(job)
