from pathlib2 import Path
from . import hyperparameter_optimization, init_plotting
from .distributions import *
from .latex_utils import *
from .utils import mkdtemp
from . import update_params_from_cmdline
import sys
import git


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
    return distr_dict[distribution](**kwargs)


def get_git_url():
    try:
        repo = git.Repo(search_parent_directories=True)
    except git.exc.InvalidGitRepositoryError:
        return None

    url_list = list(repo.remotes.origin.urls)
    if url_list:
        print(f"Auto-detected git repository with remote url: {url_list[0]}")
        return url_list[0]

    return None


params = update_params_from_cmdline(verbose=False)

json_full_name = os.path.abspath(sys.argv[1])
init_plotting()

opt_procedure_name = params.optimization_procedure_name

home = str(Path.home())
main_path = mkdtemp(suffix=opt_procedure_name + "-" + "project")
results_path = os.path.join(home, params.results_dir, opt_procedure_name)
jobs_path = mkdtemp(suffix=opt_procedure_name + "-" + "jobs")


given_url = params.git_params.get("url")
if not given_url:
    auto_url = get_git_url()
    if not auto_url:
        raise git.exc.InvalidGitRepositoryError("No git repository given in json file or auto-detected")

    git_params = dict(url=auto_url, local_path=main_path, **params.git_params)

else:
    git_params = dict(local_path=main_path, **params.git_params)

base_paths_and_files = dict(
    script_to_run=os.path.join(main_path, params.script_relative_path),
    result_dir=results_path,
    jobs_dir=jobs_path,
    **params.environment_setup
)

distribution_list = [get_distribution(**item) for item in params.optimized_params]


# noinspection PyUnusedLocal
def find_json(df, path_to_results, filename_generator):
    return json_full_name


json_hook = SectionFromJsonHook(section_title="Optimization setting script", section_generator=find_json)

hyperparameter_optimization(
    base_paths_and_files=base_paths_and_files,
    submission_requirements=params.cluster_requirements,
    distribution_list=distribution_list,
    other_params=params.fixed_params,
    git_params=git_params,
    report_hooks=[json_hook],
    num_best_jobs_whose_data_is_kept=params.num_best_jobs_whose_data_is_kept,
    **params.optimization_setting,
)
