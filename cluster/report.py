
import os
from itertools import combinations
from .latex_utils import LatexFile
import datetime
from .data_analysis import *
from tempfile import TemporaryDirectory
from . import export
from itertools import count
import seaborn as sns
from matplotlib import rc


@export
def init_plotting():
  sns.set_style("darkgrid", {'legend.frameon':True})
  rc('font',**{'family':'sans-serif','sans-serif':['Helvetica']})
  rc('text', usetex=True)


@export
def produce_basic_report(df, params, metrics, python_file, procedure_name, output_file,
                 maximized_metrics=None, log_scale_list=None):

  if log_scale_list is None:
    log_scale_list = []
  if maximized_metrics is None:
    maximized_metrics = []

  today = datetime.datetime.now().strftime("%B %d, %Y")
  latex_title = 'Cluster job \'{}\' results ({})'.format(procedure_name, today)
  latex = LatexFile(title=latex_title)

  latex.add_section_from_python_script('Specification', python_file)

  summary_df = performance_summary(df, metrics)
  latex.add_section_from_dataframe('Summary of results', summary_df)

  for metric in metrics:
    best_runs_df = best_jobs(df[params + [metric]], metric, 10, minimum=(metric not in maximized_metrics))
    latex.add_section_from_dataframe('Jobs with best result in \'{}\''.format(metric), best_runs_df)

  tmp_nums = count()
  with TemporaryDirectory() as tmpdir:
    for metric in metrics:
      distr_files = [os.path.join(tmpdir,'{}.pdf'.format(next(tmp_nums))) for param in params]

      distr_files = [fname for fname, param in zip(distr_files, params) if
                     distribution(df, param, metric, fname, metric_logscale=(metric in log_scale_list))]

      section_name = 'Distributions of \'{}\' w.r.t. parameters'.format(metric)
      latex.add_section_from_figures(section_name, distr_files)

      heat_map_files = []
      for param1, param2 in combinations(params, 2):
        filename = os.path.join(tmpdir, '{}.pdf'.format(next(tmp_nums)))
        heat_map(df, param1, param2, metric, filename)
        heat_map_files.append(filename)

      section_name = 'Heatmaps of {} w.r.t. parameters'.format(metric)
      latex.add_section_from_figures(section_name, heat_map_files)

    latex.produce_pdf(output_file)

