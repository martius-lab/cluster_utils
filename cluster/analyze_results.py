import datetime
import os
import pickle
from itertools import count
from tempfile import TemporaryDirectory

from .data_analysis import *
from .distributions import TruncatedLogNormal, smart_round, NumericalDistribution, Discrete
from .latex_utils import LatexFile
from .utils import nested_to_dict, shorten_string
from .constants import *
from .git_utils import GitConnector


class Metaoptimizer(object):
  def __init__(self, distribution_list, metric_to_optimize, best_jobs_to_take, minimize, with_restarts):
    self.distribution_list = distribution_list
    self.metric_to_optimize = metric_to_optimize
    self.best_jobs_to_take = best_jobs_to_take
    self.minimize = minimize
    self.with_restarts = with_restarts

    self.full_df = pd.DataFrame()
    self.minimal_df = pd.DataFrame()
    self.params = [distr.param_name for distr in self.distribution_list]

    self.best_param_values = {}
    self.iteration = 0

  @classmethod
  def try_load_from_pickle(cls, file, distribution_list, metric_to_optimize, best_jobs_to_take, minimize, with_restarts):
    if not os.path.exists(file):
      return None

    metaopt = pickle.load(open(file, 'rb'))
    if (metric_to_optimize, minimize) != (metaopt.metric_to_optimize, metaopt.minimize):
      raise ValueError('Attempted to continue but optimizes a different metric!')
    current_best_params = metaopt.get_best_params()
    for distr in distribution_list:
      if distr.param_name in metaopt.params:
        distr.fit(current_best_params[distr.param_name])

    metaopt.best_jobs_to_take = best_jobs_to_take
    metaopt.distribution_list = distribution_list
    setattr(metaopt, 'with_restarts', with_restarts)
    metaopt.params = [distr.param_name for distr in metaopt.distribution_list]
    return metaopt

  def process_new_df(self, df):
    self.iteration += 1
    df['iteration'] = self.iteration

    self.full_df = pd.concat([self.full_df, df], ignore_index=True)
    self.full_df = self.full_df.sort_values([self.metric_to_optimize], ascending=self.minimize)

    self.minimal_df = average_out(self.full_df, [self.metric_to_optimize], self.params)
    self.minimal_df = self.minimal_df.sort_values([self.metric_to_optimize], ascending=self.minimize)

    current_best_params = self.get_best_params()
    from json import dumps
    for distr in self.distribution_list:
      distr.fit(current_best_params[distr.param_name])

  def get_best_params(self):
    return best_params(self.minimal_df, params=self.params, metric=self.metric_to_optimize,
                       minimum=self.minimize, how_many=self.best_jobs_to_take)

  @property
  def settings_to_restart(self):
    if not self.with_restarts:
      return None
    if not len(self.minimal_df):
      return None

    best_ones = self.get_best_params()
    repeats = 1 + self.iteration // 4

    def restart_setting_generator():
      length = min(len(val) for val in best_ones.values())
      job_budget = self.best_jobs_to_take
      for i in range(length):
        nested_items = [(key.split('.'), val[i]) for key, val in best_ones.items()]
        for j in range(repeats):
            job_budget = job_budget - 1
            to_restart = nested_to_dict(nested_items)
            print(to_restart)
            yield to_restart
            if job_budget == 0:
                return

    return restart_setting_generator()

  def best_jobs_model_dirs(self, how_many):
    df_to_use = self.full_df[['model_dir', self.metric_to_optimize]]
    return best_jobs(df_to_use, metric=self.metric_to_optimize, how_many=how_many, minimum=self.minimize)['model_dir']


  @property
  def minimal_restarts_to_count(self):
    if self.with_restarts:
      return 1 + (self.iteration // 4)
    else:
      return 1

  def get_best(self, how_many=10):

    if self.iteration > 0:
      df_to_use = self.minimal_df[self.minimal_df[RESTART_PARAM_NAME] >= self.minimal_restarts_to_count]
      return best_jobs(df_to_use, metric=self.metric_to_optimize, how_many=how_many, minimum=self.minimize)
    else:
      return ''

  def provide_recommendations(self, how_many):
    best_jobs_df = self.get_best(how_many).reset_index()
    best_jobs_df[self.metric_to_optimize] = list(smart_round(best_jobs_df[self.metric_to_optimize]))

    metric_std = self.metric_to_optimize + STD_ENDING
    if self.with_restarts and self.minimal_restarts_to_count > 1:
      best_jobs_df[metric_std] = list(smart_round(best_jobs_df[metric_std]))
      sign = -1.0 if self.minimize else 1.0
      mean, std = best_jobs_df[self.metric_to_optimize], best_jobs_df[metric_std]

      # pessimistic estimate mean - std/sqrt(samples), based on Central Limit Theorem
      expected_metric = mean - (sign * std / np.sqrt(best_jobs_df[RESTART_PARAM_NAME]))
      best_jobs_df[f'expected {self.metric_to_optimize}'] = expected_metric
    else:
      best_jobs_df[f'expected {self.metric_to_optimize}'] = best_jobs_df[self.metric_to_optimize]

    del best_jobs_df[metric_std]
    del best_jobs_df[self.metric_to_optimize]
    del best_jobs_df[RESTART_PARAM_NAME]
    del best_jobs_df['index']

    best_jobs_df.index += 1
    best_jobs_df = best_jobs_df.transpose()
    best_jobs_df.index = [shorten_string(el, 40) for el in best_jobs_df.index]
    return best_jobs_df

  def save_pdf_report(self, output_file, calling_script, submission_hook_stats):
    today = datetime.datetime.now().strftime("%B %d, %Y")
    latex_title = 'Results of optimization procedure from ({})'.format(today)
    latex = LatexFile(latex_title)

    if 'GitConnector' in submission_hook_stats and submission_hook_stats['GitConnector']:
      latex.add_generic_section('Git Meta Information', content=submission_hook_stats['GitConnector'])

    tmp_nums = count()
    files = []
    with TemporaryDirectory() as tmpdir:
      for distr in self.distribution_list:
        filename = os.path.join(tmpdir, '{}.pdf'.format(next(tmp_nums)))
        if isinstance(distr, NumericalDistribution):
          log_scale = isinstance(distr, TruncatedLogNormal)
          res = distribution(self.full_df, 'iteration', distr.param_name,
                             filename=filename, metric_logscale=log_scale,
                             transition_colors=True, x_bounds=(distr.lower, distr.upper))
          if res:
            files.append(filename)
        elif isinstance(distr, Discrete):
          count_plot_horizontal(self.full_df, 'iteration', distr.param_name, filename=filename)
          files.append(filename)
        else:
          assert False

      overall_progress_file = os.path.join(tmpdir, '{}.pdf'.format(next(tmp_nums)))
      plot_opt_progress(self.full_df, self.metric_to_optimize, overall_progress_file)

      sensitivity_file = os.path.join(tmpdir, '{}.pdf'.format(next(tmp_nums)))
      importance_by_iteration_plot(self.full_df, self.params, self.metric_to_optimize, self.minimize,
                                   sensitivity_file)

      latex.add_section_from_figures('Overall progress', [overall_progress_file], common_scale=1.2)
      latex.add_section_from_dataframe('Top 5 recommendations', self.provide_recommendations(5))
      latex.add_section_from_figures('Hyperparameter importance', [sensitivity_file])
      latex.add_section_from_figures('Distribution development', files)
      latex.add_section_from_python_script('Specification', calling_script)
      latex.produce_pdf(output_file)

  def save_data_and_self(self, directory):
    self.full_df.to_csv(os.path.join(directory, FULL_DF_FILE))
    self.minimal_df.to_csv(os.path.join(directory, REDUCED_DF_FILE))
    self_file = os.path.join(directory, STATUS_PICKLE_FILE)
    with open(self_file, 'wb') as f:
      pickle.dump(self, f)
