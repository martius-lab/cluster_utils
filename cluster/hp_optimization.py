import os
import sys
from pathlib import Path

from . import hp_optimization, init_plotting
from .distributions import *
from .git_utils import make_git_params
from .latex_utils import *
from .utils import mkdtemp
from . import update_params_from_cmdline


def get_distribution(distribution, **kwargs):
    distr_dict = {
        "TruncatedNormal": TruncatedNormal,
        "TruncatedLogNormal": TruncatedLogNormal,
        "IntNormal": IntNormal,
        "IntLogNormal": IntLogNormal,
        "Discrete": Discrete,
    }

    if distribution not in distr_dict:
        raise NotImplementedError(f"Distribution {distribution} does not exist")

    if distribution == 'Discrete' and "bounds" in kwargs:
        print("Change \'bounds\' to \'options\' for a Discrete distribution!! Trying to continue...")
        kwargs["options"] = kwargs.pop("bounds")

    if distribution != 'Discrete' and "options" in kwargs:
        print(f"Change \'options\' to \'bounds\' to options for a {distribution} distribution!! Trying to continue...")
        kwargs["bounds"] = kwargs.pop("options")
    return distr_dict[distribution](**kwargs)


if __name__ == '__main__':
    params = update_params_from_cmdline(verbose=False)

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

    distribution_list = [get_distribution(**item) for item in params.optimized_params]

    # noinspection PyUnusedLocal
    def find_json(df, path_to_results, filename_generator):
        return json_full_name

    json_hook = SectionFromJsonHook(section_title="Optimization setting script", section_generator=find_json)

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
        kill_bad_jobs_early=params.get('kill_bad_jobs_early', False),
        early_killing_params=params.get('early_killing_params', {}),
        **params.optimization_setting,
    )
