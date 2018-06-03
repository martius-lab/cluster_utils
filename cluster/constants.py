CLUSTER_PARAM_FILE = 'param_choice.csv'
CLUSTER_METRIC_FILE = 'metrics.csv'
JSON_SETTINGS_FILE = 'settings.json'
JSON_FILE_KEY = 'default_json'
OBJECT_SEPARATOR = '.'

PARAM_TYPES = (bool, str, int, float, tuple)

RESERVED_PARAMS = ('model_dir', 'id', 'iteration')

DISTR_COLOR = (0.999, 0.786, 0.409)


MPI_CLUSTER_RUN_SCRIPT = '''
#!/bin/bash
# %(name)s%(id)d

export PATH=${HOME}/bin:/usr/bin:$PATH:/bin
export LD_LIBRARY_PATH=/is/software/nvidia/cuda-9.0/lib64:/is/software/nvidia/cudnn-7.0-cu9.0/lib64:$LD_LIBRARY_PATH
module load cuda/9.0
module load cudnn/7.0-cu9.0
%(cmd)s
rc=$?

if [[ $rc == 0 ]]; then
    rm -f %(run_script_file_path)s
    rm -f %(job_spec_file_path)s
elif [[ $rc == 3 ]]; then
    echo "exit with code 3 for resume"
    exit 3
elif [[ $rc == 1 ]]; then
    exit 1
fi
'''

MPI_CLUSTER_JOB_SPEC_FILE = '''
executable = %(run_script_file_path)s
error = %(run_script_file_path)s.err
output = %(run_script_file_path)s.out
log = %(run_script_file_path)s.log
request_memory=%(mem)s
request_cpus=%(cpus)s
request_gpus=%(gpus)s
%(cuda_line)s
on_exit_hold = (ExitCode =?= 3)
on_exit_hold_reason = "Checkpointed, will resume"
on_exit_hold_subcode = 2
periodic_release = ( (JobStatus =?= 5) && (HoldReasonCode =?= 3) && (HoldReasonSubCode =?= 2) )
queue
'''