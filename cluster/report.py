from __future__ import annotations

import datetime
import logging
import os
from itertools import combinations, count
from tempfile import TemporaryDirectory
from typing import Any, Iterator, Mapping, NamedTuple, Sequence

import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import rc

from cluster import constants, data_analysis, distributions
from cluster.latex_utils import LatexFile, SectionHook
from cluster.utils import log_and_print, shorten_string


def init_plotting():
    sns.set_style("darkgrid", {"legend.frameon": True})
    font = {
        "family": "sans-serif",
        "serif": "Ubuntu",
        "weight": "bold",
        "monospace": "Ubuntu Mono",
    }

    rc("font", **font)


def flatten_params(params_with_tuples):
    for p in params_with_tuples:
        if isinstance(p, tuple):
            for i in p:
                yield i
        else:
            yield p


def produce_basic_report(
    df,
    params,
    metrics,
    procedure_name,
    output_file,
    submission_hook_stats=None,
    maximized_metrics=None,
    report_hooks=None,
):
    logger = logging.getLogger("cluster_utils")
    log_and_print(logger, "Producing basic report... ")
    maximized_metrics = maximized_metrics or []
    report_hooks = report_hooks or []

    today = datetime.datetime.now().strftime("%B %d, %Y")
    latex_title = "Cluster job '{}' results ({})".format(procedure_name, today)
    latex = LatexFile(title=latex_title)

    if (
        "GitConnector" in submission_hook_stats
        and submission_hook_stats["GitConnector"]
    ):
        latex.add_generic_section(
            "Git Meta Information", content=submission_hook_stats["GitConnector"]
        )

    summary_df = data_analysis.performance_summary(df, metrics)
    latex.add_section_from_dataframe("Summary of results", summary_df)

    # flatten param-lists if they exist
    params = list(flatten_params(params))

    for metric in metrics:
        best_runs_df = data_analysis.best_jobs(
            df[params + [metric]], metric, 10, minimum=(metric not in maximized_metrics)
        )
        latex.add_section_from_dataframe(
            "Jobs with best result in '{}'".format(metric), best_runs_df
        )

    def filename_gen(base_path):
        for num in count():
            yield os.path.join(base_path, "{}.pdf".format(num))

    with TemporaryDirectory() as tmpdir:
        file_gen = filename_gen(tmpdir)

        correlation_file = next(file_gen)
        data_analysis.metric_correlation_plot(df, metrics, correlation_file)
        latex.add_section_from_figures(
            "Metric Spearman Correlation", [correlation_file]
        )

        for metric in metrics:
            distr_files = [next(file_gen) for param in params]
            distr_files = [
                fname
                for fname, param in zip(distr_files, params)
                if data_analysis.distribution(df, param, metric, fname)
            ]

            section_name = "Distributions of '{}' w.r.t. parameters".format(metric)
            latex.add_section_from_figures(section_name, distr_files)

            heat_map_files = []
            for param1, param2 in combinations(params, 2):
                filename = next(file_gen)
                data_analysis.heat_map(df, param1, param2, metric, filename, annot=True)
                heat_map_files.append(filename)

            section_name = "Heatmaps of {} w.r.t. parameters".format(metric)
            latex.add_section_from_figures(section_name, heat_map_files)

        hook_args = dict(df=df, path_to_results=None)

        for hook in report_hooks:
            hook.write_section(latex, file_gen, hook_args)
        logger.info("Calling pdflatex on prepared report")
        try:
            latex.produce_pdf(output_file)
            log_and_print(logger, f"Report saved at {output_file}")
        except Exception:
            logging.warning("Could not generate PDF report", exc_info=True)


class OptimizationConfig(NamedTuple):
    """Optimization parameters that are relevant for generating the report."""

    parameters: Sequence[distributions.Distribution]
    metric_to_optimize: str
    minimize: bool
    with_restarts: bool
    minimal_restarts_to_count: int


def distribution_plots(
    full_data: pd.DataFrame,
    optimized_params: Sequence[distributions.Distribution],
    filename_generator: Iterator[str],
) -> Iterator[str]:
    """Generator to iteratively create distribution plots for the given parameters.

    The plots are saved to PDF files, using the given filename_generator for determining
    the file names.

    Args:
        full_df:  DataFrame with data of all runs.
        optimized_params:  Sequence of Distribution instances (containing parameter
            names).  Only distribution types
            :class:`~distributions.NumericalDistribution` and
            :class:`distributions.Discrete` are supported.
        filename_generator:  Generator to create names for temporary files.

    Raises:
        TypeError:  if a distribution of an unsupported type is given.

    Yields:
        Filename of the generated plot.
    """
    for distr in optimized_params:
        filename = next(filename_generator)
        if isinstance(distr, distributions.NumericalDistribution):
            log_scale = isinstance(distr, distributions.TruncatedLogNormal)
            res = data_analysis.distribution(
                full_data,
                constants.ITERATION,
                distr.param_name,
                filename=filename,
                metric_logscale=log_scale,
                x_bounds=(distr.lower, distr.upper),
            )
            if res:
                yield filename
        elif isinstance(distr, distributions.Discrete):
            data_analysis.count_plot_horizontal(
                full_data,
                constants.ITERATION,
                distr.param_name,
                filename=filename,
            )
            yield filename
        else:
            raise TypeError(f"Distribution of type {type(distr)} is not supported.")


