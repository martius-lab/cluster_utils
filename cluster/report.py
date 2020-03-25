import datetime
import logging
import os
from itertools import combinations
from itertools import count
from tempfile import TemporaryDirectory

from matplotlib import rc

from .data_analysis import *
from .latex_utils import LatexFile

logger = logging.getLogger('cluster_utils')

def init_plotting():
    sns.set_style("darkgrid", {'legend.frameon': True})
    font = {'family': 'sans-serif',
            'serif': 'Ubuntu',
            'weight': 'bold',
            'monospace': 'Ubuntu Mono'}

    rc('font', **font)


def produce_basic_report(df, params, metrics, procedure_name, output_file,
                         submission_hook_stats=None, maximized_metrics=None, log_scale_list=None, report_hooks=None):
    logger.info("Producing basic report... ")
    log_scale_list = log_scale_list or []
    maximized_metrics = maximized_metrics or []
    report_hooks = report_hooks or []

    today = datetime.datetime.now().strftime("%B %d, %Y")
    latex_title = 'Cluster job \'{}\' results ({})'.format(procedure_name, today)
    latex = LatexFile(title=latex_title)

    if 'GitConnector' in submission_hook_stats and submission_hook_stats['GitConnector']:
        latex.add_generic_section('Git Meta Information', content=submission_hook_stats['GitConnector'])

    summary_df = performance_summary(df, metrics)
    latex.add_section_from_dataframe('Summary of results', summary_df)

    for metric in metrics:
        best_runs_df = best_jobs(df[params + [metric]], metric, 10, minimum=(metric not in maximized_metrics))
        latex.add_section_from_dataframe('Jobs with best result in \'{}\''.format(metric), best_runs_df)

    def filename_gen(base_path):
        for num in count():
            yield os.path.join(base_path, '{}.pdf'.format(num))

    with TemporaryDirectory() as tmpdir:
        file_gen = filename_gen(tmpdir)

        for metric in metrics:
            distr_files = [next(file_gen) for param in params]

            distr_files = [fname for fname, param in zip(distr_files, params) if
                           distribution(df, param, metric, fname, metric_logscale=(metric in log_scale_list))]

            section_name = 'Distributions of \'{}\' w.r.t. parameters'.format(metric)
            latex.add_section_from_figures(section_name, distr_files)

            heat_map_files = []
            for param1, param2 in combinations(params, 2):
                filename = next(file_gen)
                heat_map(df, param1, param2, metric, filename)
                heat_map_files.append(filename)

            section_name = 'Heatmaps of {} w.r.t. parameters'.format(metric)
            latex.add_section_from_figures(section_name, heat_map_files)

        hook_args = dict(df=df, path_to_results=None)

        for hook in report_hooks:
            hook.write_section(latex, file_gen, hook_args)
        logger.info('Calling pdflatex on prepared report')
        latex.produce_pdf(output_file)
        logger.info(f'Report saved at {output_file}')
