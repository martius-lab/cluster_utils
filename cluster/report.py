import ast
import datetime
import os
import pickle
from subprocess import run
import sys
from importlib import import_module
from importlib import reload
from itertools import combinations
from shutil import copyfile

from . import analyze_results as res
import pandas as pd
from .utils import default_value_dict


def include_figure(filename, scale=1.0):
  return '\\includegraphics[scale={}]{{{}}}\n'.format(scale, filename)


def section(section_name, content):
  begin = '\\begin{{section}}{{{}}}\n'.format(section_name)
  end = '\\end{section}\n'
  return '{}{}{}'.format(begin, content, end)


def subsection(section_name, content):
  begin = '\\begin{{subsection}}{{{}}}\n'.format(section_name)
  end = '\\end{subsection}\n'
  return '{}\n\\leavevmode\n\n\\medskip\n{}{}'.format(begin, content, end)


def section_from_figures(section_name, file_list, common_scale=0.7):
  content = '\n'.join([include_figure(filename, common_scale) for filename in file_list])
  return section(section_name, content)


def subsection_from_figures(section_name, file_list, common_scale=0.7):
  content = '\n'.join([include_figure(filename, common_scale) for filename in file_list])
  return subsection(section_name, content)


def write_tex_file(title, date, content, filename):
  begin = '''
\\documentclass{amsart}
\\usepackage{graphicx}
\\usepackage{framed}
\\usepackage{verbatim}
\\usepackage{booktabs}
\\usepackage{url}
\\usepackage{underscore}
\\usepackage{listings}
\\usepackage{mdframed}

\\usepackage{color}

\\definecolor{codegreen}{rgb}{0,0.6,0}
\\definecolor{codegray}{rgb}{0.5,0.5,0.5}
\\definecolor{codepurple}{rgb}{0.58,0,0.82}
\\definecolor{backcolour}{rgb}{0.95,0.95,0.92}

\\lstdefinestyle{mystyle}{
    backgroundcolor=\\color{backcolour},
    commentstyle=\\color{codegreen},
    keywordstyle=\\color{magenta},
    numberstyle=\\tiny\\color{codegray},
    stringstyle=\\color{codepurple},
    basicstyle=\\footnotesize,
    breakatwhitespace=false,
    breaklines=true,
    captionpos=b,
    keepspaces=true,
    numbers=left,
    numbersep=5pt,
    showspaces=false,
    showstringspaces=false,
    showtabs=false,
    tabsize=2
}

\\lstset{style=mystyle}

\\graphicspath{{./figures/}}
\\newtheorem{theorem}{Theorem}[section]
\\newtheorem{conj}[theorem]{Conjecture}
\\newtheorem{lemma}[theorem]{Lemma}
\\newtheorem{prop}[theorem]{Proposition}
\\newtheorem{cor}[theorem]{Corollary}
\\def \\qbar {\\overline{\\mathbb{Q}}}
\\theoremstyle{definition}
\\newtheorem{definition}[theorem]{Definition}
\\newtheorem{example}[theorem]{Example}
\\newtheorem{xca}[theorem]{Exercise}
\\theoremstyle{remark}
\\newtheorem{remark}[theorem]{Remark}
\\numberwithin{equation}{section}
\\begin{document}\n
'''

  title_str = '\\title{{{}}}\n'.format(title)
  date_str = '\\date{{{}}}\n \\maketitle\n'.format(date)
  end = '\\end{document}'
  whole_latex = '{}{}{}{}{}'.format(begin, title_str, date_str, content, end)
  with open(filename, 'w') as f:
    f.write(whole_latex)


def get_overall_metric_content(cdf):
  return cdf.get_performance_summary().to_latex()


def load_metadata(filename):
  default_metric = {'log': False, 'minimize': True, 'annot': True}
  default_param = {}

  metric_data = default_value_dict(default_metric)
  param_data = default_value_dict(default_param)
  with open(filename) as f:
    metric_new, param_new = ast.literal_eval(f.read())
  for metric in metric_new:
    metric_data[metric].update(metric_new[metric])
  for param in param_new:
    param_data[param].update(param_new[param])
  return metric_data, param_data