def provide_recommendations(
    minimal_df: pd.DataFrame,
    config: OptimizationConfig,
    how_many: int,
) -> pd.DataFrame:
    num_restarts = minimal_df[constants.RESTART_PARAM_NAME]
    jobs_df = minimal_df[num_restarts >= config.minimal_restarts_to_count].copy()

    metric_std = config.metric_to_optimize + constants.STD_ENDING
    final_metric = f"expected {config.metric_to_optimize}"
    if config.with_restarts and config.minimal_restarts_to_count > 1:
        sign = -1.0 if config.minimize else 1.0
        mean, std = jobs_df[config.metric_to_optimize], jobs_df[metric_std]
        median_std = jobs_df[metric_std].median()

        num_restarts = jobs_df[constants.RESTART_PARAM_NAME]
        # pessimistic estimate mean - std/sqrt(samples), based on Central Limit Theorem
        expected_metric = mean - (
            sign * (np.maximum(std, median_std)) / np.sqrt(num_restarts)
        )
        jobs_df[final_metric] = expected_metric
    else:
        jobs_df[final_metric] = jobs_df[config.metric_to_optimize]

    best_jobs_df = jobs_df.sort_values([final_metric], ascending=config.minimize)[
        :how_many
    ].reset_index()
    del best_jobs_df[metric_std]
    del best_jobs_df[config.metric_to_optimize]
    del best_jobs_df[constants.RESTART_PARAM_NAME]
    del best_jobs_df["index"]

    best_jobs_df.index += 1
    best_jobs_df[final_metric] = list(
        distributions.smart_round(best_jobs_df[final_metric])
    )

    best_jobs_df = best_jobs_df.transpose()
    best_jobs_df.index = pd.Index([shorten_string(el, 40) for el in best_jobs_df.index])
    return best_jobs_df


def produce_optimization_report(
    full_data: pd.DataFrame,
    config: OptimizationConfig,
    report_hooks: Sequence[SectionHook],
    output_file: str,
    submission_hook_stats: Mapping[str, Any],
    current_result_path: str | os.PathLike,
) -> None:
    """Produce PDF report for a ``hp_optimization`` run.

    Args:
        full_data:  The full data of the optimization including parameters and results
            (one line per run).
        config:  Configuration of the optimisation procedure.
        report_hooks:  Section hooks to add additional content to the report.
        output_file:  Where to save the report.
        submission_hook_stats:  Hooks to add submission-specific information (only an
            entry with key "GitConnector" is used if present).
        current_result_path:  Path to the output files of the optimization.
    """
    today = datetime.datetime.now().strftime("%B %d, %Y")
    latex_title = "Results of optimization procedure from ({})".format(today)
    latex = LatexFile(latex_title)

    params = [param.param_name for param in config.parameters]

    if (
        "GitConnector" in submission_hook_stats
        and submission_hook_stats["GitConnector"]
    ):
        latex.add_generic_section(
            "Git Meta Information", content=submission_hook_stats["GitConnector"]
        )

    def filename_gen(base_path: str | os.PathLike) -> Iterator[str]:
        for num in count():
            yield os.path.join(base_path, "{}.pdf".format(num))

    with TemporaryDirectory() as tmpdir:
        file_gen = filename_gen(tmpdir)
        hook_args = {"df": full_data, "path_to_results": current_result_path}
        overall_progress_file = next(file_gen)
        data_analysis.plot_opt_progress(
            full_data, config.metric_to_optimize, overall_progress_file
        )

        sensitivity_file = next(file_gen)
        data_analysis.importance_by_iteration_plot(
            full_data,
            params,
            config.metric_to_optimize,
            config.minimize,
            sensitivity_file,
        )

        minimal_df = data_analysis.average_out(
            full_data,
            [config.metric_to_optimize],
            params,
            sort_ascending=config.minimize,
        )

        distr_plot_files = distribution_plots(full_data, config.parameters, file_gen)

        latex.add_section_from_figures(
            "Overall progress", [overall_progress_file], common_scale=1.2
        )
        latex.add_section_from_dataframe(
            "Top 5 recommendations",
            provide_recommendations(
                minimal_df,
                config,
                how_many=5,
            ),
        )
        latex.add_section_from_figures("Hyperparameter importance", [sensitivity_file])
        latex.add_section_from_figures("Distribution development", distr_plot_files)

        for hook in report_hooks:
            hook.write_section(latex, file_gen, hook_args)

        try:
            latex.produce_pdf(output_file)
        except Exception:
            logging.warning("Could not generate PDF report", exc_info=True)
