CLUSTER_PARAM_FILE = 'param_choice.csv'
CLUSTER_METRIC_FILE = 'metrics.csv'
JSON_SETTINGS_FILE = 'settings.json'
JOB_INFO_FILE = 'job_info.csv'

STATUS_PICKLE_FILE = 'status.pickle'
FULL_DF_FILE = 'all_data.csv'
REDUCED_DF_FILE = 'reduced_data.csv'
STD_ENDING = '__std'
RESTART_PARAM_NAME = 'restarts'

JSON_FILE_KEY = 'default_json'
OBJECT_SEPARATOR = '.'

# note: must be hashable
PARAM_TYPES = (bool, str, int, float, tuple)

RESERVED_PARAMS = ('model_dir', 'id', 'iteration', RESTART_PARAM_NAME, 'cluster_job_id')

DISTR_BASE_COLORS = [(0.99, 0.7, 0.18), (0.7, 0.7, 0.9), (0.56, 0.692, 0.195), (0.923, 0.386, 0.209)]

MPI_CLUSTER_RUN_SCRIPT = '''
#!/bin/bash
# %(id)d

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
%(requirements_line)s
on_exit_hold = (ExitCode =?= 3)
on_exit_hold_reason = "Checkpointed, will resume"
on_exit_hold_subcode = 2
periodic_release = ( (JobStatus =?= 5) && (HoldReasonCode =?= 3) && (HoldReasonSubCode =?= 2) )
getenv=True
queue
'''


LOCAL_RUN_SCRIPT = '''#!/bin/bash
# %(id)d

%(cmd)s
'''
