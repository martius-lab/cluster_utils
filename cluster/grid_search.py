import logging
import os
import sys
from collections import Counter
from pathlib import Path

from cluster import update_params_from_cmdline
from cluster.latex_utils import SectionFromJsonHook
from cluster.report import produce_basic_report, init_plotting
from cluster.git_utils import make_git_params
from cluster.utils import mkdtemp, check_import_in_fixed_params, rename_import_promise
from . import grid_search

if __name__ == '__main__':
    params = update_params_from_cmdline(verbose=False, pre_unpack_hooks=[check_import_in_fixed_params],
                                        post_unpack_hooks=[rename_import_promise])

    json_full_name = os.path.abspath(sys.argv[1])
    init_plotting()

    opt_procedure_name = params.optimization_procedure_name

    home = str(Path.home())
    results_path = os.path.join(home, params.results_dir, opt_procedure_name)
    jobs_path = mkdtemp(suffix=f"{opt_procedure_name}-jobs")

    run_in_working_dir = params.get("run_in_working_dir", False)
    if not run_in_working_dir:
        main_path = mkdtemp(suffix=f"{opt_procedure_name}-project")
        git_params = make_git_params(params.get('git_params'), main_path)
    else:
        main_path = os.getcwd()
        git_params = None

    base_paths_and_files = dict(
        main_path=main_path,
        script_to_run=params.script_relative_path,
        result_dir=results_path,
        jobs_dir=jobs_path,
        **params.environment_setup
    )

    class DummyDistribution():
        def __init__(self, param, values):
            self.param_name = tuple(param) if isinstance(param, list) else param
            self.values = values

    hyperparam_dict = [DummyDistribution(hyperparam["param"], hyperparam["values"]) for hyperparam in
                       params.hyperparam_list]
    hyperparam_names = [dummy_dist.param_name for dummy_dist in hyperparam_dict]

    num_duplicates = Counter(hyperparam_names)
    if num_duplicates and max(num_duplicates.values()) > 1:
        raise ValueError(f"There we duplicate entries in the list of hyperparameters e.g. {num_duplicates.most_common}")

    df, all_params, metrics, submission_hook_stats = grid_search(
        base_paths_and_files=base_paths_and_files,
        submission_requirements=params.cluster_requirements,
        optimized_params=hyperparam_dict,
        other_params=params.fixed_params,
        git_params=git_params,
        report_hooks=[],  # json_hook], TODO: Make this hook thing work again
        restarts=params.restarts,
        remove_jobs_dir=params.get("remove_jobs_dir", True),
        remove_working_dirs=params.get("remove_working_dirs", False),
        load_existing_results=params.get("load_existing_results", False),
        run_local=params.get("local_run", None)
    )

    if df is None:
        logger = logging.getLogger('cluster_utils')
        logger.warning(('Exiting without report because no job results are '
                        'available. Either the jobs did not exit properly, or '
                        'you forgot to call `save_metric_params`.'))
        sys.exit()

    df.to_csv(os.path.join(base_paths_and_files["result_dir"], "results_raw.csv"))

    relevant_params = [param.param_name for param in hyperparam_dict]
    output_pdf = os.path.join(base_paths_and_files["result_dir"], f"{params.optimization_procedure_name}_report.pdf")

    # noinspection PyUnusedLocal

    def find_json(df, path_to_results, filename_generator):
        return json_full_name

    json_hook = SectionFromJsonHook(section_title="Optimization setting script", section_generator=find_json)

    produce_basic_report(
        df,
        relevant_params,
        metrics,
        submission_hook_stats=submission_hook_stats,
        procedure_name=params.optimization_procedure_name,
        output_file=output_pdf,
        report_hooks=[json_hook]
    )
