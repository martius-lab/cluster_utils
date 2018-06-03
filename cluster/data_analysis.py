from contextlib import suppress
from warnings import warn

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


def performance_summary(df, metrics):
  perf = {}
  for metric in metrics:
    min_val = df[metric].min()
    max_val = df[metric].max()
    mean_val = df[metric].mean()
    std_val = df[metric].std()
    perf[metric] = {'min': min_val, 'max': max_val, 'mean': mean_val, 'stddev': std_val}

  return pd.DataFrame.from_dict(perf, orient='index')


def average_out(df, metrics, params_to_keep, std_ending='_std', add_std=True):
  new_df = df[params_to_keep + metrics]
  result = new_df.groupby(params_to_keep, as_index=False).agg(np.mean)
  if not add_std:
    return result
  for metric in metrics:
    std_name = metric + std_ending
    if std_name in result.columns:
      warn('Name {} already used. Skipping ...'.format(std_name))
    else:
      result[std_name] = new_df.groupby(params_to_keep, as_index=False).agg({metric: np.std})[metric]
  return result

def darker(color, factor=0.92):
  if color is None:
    return None
  r, g, b = color
  return (r * factor, g * factor, b * factor)

def distribution(df, param, metric, filename=None, metric_logscale=False, darken_from_color=None):
  smaller_df = df[[param, metric]]
  unique_vals = smaller_df[param].unique()
  if not len(unique_vals):
    return False
  ax = None
  color = darken_from_color
  for val in sorted(unique_vals):
    filtered = smaller_df.loc[smaller_df[param] == val][metric]
    if filtered.nunique() == 1:
      warn('Singular matrix for {}, skipping'.format(metric))
      continue
    with suppress(Exception):
      ax = sns.distplot(filtered, hist=False, label=str(val), color=color)
    color = darker(color)

  if ax is None:
    return False
  if metric_logscale:
    ax.set_xscale("log")
  ax.set_title('Distribution of {} by {}'.format(metric, param))
  fig = plt.gcf()
  if filename:
    fig.savefig(filename, format='pdf', dpi=1200)
  else:
    plt.show()
  plt.clf()
  return True


def heat_map(df, param1, param2, metric, filename=None, annot=False):
  reduced_df = df[[param1, param2, metric]]
  grouped_df = reduced_df.groupby([param1, param2], as_index=False).mean()
  pivoted_df = grouped_df.pivot(index=param1, columns=param2, values=metric)
  ax = sns.heatmap(pivoted_df, annot=annot)
  ax.set_title(metric)
  fig = plt.gcf()
  if filename:
    fig.savefig(filename, format='pdf', dpi=1200)
  else:
    plt.show()
  plt.clf()


def best_params(df, params, metric, how_many, minimum=False):
  df_sorted = df.sort_values([metric], ascending=minimum)
  best_params = df_sorted[params].iloc[0:how_many].to_dict()
  return {key: list(value.values()) for key, value in best_params.items()}


def best_jobs(df, metric, how_many, minimum=False):
  sorted_df = df.sort_values([metric], ascending=minimum)
  return sorted_df.iloc[0:how_many]
