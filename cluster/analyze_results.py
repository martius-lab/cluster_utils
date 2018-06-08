import datetime
import os
import pickle
from itertools import count
from tempfile import TemporaryDirectory

from .data_analysis import *
from .distributions import TruncatedLogNormal, smart_round, NumericalDistribution, Discrete
from .latex_utils import LatexFile


class Metaoptimizer(object):
  def __init__(self, distribution_list, metric_to_optimize, best_jobs_to_take, minimize):
    self.distribution_list = distribution_list
    self.metric_to_optimize = metric_to_optimize
    self.best_jobs_to_take = best_jobs_to_take
    self.minimize = minimize

    self.full_df = pd.DataFrame()
    self.minimal_df = pd.DataFrame()
    self.params = [distr.param_name for distr in self.distribution_list]

    self.best_param_values = {}
    self.iteration = 0

  @classmethod
  def try_load_from_pickle(cls, file, distribution_list, metric_to_optimize, best_jobs_to_take, minimize):
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
    metaopt.params = [distr.param_name for distr in metaopt.distribution_list]
    return metaopt

  def process_new_df(self, df):
    self.iteration += 1
    df['iteration'] = self.iteration

    self.full_df = pd.concat([self.full_df, df], ignore_index=True)
    self.full_df = self.full_df.sort_values([self.metric_to_optimize], ascending=self.minimize)

    minimal_df = average_out(df, [self.metric_to_optimize], self.params + ['iteration'])
    self.minimal_df = pd.concat([self.minimal_df, minimal_df], ignore_index=True)
    self.minimal_df = self.minimal_df.sort_values([self.metric_to_optimize], ascending=self.minimize)

    current_best_params = self.get_best_params()
    for distr in self.distribution_list:
      distr.fit(current_best_params[distr.param_name])

  def get_best_params(self):
    return best_params(self.minimal_df, params=self.params, metric=self.metric_to_optimize,
                       minimum=self.minimize, how_many=self.best_jobs_to_take)

  def get_best(self, how_many=10):
    if self.iteration > 0:
      return best_jobs(self.minimal_df, metric=self.metric_to_optimize, how_many=how_many, minimum=self.minimize)
    else:
      return ''

  def save_pdf_report(self, output_file, calling_script):
    today = datetime.datetime.now().strftime("%B %d, %Y")
    latex_title = 'Results of optimization procedure from ({})'.format(today)
    latex = LatexFile(latex_title)

    latex.add_section_from_python_script('Specification', calling_script)

    best_jobs_df = self.get_best(10).reset_index()
    best_jobs_df[self.metric_to_optimize] = list(smart_round(best_jobs_df[self.metric_to_optimize]))

    metric_std = self.metric_to_optimize + STD_ENDING
    best_jobs_df[metric_std] = list(smart_round(best_jobs_df[metric_std]))
    del best_jobs_df['index']
    best_jobs_df.index += 1
    best_jobs_df = best_jobs_df.transpose()
    latex.add_section_from_dataframe('Overall best jobs', best_jobs_df)

    tmp_nums = count()
    files = []
    with TemporaryDirectory() as tmpdir:
      for distr in self.distribution_list:
        filename = os.path.join(tmpdir, '{}.pdf'.format(next(tmp_nums)))
        if isinstance(distr, NumericalDistribution):
          log_scale = isinstance(distr, TruncatedLogNormal)
          res = distribution(self.minimal_df, 'iteration', distr.param_name,
                             filename=filename, metric_logscale=log_scale,
                             transition_colors=True, x_bounds=(distr.lower, distr.upper))
          if res:
            files.append(filename)
        elif isinstance(distr, Discrete):
          count_plot_horizontal(self.minimal_df, 'iteration', distr.param_name, filename=filename)
          files.append(filename)
        else:
          assert False

      latex.add_section_from_figures('Distribution development', files)
      latex.produce_pdf(output_file)

  def save_data_and_self(self, directory):
    self.full_df.to_csv(os.path.join(directory, FULL_DF_FILE))
    self.minimal_df.to_csv(os.path.join(directory, REDUCED_DF_FILE))
    self_file = os.path.join(directory, STATUS_PICKLE_FILE)
    with open(self_file, 'wb') as f:
      pickle.dump(self, f)
