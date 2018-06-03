from .data_analysis import *
from .latex_utils import LatexFile
from .distributions import TruncatedLogNormal, smart_round
from .constants import *
import os
import datetime
from tempfile import TemporaryDirectory
from itertools import count
import pickle

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


  def process_new_df(self, df):
    self.iteration += 1
    df['iteration'] = self.iteration

    self.full_df = pd.concat([self.full_df, df], ignore_index=True)

    minimal_df = average_out(df, [self.metric_to_optimize], self.params + ['iteration'])
    self.minimal_df = pd.concat([self.minimal_df, minimal_df], ignore_index=True)

    current_best_params = best_params(self.minimal_df, params=self.params, metric=self.metric_to_optimize,
                                      minimum=self.minimize, how_many=self.best_jobs_to_take)

    for distr in self.distribution_list:
      distr.fit(current_best_params[distr.param_name])

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
    best_jobs_df[self.metric_to_optimize+'_std'] = list(smart_round(best_jobs_df[self.metric_to_optimize+'_std']))
    del best_jobs_df['index']
    best_jobs_df.index += 1
    best_jobs_df = best_jobs_df.transpose()
    latex.add_section_from_dataframe('Overall best jobs', best_jobs_df)


    tmp_nums = count()
    files = []
    with TemporaryDirectory() as tmpdir:
      for distr in self.distribution_list:
        filename = os.path.join(tmpdir, '{}.pdf'.format(next(tmp_nums)))
        log_scale = isinstance(distr, TruncatedLogNormal)
        res = distribution(self.minimal_df, 'iteration', distr.param_name,
                           filename=filename, metric_logscale=log_scale,
                           darken_from_color=DISTR_COLOR)
        if res:
          files.append(filename)

      latex.add_section_from_figures('Distribution development', files)
      latex.produce_pdf(output_file)


  def save_data_and_self(self, directory):
    self.full_df.to_csv(os.path.join(directory, 'all_data.csv'))
    self.minimal_df.to_csv(os.path.join(directory, 'reduced_data.csv'))
    self_file = os.path.join(directory, 'status.pickle')
    with open(self_file, 'wb') as f:
      pickle.dump(self, f)



