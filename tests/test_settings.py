import json
import pathlib

import pytest

from cluster import constants
from cluster import settings as s
from cluster.utils import (
    check_import_in_fixed_params,
    rename_import_promise,
)

_PRE_UNPACK_HOOKS = [check_import_in_fixed_params]
_POST_UNPACK_HOOKS = [
    rename_import_promise,
    s.GenerateReportSetting.parse_generate_report_setting_hook,
]


@pytest.fixture()
def tests_dir() -> pathlib.Path:
    """Get path to the directory containing this test."""
    return pathlib.Path(__file__).parent


@pytest.fixture()
def base_config() -> dict:
    return {
        "optimization_procedure_name": "test_grid_search",
        "run_in_working_dir": True,
        "git_params": {"branch": "master", "commit": None},
        "generate_report": "never",
        "script_relative_path": "examples/basic/main_no_fail.py",
        "remove_jobs_dir": True,
        "environment_setup": {
            "pre_job_script": "examples/basic/pre_job_script.sh",
            "variables": {"TEST_VARIABLE": "test_value"},
        },
        "cluster_requirements": {
            "request_cpus": 1,
            "request_gpus": 0,
            "cuda_requirement": None,
            "memory_in_mb": 16000,
            "bid": 800,
        },
        "fixed_params": {
            "test_resume": False,
            "max_sleep_time": 1,
            "fn_args.w": 1,
            "fn_args.x": 3.0,
            "fn_args.y": 0.1,
            "fn_args.sharp_penalty": False,
        },
        "restarts": 1,
        "samples": None,
        "hyperparam_list": [
            {"param": "fn_args.u", "values": [-0.5, 0.5]},
            {"param": "fn_args.v", "values": [10, 50]},
        ],
    }


def test_read_params_from_cmdline__basic(tmp_path, base_config):
    # save config to file
    config_file = tmp_path / "config.json"
    with open(config_file, "w") as f:
        json.dump(base_config, f)

    cmd_line = ["test", str(config_file)]
    params = s.read_params_from_cmdline(cmd_line)

    # just a basic check to see if the file was read
    assert params["optimization_procedure_name"] == "test_grid_search"


def test_read_params_from_cmdline__with_hooks(tmp_path, base_config):
    # save config to file
    config_file = tmp_path / "config.json"
    with open(config_file, "w") as f:
        json.dump(base_config, f)

    cmd_line = ["test", str(config_file)]
    params = s.read_params_from_cmdline(
        cmd_line,
        pre_unpack_hooks=_PRE_UNPACK_HOOKS,
        post_unpack_hooks=_POST_UNPACK_HOOKS,
        verbose=False,  # TODO fails if verbose is true
    )

    # just a basic check to see if the file was read
    assert params["optimization_procedure_name"] == "test_grid_search"
    assert params["generate_report"] is s.GenerateReportSetting.NEVER
    # TODO more checks to verify the other hooks are doing their jobs


def test_read_params_from_cmdline__working_dir(tmp_path, base_config):
    # Add "working_dir" to config
    working_dir = tmp_path / "working_dir"
    working_dir.mkdir()
    base_config["working_dir"] = str(working_dir)

    # save config to file
    config_file = tmp_path / "config.json"
    with open(config_file, "w") as f:
        json.dump(base_config, f)

    cmd_line = ["test", str(config_file)]
    params = s.read_params_from_cmdline(
        cmd_line,
        pre_unpack_hooks=_PRE_UNPACK_HOOKS,
        post_unpack_hooks=_POST_UNPACK_HOOKS,
        verbose=False,
    )

    # just a basic check to see if the file was read
    assert params["optimization_procedure_name"] == "test_grid_search"
    assert params["generate_report"] is s.GenerateReportSetting.NEVER

    # verify that settings file was written
    output_settings_file = working_dir / constants.JSON_SETTINGS_FILE
    assert output_settings_file.is_file()
    with open(output_settings_file, "r") as f:
        settings = json.load(f)
    assert settings["optimization_procedure_name"] == "test_grid_search"
