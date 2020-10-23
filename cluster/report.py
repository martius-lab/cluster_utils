import datetime
import logging
import os
from itertools import combinations, count
from tempfile import TemporaryDirectory

import seaborn as sns
from matplotlib import rc

from cluster import data_analysis
from cluster.latex_utils import LatexFile
from cluster.utils import log_and_print


def init_plotting():
    sns.set_style("darkgrid", {'legend.frameon': True})
    font = {'family': 'sans-serif',
            'serif': 'Ubuntu',
            'weight': 'bold',
            'monospace': 'Ubuntu Mono'}

    rc('font', **font)


def flatten_params(params_with_tuples):
    for p in params_with_tuples:
        if isinstance(p,tuple):
            for i in p:
                yield i
        else:
            yield p


def produce_basic_report(df, params, metrics, procedure_name, output_file,
                         submission_hook_stats=None, maximized_metrics=None, report_hooks=None):
    logger = logging.getLogger('cluster_utils')
    log_and_print(logger, "Producing basic report... ")
    maximized_metrics = maximized_metrics or []
    report_hooks = report_hooks or []

    today = datetime.datetime.now().strftime("%B %d, %Y")
    latex_title = 'Cluster job \'{}\' results ({})'.format(procedure_name, today)
    latex = LatexFile(title=latex_title)

    if 'GitConnector' in submission_hook_stats and submission_hook_stats['GitConnector']:
        latex.add_generic_section('Git Meta Information', content=submission_hook_stats['GitConnector'])

    summary_df = data_analysis.performance_summary(df, metrics)
    latex.add_section_from_dataframe('Summary of results', summary_df)

    # flatten param-lists if they exist
    params = list(flatten_params(params))

    for metric in metrics:
        best_runs_df = data_analysis.best_jobs(df[params + [metric]], metric, 10,
                                               minimum=(metric not in maximized_metrics))
        latex.add_section_from_dataframe('Jobs with best result in \'{}\''.format(metric), best_runs_df)

    def filename_gen(base_path):
        for num in count():
            yield os.path.join(base_path, '{}.pdf'.format(num))

    with TemporaryDirectory() as tmpdir:
        file_gen = filename_gen(tmpdir)

        correlation_file = next(file_gen)
        data_analysis.metric_correlation_plot(df, metrics, correlation_file)
        latex.add_section_from_figures("Metric Spearman Correlation", [correlation_file])

        for metric in metrics:
            distr_files = [next(file_gen) for param in params]
            distr_files = [fname for fname, param in zip(distr_files, params)
                           if data_analysis.distribution(df, param, metric, fname)]

            section_name = 'Distributions of \'{}\' w.r.t. parameters'.format(metric)
            latex.add_section_from_figures(section_name, distr_files)

            heat_map_files = []
            for param1, param2 in combinations(params, 2):
                filename = next(file_gen)
                data_analysis.heat_map(df, param1, param2, metric, filename, annot=True)
                heat_map_files.append(filename)

            section_name = 'Heatmaps of {} w.r.t. parameters'.format(metric)
            latex.add_section_from_figures(section_name, heat_map_files)

        hook_args = dict(df=df, path_to_results=None)

        for hook in report_hooks:
            hook.write_section(latex, file_gen, hook_args)
        logger.info('Calling pdflatex on prepared report')
        latex.produce_pdf(output_file)
        log_and_print(logger, f'Report saved at {output_file}')
