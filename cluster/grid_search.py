import os
import shutil
import sys
from collections import Counter

import git
from cluster.latex_utils import SectionFromJsonHook
from pathlib2 import Path

from cluster import update_params_from_cmdline
from cluster.report import produce_basic_report, init_plotting
from cluster.utils import mkdtemp, get_git_url
from . import grid_search

if __name__ == '__main__':

    init_plotting()

    params = update_params_from_cmdline(verbose=False)

    json_full_name = os.path.abspath(sys.argv[1])
    home = str(Path.home())

    main_path = mkdtemp(suffix=f"{params.optimization_procedure_name}-project")
    results_path = os.path.join(home, params.results_dir, params.optimization_procedure_name)
    jobs_path = mkdtemp(suffix=f"{params.optimization_procedure_name}-jobs")

    given_url = params.git_params.get("url")
    if not given_url:
        auto_url = get_git_url()
        if not auto_url:
            raise git.exc.InvalidGitRepositoryError("No git repository given in json file or auto-detected")

        git_params = dict(url=auto_url, local_path=main_path, **params.git_params)

    else:
        git_params = dict(local_path=main_path, **params.git_params)

    base_paths_and_files = dict(
        main_path=main_path,
        script_to_run=params.script_relative_path,
        result_dir=results_path,
        jobs_dir=jobs_path,
        **params.environment_setup
    )

    class DummyDistribution():
        def __init__(self, param, values):
            self.param_name = param
            self.values = values

    hyperparam_dict = [DummyDistribution(hyperparam["param"], hyperparam["values"]) for hyperparam in
                       params.hyperparam_list]

    hyperparam_names = [hyperparam["param"] for hyperparam in params.hyperparam_list]
    num_duplicates = Counter(hyperparam_names)
    if max(num_duplicates.values()) > 1:
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
        load_existing_results=params.get("load_existing_results", False)
    )

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
