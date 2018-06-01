#!/usr/bin/python
# Script for a cluster run to scan the parameter space

import os
import shutil
import sys

sys.path = ['/is/sg/mrolinek/Projects/Cluster_utils'] + sys.path

import cluster
from cluster.distributions import *

submission_name = 'test'

main_path = '/is/sg/mrolinek/Projects/Cluster_utils/example'
paths_and_files = dict(project_dir=main_path,
                       main_python_script=os.path.join(main_path, 'dummy.py'),
                       result_dir=os.path.join(main_path, 'results', 'cluster'),
                       jobs_dir=os.path.join(main_path, 'jobs'))


submission_requirements = dict(request_cpus=1,
                               request_gpus=0,
                               cuda_requirement=None,  # 'x.0' or None
                               memory_in_mb=4000,
                               bid=10)

other_params = {}

hyperparam_dict = {'x': list(np.linspace(0.0, 4.0, 3)),
                   'y': list(np.linspace(0.0, 4.0, 3)),
                   'z': list(np.linspace(0.0, 4.0, 3)),
                   'w': list(np.linspace(0.0, 4.0, 3))
}


all_args = dict(submission_name=submission_name,
                paths=paths_and_files,
                submission_requirements=submission_requirements,
                hyperparam_dict=hyperparam_dict,
                distribution_list=None,
                other_params=other_params,
                samples=None,
                restarts_per_setting=1,
                smart_naming=True)

if __name__ == '__main__':
    submission = cluster.cluster_run(**all_args)

    # copy this script to the result dir
    my_path = os.path.realpath(__file__)
    shutil.copy(my_path, os.path.join(paths_and_files['result_dir'],
                                      submission_name))
