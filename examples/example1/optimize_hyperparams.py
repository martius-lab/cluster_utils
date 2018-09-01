import os
from pathlib2 import Path

from cluster import hyperparameter_optimization, init_plotting
from cluster.distributions import *
from cluster.utils import mkdtemp

home = str(Path.home())

init_plotting()

opt_procedure_name = 'presentation'

project_path = mkdtemp(suffix=opt_procedure_name + '-' + 'project')
results_path = os.path.join(home, 'experiments/results')
jobs_path = mkdtemp(suffix=opt_procedure_name + '-' + 'jobs')

git_params = dict(url='git@gitlab.tuebingen.mpg.de:mrolinek/cluster_utils.git',
                  local_path=project_path,
                  branch='git_integration',
                  commit=None,
                  )

base_paths_and_files = dict(script_to_run=os.path.join(project_path, 'examples/example1/main.py'),
                            result_dir=os.path.join(results_path, opt_procedure_name),
                            jobs_dir=jobs_path)

submission_requirements = dict(request_cpus=1,
                               request_gpus=0,
                               cuda_requirement=None,  # 'x.0' or None (GPU only)
                               memory_in_mb=4000,
                               bid=10)

optimization_setting = dict(metric_to_optimize='result',
                            number_of_samples=100,
                            number_of_restarts=2,
                            fraction_that_need_to_finish=0.9,
                            best_fraction_to_use_for_update=0.2,
                            total_rounds=12,
                            minimize=True)

other_params = {}

distribution_list = [TruncatedNormal(param='u', bounds=(-3.0, 3.0)),
                     TruncatedNormal(param='v', bounds=(-3.0, 3.0)),
                     TruncatedNormal(param='w', bounds=(-3.0, 3.0)),
                     TruncatedNormal(param='x', bounds=(-3.0, 3.0)),
                     TruncatedNormal(param='y', bounds=(-3.0, 3.0)),
                     TruncatedNormal(param='z', bounds=(-3.0, 3.0)),
                     ]

hyperparameter_optimization(base_paths_and_files=base_paths_and_files,
                            submission_requirements=submission_requirements,
                            distribution_list=distribution_list,
                            other_params=other_params,
                            git_params=git_params,
                            **optimization_setting)
