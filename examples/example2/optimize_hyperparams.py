import os

from cluster import hyperparameter_optimization, init_plotting
from cluster.distributions import *

init_plotting()

opt_procedure_name = 'mnist_opt'
main_path = '/is/sg/mrolinek/Projects/Cluster_utils/examples/example2'

base_paths_and_files = dict(script_to_run=os.path.join(main_path, 'main.py'),
                            result_dir=os.path.join(main_path, 'results', 'cluster', opt_procedure_name),
                            jobs_dir=os.path.join(main_path, 'jobs', opt_procedure_name))

submission_requirements = dict(request_cpus=4,
                               request_gpus=0,
                               cuda_requirement=None,  # 'x.0' or None (GPU only)
                               memory_in_mb=4000,
                               bid=10)

optimization_setting = dict(metric_to_optimize='RFC Score',
                            number_of_samples=4,
                            number_of_restarts=1,
                            fraction_that_need_to_finish=0.9,
                            best_fraction_to_use_for_update=0.2,
                            total_rounds=10,
                            minimize=False)

other_params = {'dataset': 'MNIST'}

distribution_list = [IntLogNormal(param='random_forest_args.n_estimators', bounds=(80, 500)),
                     Discrete(param='random_forest_args.criterion', options=['gini', 'entropy']),
                     TruncatedNormal(param='random_forest_args.max_features', bounds=(0.0, 1.0)),
                     IntNormal(param='random_forest_args.max_depth', bounds=(10, 50)),
                     Discrete(param='bootstrap', options=[True, False]),
                     Discrete(param='oob_score', options=[True, False])
                     ]

hyperparameter_optimization(base_paths_and_files=base_paths_and_files,
                            submission_requirements=submission_requirements,
                            distribution_list=distribution_list,
                            other_params=other_params,
                            **optimization_setting)
