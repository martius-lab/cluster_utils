import os
import shutil

from cluster.progress_bars import redirect_stdout_to_tqdm, SubmittedJobsBar, RunningJobsBar, CompletedJobsBar
from .cluster_system import get_cluster_type
from .constants import *
from .settings import optimizer_dict
from .utils import process_other_params, get_caller_file, rm_dir_full, make_red
from .git_utils import ClusterSubmissionGitHook
from .job import Job, JobStatus
from .errors import OneTimeExceptionHandler
import time
import pandas as pd
import signal
import sys
from warnings import warn
from .communication_server import CommunicationServer

def ensure_empty_dir(dir_name, defensive=False):
  if os.path.exists(dir_name):
    if defensive:
      print(make_red(f"Directory {dir_name} exists. Delete everything? (y/N)"))
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


def update_best_job_datadirs(result_dir, model_dirs):
  datadir = os.path.join(result_dir, 'best_jobs')
  os.makedirs(datadir, exist_ok=True)

  short_names = [model_dir.split('_')[-1].replace('/', '_') for model_dir in model_dirs]

  # Copy over new best directories
  for model_dir in model_dirs:
    if os.path.exists(model_dir):
      new_dir_name = model_dir.split('_')[-1].replace('/', '_')
      new_dir_full = os.path.join(datadir, new_dir_name)
      if not os.path.exists((new_dir_full)):
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
                                                 **optimizer_settings)
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
            optimizer_settings):
  processed_other_params = process_other_params(other_params, None, optimized_params)
  ensure_empty_dir(base_paths_and_files['result_dir'], defensive=True)
  os.makedirs(base_paths_and_files['current_result_dir'])


  hp_optimizer = initialize_hp_optimizer(base_paths_and_files['result_dir'], optimizer_str, optimized_params,
                                         metric_to_optimize, minimize, report_hooks, number_of_samples,
                                         **optimizer_settings)

  cluster_type = get_cluster_type(requirements=submission_requirements, run_local=run_local)

  cluster_interface = cluster_type(paths=base_paths_and_files,
                                   requirements=submission_requirements,
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

  return hp_optimizer, cluster_interface, comm_server, error_handler, processed_other_params

def post_opt(cluster_interface):
  cluster_interface.exec_post_run_routines()
  cluster_interface.close()
  print('Procedure successfully finished')


def pre_iteration_opt(base_paths_and_files):
  pass

def post_iteration_opt(cluster_interface, hp_optimizer, comm_server, base_paths_and_files, metric_to_optimize,
                       num_best_jobs_whose_data_is_kept):
  pdf_output = os.path.join(base_paths_and_files['result_dir'], 'result.pdf')
  current_result_path = base_paths_and_files['current_result_dir']

  submission_hook_stats = cluster_interface.collect_stats_from_hooks()

  jobs_to_tell = [job for job in cluster_interface.successful_jobs if not job.results_used_for_update]
  hp_optimizer.tell(jobs_to_tell)

  print(hp_optimizer.full_df[:10])

  hp_optimizer.save_pdf_report(pdf_output, submission_hook_stats, current_result_path)

  hp_optimizer.iteration += 1


  hp_optimizer.save_data_and_self(base_paths_and_files['result_dir'])

  comm_server.jobs = []

  if hp_optimizer.iteration_mode:
    cluster_interface.stop_all()

  if num_best_jobs_whose_data_is_kept > 0:
    best_model_dirs = hp_optimizer.best_jobs_model_dirs(how_many=num_best_jobs_whose_data_is_kept)
    update_best_job_datadirs(base_paths_and_files['result_dir'], best_model_dirs)

  finished_model_dirs = hp_optimizer.full_df['model_dir']
  for model_dir in finished_model_dirs:
      rm_dir_full(model_dir)

  #rm_dir_full(current_result_path)
  #print('Intermediate results deleted...')


def asynchronous_optimization(base_paths_and_files, submission_requirements, optimized_params, other_params,
                              number_of_samples, metric_to_optimize, minimize, n_jobs_per_iteration,
                              optimizer_str='cem_metaoptimizer',
                              remove_jobs_dir=True, git_params=None, run_local=None, num_best_jobs_whose_data_is_kept=0,
                              report_hooks=None, optimizer_settings=None):

  optimizer_settings = optimizer_settings or {}
  base_paths_and_files['current_result_dir'] = os.path.join(base_paths_and_files['result_dir'], 'working_directories')

  hp_optimizer, cluster_interface, comm_server, error_handler, processed_other_params = pre_opt(base_paths_and_files,
                                                                                                submission_requirements,
                                                                                                optimized_params,
                                                                                                other_params,
                                                                                                number_of_samples,
                                                                                                metric_to_optimize,
                                                                                                minimize, optimizer_str,
                                                                                                remove_jobs_dir,
                                                                                                git_params, run_local,
                                                                                                report_hooks,
                                                                                                optimizer_settings)
  hp_optimizer.iteration_mode = False
  cluster_interface.iteration_mode = False
  iteration_offset = hp_optimizer.iteration
  pre_iteration_opt(base_paths_and_files)

  with redirect_stdout_to_tqdm():
      submitted_bar = SubmittedJobsBar(total_jobs=number_of_samples)
      running_bar = RunningJobsBar(total_jobs=number_of_samples)
      successful_jobs_bar = CompletedJobsBar(total_jobs=number_of_samples, minimize=minimize)

      while cluster_interface.n_completed_jobs < number_of_samples:
        time.sleep(0.2)
        jobs_to_tell = [job for job in cluster_interface.successful_jobs if not job.results_used_for_update]
        hp_optimizer.tell(jobs_to_tell)
        n_queuing_or_running_jobs = cluster_interface.n_submitted_jobs - cluster_interface.n_completed_jobs
        if n_queuing_or_running_jobs < n_jobs_per_iteration and cluster_interface.n_submitted_jobs < number_of_samples:
          new_candidate, new_settings = next(hp_optimizer.ask(1))
          new_job = Job(id=cluster_interface.inc_job_id, candidate=new_candidate, settings=new_settings,
                        other_params=processed_other_params, paths=base_paths_and_files,
                        iteration=hp_optimizer.iteration + 1, connection_info=comm_server.connection_info)
          cluster_interface.add_jobs(new_job)
          cluster_interface.submit(new_job)
        if cluster_interface.n_completed_jobs // n_jobs_per_iteration > hp_optimizer.iteration - iteration_offset:
          post_iteration_opt(cluster_interface, hp_optimizer, comm_server, base_paths_and_files, metric_to_optimize,
                             num_best_jobs_whose_data_is_kept)
          print('starting new iteration:', hp_optimizer.iteration)
          pre_iteration_opt(base_paths_and_files)

        for job in cluster_interface.submitted_jobs:
            if job.status == JobStatus.SUBMITTED or job.waiting_for_resume:
                job.check_filesystem_for_errors()
        cluster_interface.check_error_msgs()


        if cluster_interface.n_failed_jobs > cluster_interface.n_successful_jobs + cluster_interface.n_running_jobs + 5:
            cluster_interface.close()
            raise RuntimeError(f"Too many ({cluster_interface.n_failed_jobs}) jobs failed. Ending procedure.")

        submitted_bar.update(cluster_interface.n_submitted_jobs)
        running_bar.update_failed_jobs(cluster_interface.n_failed_jobs)
        running_bar.update(cluster_interface.n_running_jobs+cluster_interface.n_completed_jobs)
        successful_jobs_bar.update(cluster_interface.n_successful_jobs)
        successful_jobs_bar.update_median_time_left(cluster_interface.median_time_left)

        if len(hp_optimizer.full_df) > 0:
            best_value = hp_optimizer.full_df[hp_optimizer.metric_to_optimize].iloc[0]
            successful_jobs_bar.update_best_val(best_value)

  post_iteration_opt(cluster_interface, hp_optimizer, comm_server, base_paths_and_files, metric_to_optimize,
                     num_best_jobs_whose_data_is_kept)
  post_opt(cluster_interface)
  rm_dir_full(base_paths_and_files['current_result_dir'])


def grid_search(base_paths_and_files, submission_requirements, optimized_params, other_params,
                restarts, remove_jobs_dir=True, git_params=None, run_local=None, report_hooks=None):

  base_paths_and_files['current_result_dir'] = os.path.join(base_paths_and_files['result_dir'], 'working_directories')
  hp_optimizer, cluster_interface, comm_server, error_handler, processed_other_params = pre_opt(base_paths_and_files,
                                                                                                submission_requirements,
                                                                                                optimized_params,
                                                                                                other_params,
                                                                                                None,
                                                                                                None,
                                                                                                False,
                                                                                                'gridsearch',
                                                                                                remove_jobs_dir,
                                                                                                git_params,
                                                                                                run_local,
                                                                                                report_hooks,
                                                                                                dict(restarts=restarts))

  pre_iteration_opt(base_paths_and_files)

  settings = [(candidate, setting) for candidate, setting in hp_optimizer.ask_all()]
  jobs = [Job(id=cluster_interface.inc_job_id, candidate=candidate, settings=setting,
              other_params=processed_other_params, paths=base_paths_and_files, iteration=hp_optimizer.iteration,
              connection_info=comm_server.connection_info)
          for candidate, setting in settings]
  cluster_interface.add_jobs(jobs)

  with redirect_stdout_to_tqdm():
      submitted_bar = SubmittedJobsBar(total_jobs=len(jobs))
      running_bar = RunningJobsBar(total_jobs=len(jobs))
      successful_jobs_bar = CompletedJobsBar(total_jobs=len(jobs), minimize=None)

      while not cluster_interface.n_completed_jobs == len(jobs):
          to_submit = [job for job in jobs if job.status == JobStatus.INITIAL_STATUS]
          for job in to_submit[:5]:
              cluster_interface.submit(job)

          for job in cluster_interface.submitted_jobs:
              if job.status == JobStatus.SUBMITTED or job.waiting_for_resume:
                  job.check_filesystem_for_errors()
          cluster_interface.check_error_msgs()

          submitted_bar.update(cluster_interface.n_submitted_jobs)
          running_bar.update_failed_jobs(cluster_interface.n_failed_jobs)
          running_bar.update(cluster_interface.n_running_jobs + cluster_interface.n_completed_jobs)
          successful_jobs_bar.update(cluster_interface.n_successful_jobs)
          successful_jobs_bar.update_median_time_left(cluster_interface.median_time_left)

          if cluster_interface.n_failed_jobs > cluster_interface.n_successful_jobs + cluster_interface.n_running_jobs + 5:
              cluster_interface.close()
              raise RuntimeError(f"Too many ({cluster_interface.n_failed_jobs}) jobs failed. Ending procedure.")

          time.sleep(0.2)

  post_opt(cluster_interface)

  df, all_params, metrics = None, None, None
  for job in jobs:
    results = job.get_results()
    if results is None:
      continue
    job_df, job_all_params, job_metrics = results
    if df is None:
      df, all_params, metrics = job_df, job_all_params, job_metrics
    else:
      df = pd.concat((df, job_df), 0)
  return df, all_params, metrics, cluster_interface.collect_stats_from_hooks()
