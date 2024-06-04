import argparse
import json
import pathlib
import re

import pytest
import tomli_w
import yaml

from cluster_utils import constants
from cluster_utils import settings as s
from cluster_utils.utils import (
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
        "git_params": {"branch": "master"},
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
        "samples": 20,
        "hyperparam_list": [
            {"param": "fn_args.u", "values": [-0.5, 0.5]},
            {"param": "fn_args.v", "values": [10, 50]},
        ],
    }


def test_init_main_script_argument_parser():
    parser = s.init_main_script_argument_parser(description="foo")

    # basic (only file)
    args = parser.parse_args(["file.toml"])
    assert hasattr(args, "settings_file")
    assert hasattr(args, "settings")
    assert args.settings_file == pathlib.Path("file.toml")
    assert args.settings == []

    # file + cmd line args
    args = parser.parse_args(["file.toml", "foo=42", "bar='hi'"])
    assert hasattr(args, "settings_file")
    assert hasattr(args, "settings")
    assert args.settings_file == pathlib.Path("file.toml")
    assert args.settings == ["foo=42", "bar='hi'"]


@pytest.mark.parametrize(
    "config_file_format",
    [("json", "w", json.dump), ("yml", "w", yaml.dump), ("toml", "wb", tomli_w.dump)],
)
def test_read_main_script_params_from_args__basic(
    tmp_path, base_config, config_file_format
):
    config_file_ext, config_file_write_mode, config_file_dump = config_file_format

    # save config to file
    config_file = tmp_path / f"config.{config_file_ext}"
    with open(config_file, config_file_write_mode) as f:
        config_file_dump(base_config, f)

    args = argparse.Namespace(settings_file=config_file, settings=[])
    params = s.read_main_script_params_from_args(args)

    # just a basic check to see if the file was read
    assert params["optimization_procedure_name"] == "test_grid_search"
    assert params["fixed_params"]["test_resume"] is False
    assert params["generate_report"] is s.GenerateReportSetting.NEVER
    # TODO more checks to verify the other hooks are doing their jobs


def test_read_main_script_params_from_args__with_cmdline_overwrites(
    tmp_path, base_config
):
    # save config to file
    config_file = tmp_path / "config.json"
    with open(config_file, "w") as f:
        json.dump(base_config, f)

    args = argparse.Namespace(
        settings_file=config_file,
        settings=["optimization_procedure_name='foo'", "fixed_params.test_resume=True"],
    )
    params = s.read_main_script_params_from_args(args)

    # just a basic check to see if the file was read
    assert params["optimization_procedure_name"] == "foo"
    assert params["fixed_params"]["test_resume"] is True
    assert params["generate_report"] is s.GenerateReportSetting.NEVER


def test_read_params_from_cmdline__dict():
    argv = ["test", "--parameter-dict", "{'foo': 'bar', 'one': {'two': 13}}"]
    params = s.read_params_from_cmdline(cmd_line=argv)

    assert "foo" in params
    assert "one" in params
    assert "two" in params["one"]
    assert params["foo"] == "bar"
    assert params["one"]["two"] == 13


def test_read_params_from_cmdline__dict_and_overwrite():
    argv = [
        "test",
        "--parameter-dict",
        "{'foo': 'bar', 'one': {'two': 13}}",
        "foo='blub'",
        "three=3",
    ]
    params = s.read_params_from_cmdline(cmd_line=argv)

    assert "foo" in params
    assert params["foo"] == "blub"
    assert "one" in params
    assert "two" in params["one"]
    assert params["one"]["two"] == 13
    assert "three" in params
    assert params["three"] == 3


def test_read_params_from_cmdline__file(tmp_path):
    # save config to file
    config_file = tmp_path / "config.json"
    with open(config_file, "w") as f:
        json.dump({"foo": "bar", "one": {"two": 13}}, f)

    argv = ["test", str(config_file)]
    params = s.read_params_from_cmdline(cmd_line=argv)

    assert "foo" in params
    assert "one" in params
    assert "two" in params["one"]
    assert params["foo"] == "bar"
    assert params["one"]["two"] == 13


def test_read_params_from_cmdline__file_and_overwrite(tmp_path):
    # save config to file
    config_file = tmp_path / "config.json"
    with open(config_file, "w") as f:
        json.dump({"foo": "bar", "one": {"two": 13}}, f)

    argv = [
        "test",
        str(config_file),
        "foo='blub'",
        "three=3",
    ]
    params = s.read_params_from_cmdline(cmd_line=argv)

    assert "foo" in params
    assert params["foo"] == "blub"
    assert "one" in params
    assert "two" in params["one"]
    assert params["one"]["two"] == 13
    assert "three" in params
    assert params["three"] == 3


def test_read_params_from_cmdline__errors(monkeypatch):
    # for better testability, overwrite the ArgumentParser.error method with one that
    # raises an error instead of exiting
    def monkey_error(self, message):
        raise RuntimeError(message)

    monkeypatch.setattr(argparse.ArgumentParser, "error", monkey_error)

    argv = [
        "test",
        "{'foo': 13}",  # not a file
    ]
    with pytest.raises(
        FileNotFoundError,
        match=re.escape("'{'foo': 13}' does not exist or is not a file."),
    ):
        s.read_params_from_cmdline(cmd_line=argv)

    argv = [
        "test",
        "--job-id=42",
        "--cluster-utils-server=invalid_format",
        "--parameter-dict",
        "{'foo': 13}",
    ]
    with pytest.raises(RuntimeError, match="--cluster-utils-server"):
        s.read_params_from_cmdline(cmd_line=argv)

    argv = [
        "test",
        "--cluster-utils-server=127.0.0.1:12345",
        "--parameter-dict",
        "{'foo': 13}",
    ]
    with pytest.raises(
        RuntimeError,
        match="--job-id is required when --cluster-utils-server is set",
    ):
        s.read_params_from_cmdline(cmd_line=argv)

    argv = ["test", "--parameter-dict", "'notadictionary'"]
    with pytest.raises(
        ValueError,
        match=re.escape(
            "'parameter_file_or_dict' must be a dictionary (`--parameter-dict` is set)."
        ),
    ):
        s.read_params_from_cmdline(cmd_line=argv)


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
        verbose=False,
    )

    # just a basic check to see if the file was read
    assert params["optimization_procedure_name"] == "test_grid_search"

    # verify that settings file was written
    output_settings_file = working_dir / constants.JSON_SETTINGS_FILE
    assert output_settings_file.is_file()
    with open(output_settings_file, "r") as f:
        settings = json.load(f)
    assert settings["optimization_procedure_name"] == "test_grid_search"
