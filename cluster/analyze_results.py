import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


def walk_csv_groups_recursively(path, csv_group):
  for root, dirs, files in os.walk(path):
    csv_files = [file for file in files if file[-3:] == 'csv']
    if all([item in csv_files for item in csv_group]):
      yield {item: os.path.join(root, item) for item in csv_group}


def file_group_to_df(file_group):
  dfs = {name: pd.read_csv(file) for name, file in file_group.items()}
  columns = {name: sorted(list(df.columns)) for name, df in dfs.items()}
  df = pd.concat([one_df for one_df in dfs.values()], axis=1)
  return df, columns


class ClusterDataFrame(object):
  def __init__(self, path, param_name, metric_name):
    file_groups = walk_csv_groups_recursively(path, [param_name, metric_name])

    dfs_and_columns = [file_group_to_df(file_group) for file_group in file_groups]
    if not dfs_and_columns:
      self.df = []
      return
    dfs, columns = zip(*dfs_and_columns)

    differences = [(columns1, columns2) for columns1, columns2 in zip(columns[1:], columns[:-1])
                   if columns1 != columns2]
    if any(differences):
      raise ValueError('Two parameter files had non-identical sets of parameters', differences)

    self.df = pd.concat(dfs, ignore_index=True)
    self.params = columns[0][param_name]
    self.metrics = columns[0][metric_name]
    self.ids = []
    self.base_dir = path

  def set_id_columns(self, id_columns):
    if id_columns is None:
      return
    self.ids = id_columns
    self.params = [column for column in self.params if column not in id_columns]

  def reduce_constant_params(self, other_to_remove=None):
    if other_to_remove is None:
      other_to_remove = []
    self.params = [column for column in self.params if
                   self.df[column].nunique() > 1 and column not in other_to_remove]
    self.df = self.df[self.params + self.metrics + self.ids]

  def get_best_job(self, metric, minimum=False, show_all_metrics=True):
    if show_all_metrics:
      columns = self.ids + self.params + self.metrics
    else:
      columns = self.ids + self.params + [metric]
    if minimum:
      to_return = self.df.loc[self.df[metric].idxmin()]
    else:
      to_return = self.df.loc[self.df[metric].idxmax()]
    to_return = to_return[columns].rename('')
    return to_return

  def get_performance_summary(self):
    perf = {}
    for metric in self.metrics:
      min_val = self.df[metric].min()
      max_val = self.df[metric].max()
      mean_val = self.df[metric].mean()
      std_val = self.df[metric].std()
      perf[metric] = {'min': min_val, 'max': max_val, 'mean': mean_val, 'stddev': std_val}

    return pd.DataFrame.from_dict(perf, orient='index')

  def heat_map(self, param1, param2, metric, filename=None, annot=False):
    if (param1 not in self.params or
            param2 not in self.params or
            metric not in self.metrics):
      raise ValueError('Unknown parameter or metric given')

    reduced_df = self.df[[param1, param2, metric]]
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
    return True

  def best_params(self, metric, how_many):
    df_reduced = self.df.groupby(self.params, as_index=False)[metric].agg({metric: np.mean})
    df_reduced = df_reduced.sort_values([metric], ascending=False)
    best_params = df_reduced[self.params].iloc[0:how_many].to_dict()
    return {key: list(value.values()) for key, value in best_params.items()}

  def best_jobs(self, metric, how_many, average_restarts=True):
    if average_restarts:
      df_to_use = self.df.groupby(self.params, as_index=False)[metric].agg({metric: np.mean})
      df_to_use = df_to_use.sort_values([metric], ascending=False)
    else:
      df_to_use = self.df
    return df_to_use.iloc[0:how_many]

  def distribution(self, param, metric, filename=None, metric_logscale=False):
    if (param not in self.params or
            metric not in self.metrics):
      raise ValueError('Unknown parameter or metric given')
    smaller_df = self.df[[param, metric]]
    unique_vals = smaller_df[param].unique()
    if not len(unique_vals):
      return False
    ax = None
    for val in unique_vals:
      filtered = smaller_df.loc[smaller_df[param] == val][metric]
      if filtered.nunique() == 1:
        print('Singular matrix for {}, skipping'.format(metric))
        continue
      try:
        ax = sns.distplot(filtered, hist=False, label=str(val))
      except:
        pass
    if ax is None:
      return False
    if metric_logscale:
      ax.set_xscale("log")
    ax.set_title('Distribution by {}'.format(param))
    fig = plt.gcf()
    if filename:
      fig.savefig(filename, format='pdf', dpi=1200)
    else:
      plt.show()
    plt.clf()
    return True
