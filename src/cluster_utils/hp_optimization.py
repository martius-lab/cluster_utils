"""Run hyperparameter optimization.

Test various hyperparameter configurations using an iterative optimization method to
sample the values of the hyperparameters.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from cluster_utils.base.utils import OptionalDependencyImport

with OptionalDependencyImport("runner"):
    from cluster_utils.server import distributions, latex_utils
    from cluster_utils.server.git_utils import make_git_params
    from cluster_utils.server.job_manager import hp_optimization
    from cluster_utils.server.settings import (
        GenerateReportSetting,
        SingularitySettings,
        init_main_script_argument_parser,
        read_main_script_params_from_args,
    )
    from cluster_utils.server.utils import (
        get_time_string,
        make_temporary_dir,
    )


def get_distribution(distribution, **kwargs):
    distr_dict = {
        "TruncatedNormal": distributions.TruncatedNormal,
        "TruncatedLogNormal": distributions.TruncatedLogNormal,
        "IntNormal": distributions.IntNormal,
        "IntLogNormal": distributions.IntLogNormal,
        "Discrete": distributions.Discrete,
    }

    if distribution not in distr_dict:
        raise NotImplementedError(f"Distribution {distribution} does not exist")

    if distribution == "Discrete" and "bounds" in kwargs:
        print(
            "Change 'bounds' to 'options' for a Discrete distribution!! Trying to"
            " continue..."
        )
        kwargs["options"] = kwargs.pop("bounds")

    if distribution != "Discrete" and "options" in kwargs:
        print(
            "Change 'options' to 'bounds' to options for a"
            f" {distribution} distribution!! Trying to continue..."
        )
        kwargs["bounds"] = kwargs.pop("options")
    return distr_dict[distribution](**kwargs)


def main() -> int:
    parser = init_main_script_argument_parser(description=__doc__)
    args = parser.parse_args()
    try:
        params = read_main_script_params_from_args(args)
    except Exception as e:
        print(f"Error while reading parameters: {e}", file=sys.stderr)
        return 1

    if params["generate_report"] is not GenerateReportSetting.NEVER:
        # conditional import as it depends on optional dependencies (not used here but
        # already import to fail early in case dependencies are missing)
        import cluster_utils.server.report  # noqa:F401

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

    base_paths_and_files: dict[str, str] = dict(
        main_path=main_path,
        script_to_run=params.script_relative_path,
        result_dir=results_path,
        jobs_dir=jobs_path,
        **params.environment_setup,
    )

    distribution_list = [get_distribution(**item) for item in params.optimized_params]

    json_hook = latex_utils.SectionFromJsonHook(
        section_title="Optimization setting script",
        section_generator=latex_utils.StaticSectionGenerator(json_full_name),
    )

    singularity_settings = (
        SingularitySettings.from_settings(params["singularity"])
        if "singularity" in params
        else None
    )

    hp_optimization(
        base_paths_and_files=base_paths_and_files,
        submission_requirements=params.cluster_requirements,
        optimized_params=distribution_list,
        other_params=params.fixed_params,
        optimizer_str=params.optimizer_str,
        remove_jobs_dir=params.get("remove_jobs_dir", True),
        remove_working_dirs=params.get("remove_working_dirs", True),
        git_params=git_params,
        report_hooks=[json_hook],
        num_best_jobs_whose_data_is_kept=params.num_best_jobs_whose_data_is_kept,
        optimizer_settings=params.optimizer_settings,
        kill_bad_jobs_early=params.get("kill_bad_jobs_early", False),
        early_killing_params=params.get("early_killing_params", {}),
        no_user_interaction=params.get("no_user_interaction", False),
        opt_procedure_name=opt_procedure_name,
        report_generation_mode=params["generate_report"],
        singularity_settings=singularity_settings,
        **params.optimization_setting,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
