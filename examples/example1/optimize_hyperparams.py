import os
from pathlib2 import Path

from cluster import hyperparameter_optimization, init_plotting
from cluster.distributions import *
from cluster.latex_utils import *
from cluster.utils import mkdtemp

home = str(Path.home())

init_plotting()

opt_procedure_name = 'dummy12'

optimizer_str = 'cem_metaoptimizer'
optimizer_settings = {'with_restarts': True,
                      'best_fraction_to_use_for_update': 0.15}

project_path = mkdtemp(suffix=opt_procedure_name + '-' + 'project')
results_path = os.path.join(home, 'experiments/results')
jobs_path = mkdtemp(suffix=opt_procedure_name + '-' + 'jobs')

git_params = dict(url='git@gitlab.tuebingen.mpg.de:mrolinek/cluster_utils.git',
                  local_path=project_path,
                  branch='socket_based_communication',
                  )

base_paths_and_files = dict(script_to_run=os.path.join(project_path, 'examples/example1/main.py'),
                            result_dir=os.path.join(results_path, opt_procedure_name),
                            jobs_dir=jobs_path)

submission_requirements = dict(request_cpus=1,
                               request_gpus=0,
                               cuda_requirement=None,  # 'x.0' or None (GPU only)
                               memory_in_mb=4000,
                               bid=2000)

optimization_setting = dict(metric_to_optimize='result',
                            number_of_samples=50,
                            fraction_that_need_to_finish=0.9,
                            total_rounds=15,
                            remove_jobs_dir=False,
                            minimize=True)

other_params = {'w': 5.0}

optimized_params = [TruncatedNormal(param='u', bounds=(-3.0, 3.0)),
                     TruncatedNormal(param='v', bounds=(-3.0, 3.0)),
                     TruncatedNormal(param='x', bounds=(-3.0, 4.0)),
                     TruncatedNormal(param='y', bounds=(-3.0, 3.0)),
                     TruncatedNormal(param='z', bounds=(-3.0, 3.0)),
                     Discrete(param='flag', options=[False, True])
                     ]

def find_json(df, path_to_results, filename_generator):
    return '/is/sg/mrolinek/Projects/mbrl/optimization_scripts/gym/halfcheetah/mpc_opt_script.json'



#json_hook = SectionFromJsonHook(section_title='Random script', section_generator=find_json)
hyperparameter_optimization(base_paths_and_files=base_paths_and_files,
                            submission_requirements=submission_requirements,
                            optimizer_str=optimizer_str,
                            optimizer_settings=optimizer_settings,
                            optimized_params=optimized_params,
                            other_params=other_params,
                            git_params=git_params,
                            num_best_jobs_whose_data_is_kept=5,
                            report_hooks=None,#[json_hook],
                            run_local=True,
                            **optimization_setting)
