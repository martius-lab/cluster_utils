"""Run grid_search over hyperparameters."""

import logging
import os
import sys
from collections import Counter
from pathlib import Path

from cluster_utils.base.utils import OptionalDependencyImport

with OptionalDependencyImport("runner"):
    from cluster_utils.base.constants import FULL_DF_FILE
    from cluster_utils.server.git_utils import make_git_params
    from cluster_utils.server.job_manager import grid_search
    from cluster_utils.server.latex_utils import (
        SectionFromJsonHook,
        StaticSectionGenerator,
    )
    from cluster_utils.server.settings import (
        GenerateReportSetting,
        SingularitySettings,
        init_main_script_argument_parser,
        read_main_script_params_from_args,
    )
    from cluster_utils.server.utils import (
        get_time_string,
        make_temporary_dir,
        save_report_data,
    )


def main() -> int:
    parser = init_main_script_argument_parser(description=__doc__)
    args = parser.parse_args()
    try:
        params = read_main_script_params_from_args(args)
    except Exception as e:
        print(f"Error while reading parameters: {e}", file=sys.stderr)
        return 1

    logger = logging.getLogger("cluster_utils")

    # check parameters
    if params["generate_report"] == GenerateReportSetting.EVERY_ITERATION:
        logger.warning(
            "grid_search does not support setting generate_report='EVERY_ITERATION'. "
            " Will only create report when finished."
        )

    if params["generate_report"] is not GenerateReportSetting.NEVER:
        # conditional import as it depends on optional dependencies
        # (already import here to fail early in case dependencies are missing)
        from cluster_utils.server.report import produce_gridsearch_report

    json_full_name = os.path.abspath(sys.argv[1])

    opt_procedure_name = params.optimization_procedure_name

    home = str(Path.home())
    results_path = os.path.join(home, params.results_dir, opt_procedure_name)

    time = get_time_string()
    jobs_path = make_temporary_dir(f"{opt_procedure_name}-{time}-jobs")

    run_in_working_dir = params.get("run_in_working_dir", False)
    if not run_in_working_dir:
        main_path = make_temporary_dir(f"{opt_procedure_name}-{time}-project")
        git_params = make_git_params(params.get("git_params"), main_path)
    else:
        main_path = os.getcwd()
        git_params = None

    base_paths_and_files = dict(
        main_path=main_path,
        script_to_run=params.script_relative_path,
        result_dir=results_path,
        jobs_dir=jobs_path,
        **params.environment_setup,
    )

    class DummyDistribution:
        def __init__(self, param, values):
            self.param_name = tuple(param) if isinstance(param, list) else param
            self.values = values

    hyperparam_dict = [
        DummyDistribution(hyperparam["param"], hyperparam["values"])
        for hyperparam in params.hyperparam_list
    ]
    hyperparam_names = [dummy_dist.param_name for dummy_dist in hyperparam_dict]

    num_duplicates = Counter(hyperparam_names)
    if num_duplicates and max(num_duplicates.values()) > 1:
        raise ValueError(
            "There we duplicate entries in the list of hyperparameters e.g."
            f" {num_duplicates.most_common}"
        )

    singularity_settings = (
        SingularitySettings.from_settings(params["singularity"])
        if "singularity" in params
        else None
    )

    df, all_params, metrics, submission_hook_stats = grid_search(
        base_paths_and_files=base_paths_and_files,
        submission_requirements=params.cluster_requirements,
        optimized_params=hyperparam_dict,
        other_params=params.fixed_params,
        git_params=git_params,
        report_hooks=[],  # json_hook], TODO: Make this hook thing work again
        restarts=params.restarts,
        samples=params.get("samples", None),
        remove_jobs_dir=params.get("remove_jobs_dir", True),
        remove_working_dirs=params.get("remove_working_dirs", False),
        load_existing_results=params.get("load_existing_results", False),
        run_local=params.get("local_run", None),
        no_user_interaction=params.get("no_user_interaction", False),
        opt_procedure_name=opt_procedure_name,
        singularity_settings=singularity_settings,
    )

    if df is None:
        logger.error(
            "Exiting because no job results are available. Either the jobs did not exit"
            " properly, or you forgot to call `save_metric_params`."
        )
        return 1

    df.to_csv(os.path.join(base_paths_and_files["result_dir"], FULL_DF_FILE))

    relevant_params = [param.param_name for param in hyperparam_dict]
    output_pdf = os.path.join(
        base_paths_and_files["result_dir"],
        f"{params.optimization_procedure_name}_report.pdf",
    )

    json_hook = SectionFromJsonHook(
        section_title="Optimization setting script",
        section_generator=StaticSectionGenerator(json_full_name),
    )

    # save further data that is needed for offline report generation
    save_report_data(
        base_paths_and_files["result_dir"],
        params=relevant_params,
        metrics=metrics,
        submission_hook_stats=submission_hook_stats,
        procedure_name=params.optimization_procedure_name,
        report_hooks=[json_hook],
    )

    if params["generate_report"] is not GenerateReportSetting.NEVER:
        produce_gridsearch_report(
            df,
            relevant_params,
            metrics,
            submission_hook_stats=submission_hook_stats,
            procedure_name=params.optimization_procedure_name,
            output_file=output_pdf,
            report_hooks=[json_hook],
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
