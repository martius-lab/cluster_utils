#: Name of the CSV file to which used parameters of a job are saved.
CLUSTER_PARAM_FILE = "param_choice.csv"
#: Name of the CSV file to which resulting metrics of a job are saved.
CLUSTER_METRIC_FILE = "metrics.csv"
#: Name of the JSON file to which used parameters of a job are saved.
JSON_SETTINGS_FILE = "settings.json"

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

CONCLUDED_WITHOUT_RESULTS_GRACE_TIME_IN_SECS = 5.0
JOB_MANAGER_LOOP_SLEEP_TIME_IN_SECS = 0.2

RETURN_CODE_FOR_RESUME = 3
