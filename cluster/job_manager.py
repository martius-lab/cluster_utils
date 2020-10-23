import logging
import os
import shutil
import signal
import sys
import time

import numpy as np
import pandas as pd

from cluster import constants
from cluster.cluster_system import get_cluster_type
from cluster.communication_server import CommunicationServer
from cluster.git_utils import ClusterSubmissionGitHook
from cluster.job import Job, JobStatus
from cluster.optimizers import NGOptimizer
from cluster.progress_bars import CompletedJobsBar, RunningJobsBar, SubmittedJobsBar, redirect_stdout_to_tqdm
from cluster.settings import optimizer_dict
from cluster.user_interaction import InteractiveMode, NonInteractiveMode
from cluster.utils import log_and_print, make_red, process_other_params, rm_dir_full


def init_logging(working_dir):
    from importlib import reload
    reload(logging)
    filename = os.path.join(working_dir, 'cluster_run.log')
    logging.basicConfig(filename=filename,
                        level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    print(f"Detailed logging available in {filename}")


def ensure_empty_dir(dir_name, defensive=False):
    logger = logging.getLogger('cluster_utils')
    if os.path.exists(dir_name):
        if defensive:
            print(make_red(f"Directory {dir_name} exists. Delete everything? (y/N)"))
            ans = input()
            if ans.lower() == 'y':
                shutil.rmtree(dir_name, ignore_errors=True)
                logger.info(f"Deleted old contents of {dir_name}")
                os.makedirs(dir_name)
        else:
            shutil.rmtree(dir_name, ignore_errors=True)
            logger.info(f"Deleted old contents of {dir_name}")
            os.makedirs(dir_name)
    else:
        os.makedirs(dir_name)
        logger.info(f"Directory {dir_name} created")


def dict_to_dirname(setting, id, smart_naming=True):
    vals = ['{}={}'.format(str(key)[:3], str(value)[:6]) for key, value in setting.items() if
            not isinstance(value, dict)]
    res = '{}_{}'.format(id, '_'.join(vals))
    if len(res) < 35 and smart_naming:
        return res
    return str(id)


def update_best_job_datadirs(result_dir, working_dirs, remove_working_dirs=True):
    logger = logging.getLogger('cluster_utils')
    datadir = os.path.join(result_dir, 'best_jobs')
    os.makedirs(datadir, exist_ok=True)

    short_names = [working_dir.split('_')[-1].replace('/', '_') for working_dir in working_dirs]

    # Copy over new best directories
    for working_dir in working_dirs:
        if os.path.exists(working_dir):
            new_dir_name = working_dir.split('_')[-1].replace('/', '_')
            new_dir_full = os.path.join(datadir, new_dir_name)
            if not os.path.exists((new_dir_full)):
                shutil.copytree(working_dir, new_dir_full)
            if remove_working_dirs:
                rm_dir_full(working_dir)

    # Delete old best directories if outdated
    for dir_or_file in os.listdir(datadir):
        full_path = os.path.join(datadir, dir_or_file)
        if os.path.isfile(full_path):
            continue
        if dir_or_file not in short_names:
            rm_dir_full(full_path)

    logger.info(f"Best jobs in directory {datadir} updated.")

def initialize_hp_optimizer(result_dir, optimizer_str, optimized_params, metric_to_optimize, minimize, report_hooks,
                            number_of_samples, **optimizer_settings):
    logger = logging.getLogger('cluster_utils')

    possible_pickle = os.path.join(result_dir, constants.STATUS_PICKLE_FILE)
    hp_optimizer = optimizer_dict[optimizer_str].try_load_from_pickle(possible_pickle, optimized_params,
                                                                      metric_to_optimize,
                                                                      minimize, report_hooks, **optimizer_settings)
    if hp_optimizer is None:
        logger.info("No earlier optimization status found. Starting new optimization")
        hp_optimizer = optimizer_dict[optimizer_str](optimized_params=optimized_params,
                                                     metric_to_optimize=metric_to_optimize,
                                                     minimize=minimize, number_of_samples=number_of_samples,
                                                     report_hooks=report_hooks,
                                                     **optimizer_settings)
    else:
        logger.info("Optimization status loaded.")
    return hp_optimizer


def pre_opt(base_paths_and_files, submission_requirements, optimized_params, other_params, number_of_samples,
            metric_to_optimize, minimize, optimizer_str, remove_jobs_dir, git_params, run_local, report_hooks,
            optimizer_settings):
    processed_other_params = process_other_params(other_params, None, optimized_params)
    ensure_empty_dir(base_paths_and_files['result_dir'], defensive=True)
    init_logging(base_paths_and_files['result_dir'])

    logger = logging.getLogger('cluster_utils')

    os.makedirs(base_paths_and_files['current_result_dir'], exist_ok=True)
    log_and_print(logger, f'Creating directory {base_paths_and_files["current_result_dir"]}')
    log_and_print(logger, f'Logs of individual jobs stored at {base_paths_and_files["jobs_dir"]}')

    hp_optimizer = initialize_hp_optimizer(base_paths_and_files['result_dir'], optimizer_str, optimized_params,
                                           metric_to_optimize, minimize, report_hooks, number_of_samples,
                                           **optimizer_settings)

    cluster_type = get_cluster_type(requirements=submission_requirements, run_local=run_local)

    cluster_interface = cluster_type(paths=base_paths_and_files,
                                     requirements=submission_requirements,
                                     remove_jobs_dir=remove_jobs_dir)
    if git_params is not None:
        cluster_interface.register_submission_hook(
            ClusterSubmissionGitHook(git_params, base_paths_and_files))
    else:
        msg = (f'Running without git repository, using local directory '
               f'{base_paths_and_files["main_path"]}. Make sure this is intentional!')
        logger.warning(msg)
        print(make_red(f'Warning: {msg}'))

    cluster_interface.exec_pre_run_routines()
    comm_server = CommunicationServer(cluster_interface)

    def signal_handler(sig, frame):
        cluster_interface.close()
        logger.info('Exiting now')
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    return hp_optimizer, cluster_interface, comm_server, processed_other_params


def post_opt(cluster_interface):
    cluster_interface.exec_post_run_routines()
    cluster_interface.close()
    print('Procedure successfully finished')


def pre_iteration_opt(base_paths_and_files):
    pass


def post_iteration_opt(cluster_interface, hp_optimizer, comm_server, base_paths_and_files, metric_to_optimize,
                       num_best_jobs_whose_data_is_kept, remove_working_dirs):
    pdf_output = os.path.join(base_paths_and_files['result_dir'], 'result.pdf')
    current_result_path = base_paths_and_files['current_result_dir']

    submission_hook_stats = cluster_interface.collect_stats_from_hooks()

    jobs_to_tell = [job for job in cluster_interface.successful_jobs if not job.results_used_for_update]
    hp_optimizer.tell(jobs_to_tell)

    print(hp_optimizer.minimal_df[:10])

    hp_optimizer.save_pdf_report(pdf_output, submission_hook_stats, current_result_path)

    hp_optimizer.iteration += 1

    hp_optimizer.save_data_and_self(base_paths_and_files['result_dir'])

    comm_server.jobs = []

    if num_best_jobs_whose_data_is_kept > 0:
        best_working_dirs = hp_optimizer.best_jobs_working_dirs(how_many=num_best_jobs_whose_data_is_kept)
        update_best_job_datadirs(base_paths_and_files['result_dir'], best_working_dirs, remove_working_dirs)

    if remove_working_dirs:
        finished_working_dirs = hp_optimizer.full_df['working_dir']
        for working_dir in finished_working_dirs:
            rm_dir_full(working_dir)


def hp_optimization(base_paths_and_files, submission_requirements, optimized_params, other_params,
                    number_of_samples, metric_to_optimize, minimize, n_jobs_per_iteration, kill_bad_jobs_early,
                    early_killing_params, optimizer_str='cem_metaoptimizer',
                    remove_jobs_dir=True, remove_working_dirs=True, git_params=None, run_local=None, num_best_jobs_whose_data_is_kept=0,
                    report_hooks=None, optimizer_settings=None, n_completed_jobs_before_resubmit=1,
                    no_user_interaction=False):
    if not (1 <= n_completed_jobs_before_resubmit <= n_jobs_per_iteration):
        raise ValueError(f'n_completed_jobs_before_resubmit must be in [1, {n_jobs_per_iteration}]')

    optimizer_settings = optimizer_settings or {}
    logger = logging.getLogger('cluster_utils')
    base_paths_and_files['current_result_dir'] = os.path.join(base_paths_and_files['result_dir'], 'working_directories')

    hp_optimizer, cluster_interface, comm_server, processed_other_params = pre_opt(base_paths_and_files,
                                                                                  submission_requirements,
                                                                                  optimized_params,
                                                                                  other_params,
                                                                                  number_of_samples,
                                                                                  metric_to_optimize,
                                                                                  minimize, optimizer_str,
                                                                                  remove_jobs_dir,
                                                                                  git_params, run_local,
                                                                                  report_hooks,
                                                                                  optimizer_settings,
                                                                                  )
    iteration_offset = hp_optimizer.iteration
    pre_iteration_opt(base_paths_and_files)

    interaction_mode = NonInteractiveMode if no_user_interaction else InteractiveMode
    with interaction_mode(cluster_interface, comm_server) as check_for_keyboard_input:
        with redirect_stdout_to_tqdm():
            submitted_bar = SubmittedJobsBar(total_jobs=number_of_samples)
            running_bar = RunningJobsBar(total_jobs=number_of_samples)
            successful_jobs_bar = CompletedJobsBar(total_jobs=number_of_samples, minimize=minimize)

            while cluster_interface.n_completed_jobs < number_of_samples:
                check_for_keyboard_input()
                time.sleep(0.2)
                jobs_to_tell = [job for job in cluster_interface.successful_jobs if not job.results_used_for_update]
                hp_optimizer.tell(jobs_to_tell)
                n_jobs_completed_cur_iteration = (cluster_interface.n_completed_jobs
                                                  - n_jobs_per_iteration * (hp_optimizer.iteration - iteration_offset))
                n_jobs_submitted_cur_iteration = (cluster_interface.n_submitted_jobs
                                                  - n_jobs_per_iteration * (hp_optimizer.iteration - iteration_offset))
                max_job_submissions = ((n_jobs_completed_cur_iteration // n_completed_jobs_before_resubmit)
                                       * n_completed_jobs_before_resubmit + n_jobs_per_iteration)
                iteration_finished = cluster_interface.n_completed_jobs // n_jobs_per_iteration > hp_optimizer.iteration - iteration_offset
                if (n_jobs_submitted_cur_iteration < max_job_submissions
                        and cluster_interface.n_submitted_jobs < number_of_samples
                        and not iteration_finished):
                    new_settings = hp_optimizer.ask()
                    new_job = Job(id=cluster_interface.inc_job_id, settings=new_settings,
                                  other_params=processed_other_params, paths=base_paths_and_files,
                                  iteration=hp_optimizer.iteration + 1, connection_info=comm_server.connection_info,
                                  metric_to_watch=metric_to_optimize)
                    if isinstance(hp_optimizer, NGOptimizer):
                        hp_optimizer.add_candidate(new_job.id)
                    cluster_interface.add_jobs(new_job)
                    cluster_interface.submit(new_job)
                if iteration_finished:
                    post_iteration_opt(cluster_interface, hp_optimizer, comm_server, base_paths_and_files, metric_to_optimize,
                                       num_best_jobs_whose_data_is_kept, remove_working_dirs)
                    logger.info(f'starting new iteration: {hp_optimizer.iteration}')
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

                best_seen_metric = cluster_interface.get_best_seen_value_of_main_metric(minimize=minimize)
                if len(hp_optimizer.full_df) > 0:
                    best_value = hp_optimizer.full_df[hp_optimizer.metric_to_optimize].iloc[0]
                else:
                    best_value = None

                estimates = [item for item in [best_seen_metric, best_value] if item is not None]
                if estimates:
                    best_estimate = min(estimates) if minimize else max(estimates)
                    successful_jobs_bar.update_best_val(best_estimate)
                if kill_bad_jobs_early:
                    kill_bad_looking_jobs(cluster_interface, metric_to_optimize, minimize, **early_killing_params)

    post_iteration_opt(cluster_interface, hp_optimizer, comm_server, base_paths_and_files, metric_to_optimize,
                       num_best_jobs_whose_data_is_kept, remove_working_dirs)
    post_opt(cluster_interface)

    if remove_working_dirs:
        rm_dir_full(base_paths_and_files['current_result_dir'])


def kill_bad_looking_jobs(cluster_interface, metric_to_optimize, minimize, target_rank, how_many_stds):
    intermediate_results = [job.reported_metric_values + [job.metrics[metric_to_optimize]]
                            for job in cluster_interface.successful_jobs if job.reported_metric_values]
    if not intermediate_results:
        return
    max_len = max([len(item) for item in intermediate_results])
    intermediate_results = [item for item in intermediate_results if len(item) == max_len]

    if len(intermediate_results) < 5:
        return

    intermediate_results_np = np.array(intermediate_results)
    sign = 1 if minimize else -1
    intermediate_ranks = np.argsort(np.argsort(intermediate_results_np*sign, axis=0), axis=0)
    rank_deviations = np.sqrt(np.mean((intermediate_ranks - intermediate_ranks[:, -1:]) ** 2, axis=0))

    for job in cluster_interface.running_jobs:
        if not job.reported_metric_values:
            continue
        if len(job.reported_metric_values) > intermediate_results_np.shape[1]//2:
            # If a job runs more than half of its runtime, don't kill it
            continue
        index, value = len(job.reported_metric_values)-1, np.array(job.reported_metric_values[-1])
        all_values = np.concatenate([intermediate_results_np[:, index], value.reshape(1)])
        rank_of_current_job = np.argsort(np.argsort(all_values*sign))[-1]
        if rank_of_current_job - how_many_stds*rank_deviations[index] > target_rank:
            job.metrics = {metric_to_optimize: float(value)}
            job.status = JobStatus.CONCLUDED
            job.set_results()
            cluster_interface.stop_fn(job.cluster_id)

def grid_search(base_paths_and_files, submission_requirements, optimized_params, other_params,
                restarts, remove_jobs_dir=True, remove_working_dirs=False, samples=None,
                git_params=None, run_local=None, report_hooks=None,
                load_existing_results=False, no_user_interaction=False):

    base_paths_and_files['current_result_dir'] = os.path.join(base_paths_and_files['result_dir'], 'working_directories')
    hp_optimizer, cluster_interface, comm_server, processed_other_params = pre_opt(base_paths_and_files,
                                                                                   submission_requirements,
                                                                                   optimized_params,
                                                                                   other_params,
                                                                                   samples,
                                                                                   None,
                                                                                   False,
                                                                                   'gridsearch',
                                                                                   remove_jobs_dir,
                                                                                   git_params,
                                                                                   run_local,
                                                                                   report_hooks,
                                                                                   dict(restarts=restarts))

    pre_iteration_opt(base_paths_and_files)
    logger = logging.getLogger('cluster_utils')

    settings = hp_optimizer.ask_all()
    jobs = [Job(id=cluster_interface.inc_job_id, settings=setting,
                other_params=processed_other_params, paths=base_paths_and_files, iteration=hp_optimizer.iteration,
                connection_info=comm_server.connection_info)
            for setting in settings]
    cluster_interface.add_jobs(jobs)

    if load_existing_results:
        logger.info("Trying to load existing results")
        for job in jobs:
            job.try_load_results_from_filesystem(base_paths_and_files)

    interaction_mode = NonInteractiveMode if no_user_interaction else InteractiveMode
    with interaction_mode(cluster_interface, comm_server) as check_for_keyboard_input:
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
                check_for_keyboard_input()
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

    if remove_working_dirs:
        rm_dir_full(base_paths_and_files['current_result_dir'])

    return df, all_params, metrics, cluster_interface.collect_stats_from_hooks()
