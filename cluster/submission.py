import os
from time import sleep
from warnings import warn

import pandas as pd

from .constants import *
from .errors import OneTimeExceptionHandler

class SubmissionStatus(object):
  def __init__(self, total_jobs, fraction_to_finish, min_fraction_to_finish):

    self.total = total_jobs
    self.fraction_to_finish = fraction_to_finish
    self.min_fraction_to_finish = min_fraction_to_finish

    self.completed = 0
    self.running = 0
    self.idle = total_jobs
    self.held = 0

  @property
  def hopeful_to_finish(self):
    return self.running + self.idle

  @property
  def gone_from_cluster(self):
    return self.total - self.hopeful_to_finish - self.held

  @property
  def no_output(self):
    return max(self.gone_from_cluster - self.completed, 0)

  @property
  def running_after_completion(self):
    return max(self.completed - self.gone_from_cluster, 0)

  @property
  def running_for_print(self):
    return self.running - self.running_after_completion

  @property
  def failed(self):
    return self.held + self.no_output

  @property
  def max_completable(self):
    return self.total - self.failed

  @property
  def total_need_to_finish(self):
    bare_minimum = self.total * self.min_fraction_to_finish
    fraction_of_completable = int(self.fraction_to_finish * self.max_completable)
    return max(bare_minimum, fraction_of_completable)

  @property
  def still_need_to_finish(self):
    return self.total_need_to_finish - self.completed

  @property
  def finished(self):
    return self.completed >= self.total_need_to_finish

  def update(self, completed, cluster_response):
    self.completed = completed
    if cluster_response:
      self.running, self.idle, self.held = cluster_response

  def do_checks(self, error_handler):
    if self.held > 0:
      error_handler.maybe_raise('Some jobs held!')
    if self.no_output > 0:
      error_handler.maybe_raise('Some jobs exited without output! Possible explanation: filesystem lag.')
    if self.hopeful_to_finish < self.still_need_to_finish:
      raise RuntimeError('Too many jobs failed. Impossible to continue.')

  def __repr__(self):
    return ('Total: {.total}, Completed with output: {.completed}, Failed: {.failed}, '
            'Running: {.running_for_print}, Idle: {.idle}, Still need to finish: {.still_need_to_finish}').format(
      *(6 * [self]))


def execute_submission(submission, collect_data_directory, fraction_need_to_finish=1.0, min_fraction_to_finish=0.5,
                       ignore_errors=True):
  error_handler = OneTimeExceptionHandler(ignore_errors=ignore_errors)
  submission_status = SubmissionStatus(total_jobs=submission.total_jobs,
                                       fraction_to_finish=fraction_need_to_finish,
                                       min_fraction_to_finish=min_fraction_to_finish)

  git_conn = submission.git_conn()

  print('Submitting jobs ...')
  df, params, metrics = None, None, None
  with submission:
    while not submission_status.finished:
      print(submission_status)
      sleep(60)
      df, params, metrics = load_cluster_results(collect_data_directory)
      completed_succesfully = len(df)

      any_errors = submission.check_error_msgs()
      if any_errors:
        error_handler.maybe_raise('Some jobs had errors!')
      status = submission.get_status()
      submission_status.update(completed_succesfully, status)
      submission_status.do_checks(error_handler)

  print('Submission finished ({}/{})'.format(submission_status.completed, submission_status.total))
  git_meta = None
  if git_conn:
      git_meta = git_conn.formatted_meta_information
  assert df is not None
  return df, params, metrics, git_meta


def load_dirs_containing_cluster_output(base_path):
  job_output_files = (CLUSTER_PARAM_FILE, CLUSTER_METRIC_FILE)
  for root, dirs, files in os.walk(base_path):
    if all([filename in files for filename in job_output_files]):
      param_df, metric_df = (pd.read_csv(os.path.join(root, filename)) for filename in job_output_files)
      resulting_df = pd.concat([param_df, metric_df], axis=1)
      yield resulting_df, tuple(sorted(param_df.columns)), tuple(sorted(metric_df.columns))


def load_cluster_results(base_path):
  output = list(zip(*load_dirs_containing_cluster_output(base_path)))

  if not output:
    return [], [], []

  all_dfs, all_params, all_metrics = output

  if not len(set(all_params)) == 1:
    warn("Two files had non-identical parameters. Missing data?")

  if not len(set(all_metrics)) == 1:
    warn("Two files had non-identical metrics. Missing data?")

  return pd.concat(all_dfs, ignore_index=True), all_params[0], all_metrics[0]
