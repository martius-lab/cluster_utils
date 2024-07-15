from __future__ import annotations

import logging
from typing import List

import numpy as np
import pandas as pd

from cluster_utils.base import constants

DISTR_BASE_COLORS = [
    (0.99, 0.7, 0.18),
    (0.7, 0.7, 0.9),
    (0.56, 0.692, 0.195),
    (0.923, 0.386, 0.209),
]


def performance_summary(df, metrics):
    perf = {}
    for metric in metrics:
        min_val = df[metric].min()
        max_val = df[metric].max()
        mean_val = df[metric].mean()
        std_val = df[metric].std()
        perf[metric] = {
            "min": min_val,
            "max": max_val,
            "mean": mean_val,
            "stddev": std_val,
        }

    return pd.DataFrame.from_dict(perf, orient="index")


def average_out(
    df: pd.DataFrame,
    metrics: List[str],
    params_to_keep: List[str],
    /,
    sort_ascending: bool,
    std_ending: str = constants.STD_ENDING,
    add_std: bool = True,
) -> pd.DataFrame:
    """Compute mean metric values over runs that used the same parameters.

    Args:
        df: Data of the runs including parameters and results.
        metrics: Column names in df that contain result values (the ones to be
            averaged).
        params_to_keep: Parameters by which the runs are grouped (i.e. average is
            computed over all runs with identical values on these parameters).
        sort_ascending: The resulting DataFrame will be sorted by the values of
            ``metric``.  This argument specifies whether it should be sorted ascending
            (True) or descending (False).
        std_ending: Suffix that is appended to the metric column names when adding
            standard deviations.
        add_std: Whether to add columns with the standard deviations of metric columns.

    Returns:
        DataFrame with columns params_to_keep and mean (and optionally std) values of
        metrics.
    """
    logger = logging.getLogger("cluster_utils")
    if not metrics:
        raise ValueError("Empty set of metrics not accepted.")
    new_df = df[params_to_keep + metrics]
    result = new_df.groupby(params_to_keep, as_index=False).agg("mean")
    result[constants.RESTART_PARAM_NAME] = new_df.groupby(
        params_to_keep, as_index=False
    ).agg({metrics[0]: "size"})[metrics[0]]
    if not add_std:
        return result
    for metric in metrics:
        std_name = metric + std_ending
        if std_name in result.columns:
            logger.warning("Name %s already used. Skipping ...", std_name)
        else:
            result[std_name] = new_df.groupby(params_to_keep, as_index=False).agg(
                {metric: "std"}
            )[metric]

    # sort the result
    result = result.sort_values(metrics, ascending=sort_ascending)

    return result


def darker(color, factor=0.85):
    if color is None:
        return None
    r, g, b = color
    return (r * factor, g * factor, b * factor)


def color_scheme():
    while True:
        for color in DISTR_BASE_COLORS:
            for _ in range(5):
                yield color
                color = darker(color)


def best_params(df, params, metric, how_many, minimum=False):
    df_sorted = df.sort_values([metric], ascending=minimum)
    best_params = df_sorted[params].iloc[0:how_many].to_dict()
    return {key: list(value.values()) for key, value in best_params.items()}


def best_jobs(df, metric, how_many, minimum=False):
    sorted_df = df.sort_values([metric], ascending=minimum)
    return sorted_df.iloc[0:how_many]


def detect_scale(arr):
    array = arr[~np.isnan(arr)]
    data_points = len(array)
    bins = 2 + int(np.sqrt(data_points))

    log_space_data = np.log(np.abs(array) + 1e-8)

    norm_densities, _ = np.histogram(array, bins=bins)
    log_densities, _ = np.histogram(log_space_data, bins=bins)

    if np.std(norm_densities) < np.std(log_densities):
        return "linear"
    elif min(array) > 0:
        return "log"
    else:
        return "symlog"


def turn_categorical_to_numerical(df, params):
    res = df.copy()
    non_numerical = [
        col for col in params if not np.issubdtype(df[col].dtype, np.number)
    ]

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


def performance_gain_for_iteration(clf, df_for_iter, params, metric, minimum):
    df = df_for_iter.sort_values([metric], ascending=minimum)
    df = df[: -len(df) // 4]

    ys_base = df[metric]
    if df[params].shape[0] == 0:
        for _ in params:
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
