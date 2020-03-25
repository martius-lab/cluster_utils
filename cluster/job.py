import os
import time
from contextlib import suppress
from copy import deepcopy
from warnings import warn
from .utils import dict_to_dirname, flatten_nested_string_dict
from cluster.utils import update_recursive
import pandas as pd


class JobStatus():
    INITIAL_STATUS = -1
    SUBMITTED = 0
    RUNNING = 1
    FAILED = 2
    SENT_RESULTS = 3
    CONCLUDED = 4


class Job():
    def __init__(self, id, candidate, settings, other_params, paths, iteration, connection_info, metric_to_watch=None):
        self.metric_to_watch = metric_to_watch
        self.paths = paths
        self.id = id
        self.candidate = candidate
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
        self.comm_server_info = {'id': id,
                                 'ip': connection_info['ip'],
                                 'port': connection_info['port']}
        self.status = JobStatus.INITIAL_STATUS
        self.metrics = None
        self.error_info = None
        self.resulting_df = None
        self.param_df = None
        self.metric_df = None
        self.reported_metric_values = None

    def generate_execution_cmd(self, paths):
        current_setting = deepcopy(self.settings)
        update_recursive(current_setting, self.other_params)
        current_setting['id'] = self.id
        job_res_dir = dict_to_dirname(current_setting, self.id, smart_naming=False)
        current_setting['model_dir'] = os.path.join(paths['current_result_dir'], job_res_dir)

        setting_cwd = 'cd {}'.format(paths['main_path'])
        if 'virtual_env_path' in paths:
            virtual_env_activate = 'source {}'.format(os.path.join(paths['virtual_env_path'], 'bin/activate'))
        else:
            virtual_env_activate = ''

        if 'conda_env_path' in paths:
            conda_env_activate = f"pushd && cd && exec conda activate {paths['conda_env_path']} && popd"
        else:
            conda_env_activate = ''

        if 'custom_pythonpaths' in paths:
            raise NotImplementedError('Setting custom pythonpath was deprecated. Set \"virtual_env_path\" instead.')

        if 'custom_python_executable_path' in paths:
            warn('Setting custom_python_executable_path not recommended. Better set \"virtual_env_path\" instead.')

        python_executor = paths.get('custom_python_executable_path', 'python3')
        is_python_script = paths.get('is_python_script', True)

        self.final_settings = current_setting

        if is_python_script:
            run_script_as_module_main = paths.get('run_script_as_module_main', False)
            setting_string = '\"' + str(current_setting) + '\"'
            comm_info_string = '\"' + str(self.comm_server_info) + '\"'
            if run_script_as_module_main:
                exec_cmd = f"{python_executor} -m {os.path.basename(paths['script_to_run'])} {comm_info_string} {setting_string}"
            else:
                base_exec_cmd = '{}'.format(python_executor) + ' {} {} {}'
                exec_cmd = base_exec_cmd.format(paths['script_to_run'],
                                                comm_info_string,
                                                setting_string)
        else:
            base_exec_cmd = '{} {} {}'
            exec_cmd = base_exec_cmd.format(paths['script_to_run'],
                                            '\"' + str(self.comm_server_info) + '\"',
                                            '\"' + str(current_setting) + '\"')

        res = '\n'.join([setting_cwd, virtual_env_activate, conda_env_activate, exec_cmd])
        return res

    def set_results(self):
        flattened_params = dict(flatten_nested_string_dict(self.final_settings))
        self.param_df = pd.DataFrame([flattened_params])
        self.metric_df = pd.DataFrame([self.metrics])
        self.resulting_df = pd.concat([self.param_df, self.metric_df], axis=1)

    def get_results(self):
        if self.resulting_df is None or self.param_df is None or self.metric_df is None:
            return None
        return self.resulting_df, tuple(sorted(self.param_df.columns)), tuple(sorted(self.metric_df.columns))

    def check_filesystem_for_errors(self):
        assert self.run_script_path is not None
        assert self.status == JobStatus.SUBMITTED or self.waiting_for_resume
        log_file = f"{self.run_script_path}.log"
        with suppress(FileNotFoundError):
            with open(log_file) as f:
                content = f.read()
            _, __, after = content.rpartition('return value ')

            if after and after[0] != '1':
                return

            _, __, hostname = content.rpartition('Job executing on host: <172.22.')
            hostname = f"?0{hostname[2:].split(':')[0]}"
            self.hostname = hostname
            err_file = f"{self.run_script_path}.err"
            with open(err_file) as f_err:
                exception = f_err.read()
            self.status = JobStatus.FAILED
            self.error_info = exception

    @property
    def time_left(self):
        if self.estimated_end is not None:
            return self.estimated_end - time.time()
        return None

    @staticmethod
    def time_left_to_str(time_left):
        return f"{int(time_left // 3600)}h,{int((time_left % 3600) // 60)}m"
