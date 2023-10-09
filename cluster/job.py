import logging
import os
import time
from contextlib import suppress
from copy import deepcopy

import pandas as pd

from cluster import constants
from cluster.utils import dict_to_dirname, flatten_nested_string_dict, update_recursive


class JobStatus:
    INITIAL_STATUS = -1
    SUBMITTED = 0
    RUNNING = 1
    FAILED = 2
    SENT_RESULTS = 3
    CONCLUDED = 4


class Job:
    def __init__(
        self,
        id,  # noqa: A002
        settings,
        other_params,
        paths,
        iteration,
        connection_info,
        opt_procedure_name,
        metric_to_watch=None,
    ):
        self.metric_to_watch = metric_to_watch
        self.paths = paths
        self.id = id
        self.settings = settings
        self.other_params = other_params
        self.cluster_id = None
        self.results_used_for_update = False
        self.job_spec_file_path = False
        self.run_script_path = None
        self.hostname = None
        self.waiting_for_resume = False
        self.start_time = None
        self.estimated_end = None
        self.iteration = iteration
        self.comm_server_info = {
            constants.ID: id,
            "ip": connection_info["ip"],
            "port": connection_info["port"],
        }
        self.status = JobStatus.INITIAL_STATUS
        self.metrics = None
        self.error_info = None
        self.resulting_df = None
        self.param_df = None
        self.metric_df = None
        self.reported_metric_values = None
        self.futures_object = None
        self.opt_procedure_name = opt_procedure_name

    def generate_final_setting(self, paths):
        current_setting = deepcopy(self.settings)
        update_recursive(current_setting, self.other_params)
        job_res_dir = dict_to_dirname(current_setting, self.id, smart_naming=False)
        current_setting[constants.WORKING_DIR] = os.path.join(
            paths["current_result_dir"], job_res_dir
        )
        current_setting["id"] = self.id
        return current_setting

    def generate_execution_cmd(self, paths):
        logger = logging.getLogger("cluster_utils")
        current_setting = self.generate_final_setting(paths)

        set_cwd = "cd {}".format(paths["main_path"])

        if "variables" in paths:
            if not isinstance(paths, dict):
                raise ValueError(
                    'Expected type dict for "variables", but got type'
                    f' {type(paths["variables"])} instead'
                )
            set_env_variables = "\n".join(
                f"export {name}={value}" for name, value in paths["variables"].items()
            )
        else:
            set_env_variables = ""

        if "pre_job_script" in paths:
            pre_job_script = f'./{paths["pre_job_script"]}'
        else:
            pre_job_script = ""

        if "virtual_env_path" in paths:
            virtual_env_activate = "source {}".format(
                os.path.join(paths["virtual_env_path"], "bin/activate")
            )
        else:
            virtual_env_activate = ""

        if "conda_env_path" in paths:
            conda_env_activate = (
                f"pushd && cd && exec conda activate {paths['conda_env_path']} && popd"
            )
        else:
            conda_env_activate = ""

        if "custom_pythonpaths" in paths:
            raise NotImplementedError(
                'Setting custom pythonpath was deprecated. Set "virtual_env_path"'
                " instead."
            )

        if "custom_python_executable_path" in paths:
            logger.warning(
                "Setting custom_python_executable_path not recommended. "
                'Better set "virtual_env_path" instead.'
            )

        python_executor = paths.get("custom_python_executable_path", "python3")
        is_python_script = paths.get("is_python_script", True)

        self.final_settings = current_setting

        if is_python_script:
            run_script_as_module_main = paths.get("run_as_module", False)
            setting_string = '"' + str(current_setting) + '"'
            comm_info_string = '"' + str(self.comm_server_info) + '"'
            if run_script_as_module_main:
                # convert path to module name
                module_name = (
                    paths["script_to_run"].replace("/", ".").replace(".py", "")
                )
                exec_cmd = (
                    f"cd {paths['main_path']}; {python_executor} -m"
                    f" {module_name} {comm_info_string} {setting_string}"
                )
            else:
                base_exec_cmd = "{}".format(python_executor) + " {} {} {}"
                exec_cmd = base_exec_cmd.format(
                    os.path.join(paths["main_path"], paths["script_to_run"]),
                    comm_info_string,
                    setting_string,
                )
        else:
            base_exec_cmd = "{} {} {}"
            exec_cmd = base_exec_cmd.format(
                os.path.join(paths["main_path"], paths["script_to_run"]),
                '"' + str(self.comm_server_info) + '"',
                '"' + str(current_setting) + '"',
            )

        res = "\n".join(
            [
                set_cwd,
                pre_job_script,
                virtual_env_activate,
                conda_env_activate,
                set_env_variables,
                exec_cmd,
            ]
        )
        return res

    def set_results(self):
        flattened_params = dict(flatten_nested_string_dict(self.final_settings))
        flattened_params[constants.ID] = self.id
        self.param_df = pd.DataFrame([flattened_params])
        self.metric_df = pd.DataFrame([self.metrics])
        self.resulting_df = pd.concat([self.param_df, self.metric_df], axis=1)

    def try_load_results_from_filesystem(self, paths):
        logger = logging.getLogger("cluster_utils")
        working_dir = os.path.join(paths["current_result_dir"], str(self.id))

        possible_metric_file = os.path.join(working_dir, constants.CLUSTER_METRIC_FILE)
        if os.path.isfile(possible_metric_file):
            metric_df = pd.read_csv(possible_metric_file)
            self.metrics = {
                column: metric_df[column].iloc[0] for column in metric_df.columns
            }
            logger.info(
                f"Job {self.id} loaded final results {self.metrics} from the"
                " filesystem. Will not run!"
            )
            self.final_settings = self.generate_final_setting(paths)
            self.set_results()
            self.status = JobStatus.CONCLUDED

    def get_results(self):
        if self.resulting_df is None or self.param_df is None or self.metric_df is None:
            return None
        return (
            self.resulting_df,
            tuple(sorted(self.param_df.columns)),
            tuple(sorted(self.metric_df.columns)),
        )

    def check_filesystem_for_errors(self):
        assert self.run_script_path is not None
        assert self.status == JobStatus.SUBMITTED or self.waiting_for_resume
        log_file = f"{self.run_script_path}.log"
        with suppress(FileNotFoundError):
            with open(log_file) as f:
                content = f.read()
            _, __, after = content.rpartition("return value ")

            if after and after[0] != "1":
                return

            _, __, hostname = content.rpartition("Job executing on host: <172.22.")
            hostname = f"?0{hostname[2:].split(':')[0]}"
            self.hostname = hostname
            err_file = f"{self.run_script_path}.err"
            with open(err_file) as f_err:
                exception = f_err.read()
            self.status = JobStatus.FAILED
            self.error_info = exception

        # Local run
        if self.futures_object is not None and (
            self.futures_object.done()
            and self.futures_object.result().__dict__["returncode"] == 1
        ):
            self.status = JobStatus.FAILED
            self.error_info = self.futures_object.result().stderr.decode()

    @property
    def time_left(self):
        if self.estimated_end is not None:
            return self.estimated_end - time.time()
        return None

    @staticmethod
    def time_left_to_str(time_left):
        return f"{int(time_left // 3600)}h,{int((time_left % 3600) // 60)}m"
