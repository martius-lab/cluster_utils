#!/usr/bin/python
# Script for a cluster run to scan the parameter space

import os
import shutil
import cluster
from cluster.distributions import *

job_name = 'test'
paths_and_files = dict(project_dir='/is/sg/mrolinek/Projects/Cluster_utils/example',
                       main_python_script='dummy.py',
                       general_result_dir=os.path.join('results', 'cluster'),
                       result_file_name='results.csv',
                       jobs_dir='jobs')

job_requirements = dict(request_cpus=1,
                        request_gpus=0,
                        cuda_requirement=None,  # 'x.0' or None
                        memory_in_mb=4000,
                        bid=10)


other_params = {'random_param': 'yay'}



hyperparam_dict = {'x': list(np.linspace(0.0, 4.0, 5)),
                   'y': list(np.linspace(0.0, 4.0, 5)),
                   'z': list(np.linspace(0.0, 4.0, 5)),
                   'w': list(np.linspace(0.0, 4.0, 5))
}


all_args = dict(job_name=job_name,
                paths=paths_and_files,
                job_requirements=job_requirements,
                hyperparam_dict=hyperparam_dict,
                distribution_list=None,
                other_params=other_params,
                samples=None,
                restarts_per_setting=1,
                smart_naming=True,
                submit=False)

if __name__ == '__main__':
    cluster.cluster_run(**all_args)
    my_path = os.path.realpath(__file__)
    shutil.copy(my_path, os.path.join(paths_and_files['project_dir'],
                                      paths_and_files['general_result_dir'],
                                      job_name))
