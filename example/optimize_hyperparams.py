import os
import sys

#sys.path = ['/is/sg/mrolinek/Projects/Cluster_utils'] + sys.path

from cluster.distributions import *
from cluster import hyperparameter_optimization

opt_procedure_name = 'opt_new'
main_path = '/is/sg/mrolinek/Projects/Cluster_utils/example'

base_paths_and_files = dict(project_dir=main_path,
                            main_python_script=os.path.join(main_path, 'dummy.py'),
                            result_dir=os.path.join(main_path, 'results', 'cluster', opt_procedure_name),
                            jobs_dir=os.path.join(main_path, 'jobs', opt_procedure_name))

submission_requirements = dict(request_cpus=1,
                               request_gpus=0,
                               cuda_requirement=None,  # 'x.0' or None (GPU only)
                               memory_in_mb=4000,
                               bid=10)

optimization_setting = dict(metric_to_optimize='result',
                            number_of_samples=40,
                            number_of_restarts=1,
                            percentage_that_need_to_finish=0.9,
                            percentage_of_best=0.1,
                            total_rounds=6,
                            check_every_secs=20)

other_params = {}

distribution_list = [TruncatedNormal(param='x', bounds=(-5.0, 5.0)),
                     TruncatedNormal(param='y', bounds=(-5.0, 5.0)),
                     TruncatedNormal(param='z', bounds=(-5.0, 5.0)),
                     TruncatedNormal(param='w', bounds=(-5.0, 5.0)),
                     Discrete(param='dc.num1', options=[0, 1, 2]),
                     ]

hyperparameter_optimization(base_paths_and_files=base_paths_and_files,
                            submission_requirements=submission_requirements,
                            distribution_list=distribution_list,
                            other_params=other_params,
                            **optimization_setting)