def python_file_to_latex(python_file):
  with open(python_file) as f:
    raw = f.read()
  res = '\\begin{{lstlisting}}[language=Python]\n {}\\end{{lstlisting}}'.format(raw)
  return res


def latex_format(string):
  return string.replace('_', '-')


defaults = {'path_base': os.path.join('results', 'cluster'),
            'param_file_name': 'param_choice.csv',
            'metric_file': 'metrics.csv',
            'id_columns': ['id', 'model_dir'],
            'create_file': 'create_jobs.py',
            'save_dir': 'pdf_results',
            'latex_file_name': 'report.tex',
            'metadata_file': 'metadata.dat'}


def run_report(cmd_params):
  defaults.update(cmd_params)
  if 'job_name' not in defaults or not defaults['job_name']:
    raise ValueError('Job name not given!')

  job_name = defaults['job_name']
  path = os.path.join(defaults['path_base'], job_name)
  param_name = defaults['param_file_name']
  metric_name = defaults['metric_file']
  latex_file_name = job_name + '_' + defaults['latex_file_name']


  cdf = res.ClusterDataFrame(path, param_name, metric_name)
  cdf.reduce_constant_params()
  cdf.set_id_columns(defaults['id_columns'])

  job_file = os.path.join(path, defaults['create_file'])

  save_dir = defaults['save_dir']
  pdf_dir = job_name + '_' + datetime.datetime.now().strftime('%d_%m_%y')
  pdf_dir = os.path.join(save_dir, pdf_dir)
  figure_dir = os.path.join(pdf_dir, 'figures')
  latex_file_full = os.path.join(pdf_dir, latex_file_name)

  if not os.path.exists(figure_dir):
    os.makedirs(figure_dir)

  copyfile(job_file, os.path.join(pdf_dir, defaults['create_file']))

  job_info = section('Job specification', content=python_file_to_latex(job_file))
  overall_metrics = section('Overall performance', content=get_overall_metric_content(cdf))
  content = [job_info, overall_metrics]

  metric_data, param_data = load_metadata(defaults['metadata_file'])

  for metric in cdf.metrics:
    best_run_content = subsection('Best run parameters',
                                  cdf.get_best_job(metric,
                                                   minimum=metric_data[metric]['minimize']).to_latex())

    distr_figs = []
    for param in cdf.params:
      filename = os.path.join(figure_dir, '{}-distr-wrt-{}.pdf'.format(latex_format(param),
                                                                       latex_format(metric)))
      if cdf.distribution(param, metric, filename, metric_logscale=metric_data[metric]['log']):
        distr_figs.append(os.path.basename(filename))

    distributions_content = subsection_from_figures('Distributions wrt single hyparameters', distr_figs)

    heat_map_figs = []
    for param1, param2 in combinations(cdf.params, 2):
      filename = os.path.join(figure_dir, '{}vs{}-wrt{}.pdf'.format(latex_format(param1),
                                                                    latex_format(param2),
                                                                    latex_format(metric)))
      if cdf.heat_map(param1, param2, metric, filename, annot=metric_data[metric]['annot']):
        heat_map_figs.append(os.path.basename(filename))
    heatmap_content = subsection_from_figures('Heatmaps wrt all pairs', heat_map_figs)

    metric_content = '\n'.join([best_run_content, distributions_content, heatmap_content])
    content.append(section('Statistics of {}'.format(metric), content=metric_content))

  content_onestring = '\n'.join(content)

  date = str(datetime.datetime.today()).split()[0]
  title = 'Report on job \'{}\' from {}'.format(job_name, date)

  with open(os.path.join(pdf_dir, 'data.pickle'), 'wb') as f:
    pickle.dump(cdf, f)

  write_tex_file(title=title, date=date, content=content_onestring, filename=latex_file_full)

  run(['pdflatex', latex_file_name], cwd=str(pdf_dir))
  run(['xdg-open', latex_file_name[:-3]+'pdf'], cwd=str(pdf_dir))


if __name__ == '__main__':
  if len(sys.argv) > 1:
    arg = sys.argv[1]
    cmd_params = ast.literal_eval(arg)
  else:
    raise ValueError('No command line argument given!')
  run_report(cmd_params)


