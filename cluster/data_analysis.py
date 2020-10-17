import logging

from sklearn.ensemble import RandomForestRegressor

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from .constants import *
from .utils import shorten_string

def performance_summary(df, metrics):
    perf = {}
    for metric in metrics:
        min_val = df[metric].min()
        max_val = df[metric].max()
        mean_val = df[metric].mean()
        std_val = df[metric].std()
        perf[metric] = {'min': min_val, 'max': max_val, 'mean': mean_val, 'stddev': std_val}

    return pd.DataFrame.from_dict(perf, orient='index')


def average_out(df, metrics, params_to_keep, std_ending=STD_ENDING, add_std=True):
    logger = logging.getLogger('cluster_utils')
    if not metrics:
        raise ValueError('Empty set of metrics not accepted.')
    new_df = df[params_to_keep + metrics]
    result = new_df.groupby(params_to_keep, as_index=False).agg(np.mean)
    result[RESTART_PARAM_NAME] = new_df.groupby(params_to_keep, as_index=False).agg({metrics[0]: 'size'})[metrics[0]]
    if not add_std:
        return result
    for metric in metrics:
        std_name = metric + std_ending
        if std_name in result.columns:
            logger.warning('Name {} already used. Skipping ...'.format(std_name))
        else:
            result[std_name] = new_df.groupby(params_to_keep, as_index=False).agg({metric: np.nanstd})[metric]
    return result


def darker(color, factor=0.85):
    if color is None:
        return None
    r, g, b = color
    return (r * factor, g * factor, b * factor)


def color_scheme():
    while True:
        for color in DISTR_BASE_COLORS:
            for i in range(5):
                yield color
                color = darker(color)


def distribution(df, param, metric, filename=None, metric_logscale=None, x_bounds=None):


    logger = logging.getLogger('cluster_utils')
    smaller_df = df[[param, metric]]
    unique_vals = smaller_df[param].unique()
    if not len(unique_vals):
        return False
    ax = None
    metric_logscale = metric_logscale if metric_logscale is not None else detect_scale(smaller_df[metric]) == 'log'
    try:
        ax = sns.kdeplot(data=smaller_df, x=metric, hue=param, palette='crest', fill=True,
                         common_norm=False, alpha=.5, linewidth=0, log_scale=metric_logscale)
    except Exception as e:
        logger.warning(f'sns.distplot failed for param {param} with exception {e}')

    if ax is None:
        return False

    if x_bounds is not None:
        ax.set_xlim(*x_bounds)
    ax.set_title('Distribution of {} by {}'.format(metric, param))
    fig = plt.gcf()
    if filename:
        fig.savefig(filename, format='pdf', dpi=1200)
    else:
        plt.show()
    plt.close(fig)
    return True


def heat_map(df, param1, param2, metric, filename=None, annot=False):
    reduced_df = df[[param1, param2, metric]]
    grouped_df = reduced_df.groupby([param1, param2], as_index=False).mean()
    pivoted_df = grouped_df.pivot(index=param1, columns=param2, values=metric)
    fmt = None if not annot else ".2g"
    ax = sns.heatmap(pivoted_df, annot=annot, fmt=fmt)
    ax.set_title(metric)
    fig = plt.gcf()
    if filename:
        fig.savefig(filename, format='pdf', dpi=1200)
    else:
        plt.show()
    plt.close(fig)


def best_params(df, params, metric, how_many, minimum=False):
    df_sorted = df.sort_values([metric], ascending=minimum)
    best_params = df_sorted[params].iloc[0:how_many].to_dict()
    return {key: list(value.values()) for key, value in best_params.items()}


def best_jobs(df, metric, how_many, minimum=False):
    sorted_df = df.sort_values([metric], ascending=minimum)
    return sorted_df.iloc[0:how_many]


def count_plot_horizontal(df, time, count_over, filename=None):
    smaller_df = df[[time, count_over]]

    ax = sns.countplot(y=time, hue=count_over, data=smaller_df)
    ax.set_title('Evolving frequencies of {} over {}'.format(count_over, time))
    fig = plt.gcf()
    if filename:
        fig.savefig(filename, format='pdf', dpi=1200)
    else:
        plt.show()
    plt.close(fig)


def detect_scale(arr):
    array = arr[~np.isnan(arr)]
    data_points = len(array)
    bins = 2 + int(np.sqrt(data_points))

    log_space_data = np.log(np.abs(array) + 1e-8)

    norm_densities, _ = np.histogram(array, bins=bins)
    log_densities, _ = np.histogram(log_space_data, bins=bins)

    if np.std(norm_densities) < np.std(log_densities):
        return 'linear'
    elif min(array) > 0:
        return 'log'
    else:
        return 'symlog'


