CLUSTER_PARAM_FILE = "param_choice.csv"
CLUSTER_METRIC_FILE = "metrics.csv"
JSON_SETTINGS_FILE = "settings.json"
JOB_INFO_FILE = "job_info.csv"

METADATA_FILE = "metadata.json"
STATUS_PICKLE_FILE = "status.pickle"
FULL_DF_FILE = "all_data.csv"
REDUCED_DF_FILE = "reduced_data.csv"
REPORT_DATA_FILE = "report_data.pickle"
STD_ENDING = "__std"
RESTART_PARAM_NAME = "job_restarts"

OBJECT_SEPARATOR = "."

# note: must be hashable
PARAM_TYPES = (bool, str, int, float, tuple)

WORKING_DIR = "working_dir"
ID = "_id"
ITERATION = "_iteration"

RESERVED_PARAMS = (ID, ITERATION, RESTART_PARAM_NAME)

DISTR_BASE_COLORS = [
    (0.99, 0.7, 0.18),
    (0.7, 0.7, 0.9),
    (0.56, 0.692, 0.195),
    (0.923, 0.386, 0.209),
]

CONCLUDED_WITHOUT_RESULTS_GRACE_TIME_IN_SECS = 5.0
JOB_MANAGER_LOOP_SLEEP_TIME_IN_SECS = 0.2

RETURN_CODE_FOR_RESUME = 3

MPI_CLUSTER_MAX_NUM_TOKENS = 10000

MPI_CLUSTER_RUN_SCRIPT = f"""#!/bin/bash
# Submission ID %(id)d

%(cmd)s
rc=$?
if [[ $rc == 0 ]]; then
    rm -f %(run_script_file_path)s
    rm -f %(job_spec_file_path)s
elif [[ $rc == {RETURN_CODE_FOR_RESUME} ]]; then
    echo "exit with code {RETURN_CODE_FOR_RESUME} for resume"
    exit {RETURN_CODE_FOR_RESUME}
elif [[ $rc == 1 ]]; then
    exit 1
fi
"""
# TODO: the MPI_CLUSTER_RUN_SCRIPT above does not forward errorcodes other than 1 and 3.
# Could this be a problem?

MPI_CLUSTER_JOB_SPEC_FILE = f"""# Submission ID %(id)d
JobBatchName=%(opt_procedure_name)s
executable = %(run_script_file_path)s

error = %(run_script_file_path)s.err
output = %(run_script_file_path)s.out
log = %(run_script_file_path)s.log

request_cpus=%(cpus)s
request_gpus=%(gpus)s
request_memory=%(mem)s

%(requirements_line)s

on_exit_hold = (ExitCode =?= {RETURN_CODE_FOR_RESUME})
on_exit_hold_reason = "Checkpointed, will resume"
on_exit_hold_subcode = 2
periodic_release = ( (JobStatus =?= 5) && (HoldReasonCode =?= {RETURN_CODE_FOR_RESUME}) && (HoldReasonSubCode =?= 2) )

# Inherit environment variables at submission time in job script
getenv=True

%(concurrent_line)s

%(extra_submission_lines)s

queue
"""


LOCAL_RUN_SCRIPT = """#!/bin/bash
# %(id)d

error="%(run_script_file_path)s.err"
output="%(run_script_file_path)s.out"

# Close standard output and error file descriptors
exec 1<&-
exec 2<&-

# Redirect output and error streams to files from here on
exec 1>>"$output"
exec 2>>"$error"

%(cmd)s
exit $?
"""
