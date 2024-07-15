from __future__ import annotations

import logging
import os
import pathlib
import time
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

import pandas as pd

from cluster_utils.base import constants
from cluster_utils.base.utils import flatten_nested_string_dict

from .utils import dict_to_dirname, update_recursive

if TYPE_CHECKING:
    import concurrent.futures

    from .cluster_system import ClusterJobId
    from .settings import SingularitySettings


class JobStatus:
    INITIAL_STATUS = -1
    SUBMITTED = 0
    RUNNING = 1
    FAILED = 2
    SENT_RESULTS = 3
    CONCLUDED = 4
    CONCLUDED_WITHOUT_RESULTS = 5


class Job:
    def __init__(
        self,
        *,
        id,  # noqa: A002
        settings,
        other_params,
        paths,
        iteration,
        connection_info,
        opt_procedure_name,
        singularity_settings: Optional[SingularitySettings],
        metric_to_watch=None,
    ) -> None:
        self.metric_to_watch = metric_to_watch
        self.paths = paths
        self.id = id
        self.settings = settings
        self.other_params = other_params
        self.cluster_id: Optional[ClusterJobId] = None
        self.results_used_for_update = False
        self.job_spec_file_path: Optional[str] = None
        self.run_script_path: Optional[str] = None
        self.hostname: Optional[str] = None
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
        self.error_info: Optional[str] = None
        self.resulting_df = None
        self.param_df = None
        self.metric_df = None
        self.reported_metric_values: list[Any] = []  # FIXME what is the expected type?
        self.futures_object: Optional[concurrent.futures.Future] = None
        self.opt_procedure_name = opt_procedure_name
        self.singularity_settings = singularity_settings

    def generate_final_setting(self, paths):
        current_setting = deepcopy(self.settings)
        update_recursive(current_setting, self.other_params)
        job_res_dir = dict_to_dirname(current_setting, self.id, smart_naming=False)
        current_setting[constants.WORKING_DIR] = os.path.join(
            paths["current_result_dir"], job_res_dir
        )
        current_setting["id"] = self.id
        return current_setting

    def generate_execution_cmd(self, paths, cmd_prefix: Optional[str] = None):
        """Generate the commands to execute the job.

        Args:
            paths: Dictionary containing relevant paths.
            cmd_prefix: String that is prepended to the command that runs the user
                script.  Can be used to wrap in some cluster-system-specific command
                (e.g. to use `srun` on Slurm).

        Returns:
            Shell script running the job (includes cd-ing to the source directory,
            activating virtual environments, etc.).
        """
        logger = logging.getLogger("cluster_utils")
        current_setting = self.generate_final_setting(paths)

        set_cwd = "cd {}".format(paths["main_path"])

        if "variables" in paths:
            if not isinstance(paths["variables"], dict):
                raise ValueError(
                    'Expected type dict for "variables", but got type'
                    f' {type(paths["variables"])} instead'
                )
            env_variables = {
                str(name): str(value) for name, value in paths["variables"].items()
            }
            set_env_variables = "\n".join(
                f'export {name}="{value}"' for name, value in env_variables.items()
            )
        else:
            env_variables = None
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

        arguments = (
            "--job-id={job_id}"
            " --cluster-utils-server={ip}:{port}"
            ' --parameter-dict "{current_setting}"'
        ).format(
            job_id=self.comm_server_info[constants.ID],
            ip=self.comm_server_info["ip"],
            port=self.comm_server_info["port"],
            current_setting=current_setting,
        )

        if is_python_script:
            run_script_as_module_main = paths.get("run_as_module", False)
            if run_script_as_module_main:
                # convert path to module name
                module_name = (
                    paths["script_to_run"].replace("/", ".").replace(".py", "")
                )
                exec_cmd = f"{python_executor} -m {module_name} {arguments}"
            else:
                script_path = os.path.join(paths["main_path"], paths["script_to_run"])
                exec_cmd = f"{python_executor} {script_path} {arguments}"
        else:
            script_path = os.path.join(paths["main_path"], paths["script_to_run"])
            exec_cmd = f"{script_path} {arguments}"

        if self.singularity_settings:
            exec_cmd = self.singularity_wrap(
                exec_cmd,
                self.singularity_settings,
                paths["main_path"],
                current_setting["working_dir"],
                env_variables,
            )

        if cmd_prefix:
            exec_cmd = f"{cmd_prefix} {exec_cmd}"

        res = "\n".join(
            [
                set_cwd,
                virtual_env_activate,
                conda_env_activate,
                set_env_variables,
                pre_job_script,
                exec_cmd,
            ]
        )
        return res

    def singularity_wrap(
        self,
        exec_cmd: str,
        singularity_settings: SingularitySettings,
        exec_dir: Union[str, os.PathLike],
        working_dir: Union[str, os.PathLike],
        env_variables: Optional[Dict[str, str]],
    ) -> str:
        """Wrap the given command to execute it in a Singularity container.

        Args:
            exec_cmd: The command that shall be executed in the container.
        """
        logger = logging.getLogger("cluster_utils")

        singularity_image = pathlib.Path(singularity_settings.image).expanduser()
        working_dir = pathlib.Path(working_dir)

        if not singularity_image.exists():
            raise FileNotFoundError(
                f"Singularity image '{singularity_image}' does not exist"
            )

        # create model directory (so it can be bound into the container)
        working_dir.mkdir(exist_ok=True)

        if env_variables is None:
            env_variables = {}

        # construct singularity command
        cwd = os.fspath(exec_dir)
        bind_dirs = ["/tmp", os.fspath(working_dir), cwd]
        singularity_cmd = [
            singularity_settings.executable,
            "run" if singularity_settings.use_run else "exec",
            "--bind=%s" % ",".join(bind_dirs),
            "--pwd=%s" % cwd,
            " ".join(
                f'--env {name}="{value}"' for name, value in env_variables.items()
            ),
            *singularity_settings.args,
            os.fspath(singularity_image),
        ]

        full_cmd = "{} {}".format(" ".join(singularity_cmd), exec_cmd)
        logger.debug("Singularity-wrapped command: %s", full_cmd)

        return full_cmd

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

    def mark_failed(self, error_message: str) -> None:
        """Mark the job as failed.

        This sets the job's :attr:`~Job.status` to FAILED and stores the given error
        message to :attr:`~Job.error_info`.
        """
        logger = logging.getLogger("cluster_utils")
        logger.debug(
            "Mark job %d (cluster id: %s) as failed.", self.id, self.cluster_id
        )

        self.status = JobStatus.FAILED
        self.error_info = error_message

    @property
    def time_left(self):
        if self.estimated_end is not None:
            return self.estimated_end - time.time()
        return None

    @staticmethod
    def time_left_to_str(time_left):
        return f"{int(time_left // 3600)}h,{int((time_left % 3600) // 60)}m"