def plot_opt_progress(df, metric, filename=None):
    fig = plt.figure()
    ax = sns.boxplot(x=ITERATION, y=metric, data=df)
    ax.set_yscale(detect_scale(df[metric]))
    plt.title('Optimization progress')

    if filename:
        fig.savefig(filename, format='pdf', dpi=1200)
    else:
        plt.show()
    plt.close(fig)
    return True


def turn_categorical_to_numerical(df, params):
    res = df.copy()
    non_numerical = [col for col in params if not np.issubdtype(df[col].dtype, np.number)]

    for non_num in non_numerical:
        res[non_num], _ = pd.factorize(res[non_num])

    return res


class Normalizer:
    def __init__(self, params):
        self.means = None
        self.stds = None
        self.params = params

    def __call__(self, df):
        if self.means is None or self.stds is None:
            self.means = df[self.params].mean()
            self.stds = df[self.params].std()
        res = df.copy()
        res[self.params] = (df[self.params] - self.means) / (self.stds + 1e-8)
        return res


def fit_forest(df, params, metric):
    data = df[params + [metric]]
    clf = RandomForestRegressor(n_estimators=1000)

    x = data[params]  # Features
    y = data[metric]  # Labels

    clf.fit(x, y)
    return clf


def performance_gain_for_iteration(clf, df_for_iter, params, metric, minimum):
    df = df_for_iter.sort_values([metric], ascending=minimum)
    df = df[:-len(df) // 4]

    ys_base = df[metric]
    if df[params].shape[0] == 0:
        for param in params:
            yield 0
    else:
        ys = clf.predict(df[params])
        forest_error = np.mean(np.abs(ys_base - ys))

        for param in params:
            copy_df = df.copy()
            copy_df[param] = np.random.permutation(copy_df[param])
            ys = clf.predict(copy_df[params])
            diffs = ys - copy_df[metric]
            error = np.mean(np.abs(diffs))
            yield max(0, (error - forest_error) / np.sqrt(len(params)))


def compute_performance_gains(df, params, metric, minimum):
    df = turn_categorical_to_numerical(df, params)
    df = df.dropna(subset=[metric])
    normalize = Normalizer(params)

    forest = fit_forest(normalize(df), params, metric)

    max_iteration = df[ITERATION].max()
    dfs = [normalize(df[df[ITERATION] == 1 + i]) for i in range(max_iteration)]

    names = [f'iteration {1 + i}' for i in range(max_iteration)]
    importances = [list(performance_gain_for_iteration(forest, df_, params, metric, minimum)) for df_ in dfs]

    data_dict = dict(zip(names, list(importances)))
    feature_imp = pd.DataFrame.from_dict(data_dict)
    feature_imp.index = [shorten_string(param, 40) for param in params]
    return feature_imp


def importance_by_iteration_plot(df, params, metric, minimum, filename=None):
    importances = compute_performance_gains(df, params, metric, minimum)
    importances.T.plot(kind='bar', stacked=True, legend=False)
    lgd = plt.legend(loc='lower center', bbox_to_anchor=(0.5, -0.55), ncol=2)

    ax = plt.gca()
    fig = plt.gcf()
    ax.set_yscale(detect_scale(importances.mean().values))
    ax.set_ylabel(f'Potential change in {metric}')
    ax.set_title('Influence of hyperparameters on performance')
    if filename:
        fig.savefig(filename, format='pdf', dpi=1200, bbox_extra_artists=(lgd,), bbox_inches='tight')
    else:
        plt.show()
    plt.close(fig)
    return True


def metric_correlation_plot(df, metrics, filename=None):
    corr = df[list(metrics)].rank().corr(method='spearman')

    print(df[list(metrics)].rank())

    # Generate a custom diverging colormap
    cmap = sns.diverging_palette(10, 150, as_cmap=True)

    # Draw the heatmap with the mask and correct aspect ratio
    ax = sns.heatmap(corr, cmap=cmap, vmin=-1.0, vmax=1.0, center=0,
                square=True, linewidths=.5, cbar_kws={"shrink": .5})
    plt.xticks(rotation=90)

    ax.set_title('Spearman correlation of metrics')
    ax.figure.tight_layout()
    fig = plt.gcf()

    if filename:
        fig.savefig(filename, format='pdf', dpi=1200)
    else:
        plt.show()
    plt.close(fig)
    return True
