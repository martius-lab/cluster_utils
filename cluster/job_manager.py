#!/usr/bin/python
# Script for a cluster run to scan the parameter space

import os
import random
import collections
import itertools
import shutil

from . import utils
from subprocess import run


def rm_dir_full(dir_name):
    if os.path.exists(dir_name):
        shutil.rmtree(dir_name, ignore_errors=True)


def create_dir(dir_name):
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)


def dict_to_dirname(setting, id, smart_naming=True):
    vals = ['{}={}'.format(str(key)[:3], str(value)[:6]) for key, value in setting.items()]
    res = '{}_{}'.format(id,'_'.join(vals))
    if len(res) < 35 and smart_naming:
        return res
    return str(id)


def cluster_run(job_name, paths, job_requirements, other_params, hyperparam_dict=None,
                samples=None, distribution_list=None, restarts_per_setting=1,
                smart_naming=True, submit=False):

    # Job requirements
    mem = job_requirements['memory_in_mb']
    cpus = job_requirements['request_cpus']
    gpus = job_requirements['request_gpus']
    bid = job_requirements['bid']

    if gpus > 0 and job_requirements['cuda_requirement'] is not None:
        cuda_line = 'Requirements=CUDACapability>={}'.format(job_requirements['cuda_requirement'])
    else:
        cuda_line = ''

    # Directories and filenames
    project_dir = paths['project_dir']
    script_to_run_name = os.path.join(project_dir, paths['main_python_script'])
    result_dir_abs = os.path.join(project_dir, paths['general_result_dir'], job_name)
    job_dir_name_abs = os.path.join(project_dir, paths['jobs_dir'], job_name)

    rm_dir_full(result_dir_abs)
    rm_dir_full(job_dir_name_abs)
    create_dir(job_dir_name_abs)
    create_dir(result_dir_abs)

    submit_file = os.path.join(job_dir_name_abs, 'submit_{}.sh'.format(job_name))
    SUBMIT = open(submit_file, 'w')
    SUBMIT.write('#/bin/bash\n')
    id_number = 0

    if samples is not None:
        if hyperparam_dict is not None:
            setting_generator = my_utils.nested_dict_hyperparam_samples(hyperparam_dict, samples)
        elif distribution_list is not None:
            setting_generator = my_utils.distribution_list_sampler(distribution_list, samples)
        else:
            raise ValueError('No hyperparameter dict/distribution list given')
    else:
        setting_generator = my_utils.nested_dict_hyperparam_product(hyperparam_dict)

    for setting in setting_generator:
        #print(setting)
        for iteration in range(restarts_per_setting):  # one more run if test script not done

            id_number += 1
            other_params['id'] = id_number
            job_res_dir = dict_to_dirname(setting, id_number, smart_naming)
            other_params['model_dir'] = os.path.join(result_dir_abs, job_res_dir)
            expected_len = len(setting) + len(other_params)

            setting.update(other_params)
            if len(setting) != expected_len and iteration == 0:
                raise ValueError("Duplicate entries in hyperparam_dict and other_params!")
            base_cmd = 'python3 {} {}'
            cmd = base_cmd.format(script_to_run_name, '\"' + str(setting) + '\"')

            jobfile_name = '{}_{}.sh'.format(job_name, id_number)
            runscriptfile_path = os.path.join(job_dir_name_abs, jobfile_name)
            jobfile_path = os.path.join(job_dir_name_abs, jobfile_name + '.sub')

            SUBMIT.write('condor_submit_bid {} {}\n'.format(bid, jobfile_path))

            with open(runscriptfile_path, 'w') as FILE:      # Lines 4-6 set up my virtual environment
                FILE.write('''\
    #!/bin/bash
    cd %(project_dir)s
    # %(job_name)s%(id_number)d

    export PATH=${HOME}/bin:/usr/bin:$PATH:/bin
    export PYTHONPATH=%(project_dir)s:$PYTHONPATH
    export LD_LIBRARY_PATH=/is/software/nvidia/cuda-9.0/lib64:/is/software/nvidia/cudnn-7.0-cu9.0/lib64:$LD_LIBRARY_PATH
    module load cuda/9.0
    module load cudnn/7.0-cu9.0
    %(cmd)s
    rc=$?

    if [[ $rc == 0 ]]; then
        rm -f %(runscriptfile_path)s
        rm -f %(jobfile_path)s
    elif [[ $rc == 3 ]]; then
        echo "exit with code 3 for resume"
        exit 3
    fi
    ''' % locals())

            with open(jobfile_path, 'w') as FILE:
                                    FILE.write("""\
    executable = %(runscriptfile_path)s
    error = %(runscriptfile_path)s.err
    output = %(runscriptfile_path)s.out
    log = %(runscriptfile_path)s.log
    request_memory=%(mem)s
    request_cpus=%(cpus)s
    request_gpus=%(gpus)s
    %(cuda_line)s
    on_exit_hold = (ExitCode =?= 3)
    on_exit_hold_reason = "Checkpointed, will resume"
    on_exit_hold_subcode = 2
    periodic_release = ( (JobStatus =?= 5) && (HoldReasonCode =?= 3) && (HoldReasonSubCode =?= 2) )
    queue
    """ % locals())
            os.chmod(runscriptfile_path, 0O755)

    SUBMIT.close()
    os.chmod(submit_file, 0O755)  # Make submit script executable
    print('Jobs created:', id_number)
    if submit:
        run(['./submit_{}.sh'.format(job_name)], cwd=str(job_dir_name_abs), shell=True)
