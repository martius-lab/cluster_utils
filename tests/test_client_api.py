import argparse
import json
import pathlib
import re

import pytest

from cluster_utils import client, constants


@pytest.fixture()
def tests_dir() -> pathlib.Path:
    """Get path to the directory containing this test."""
    return pathlib.Path(__file__).parent


def test_read_params_from_cmdline__dict():
    argv = ["test", "--parameter-dict", "{'foo': 'bar', 'one': {'two': 13}}"]
    params = client.read_params_from_cmdline(cmd_line=argv)

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
    params = client.read_params_from_cmdline(cmd_line=argv)

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
    params = client.read_params_from_cmdline(cmd_line=argv)

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
    params = client.read_params_from_cmdline(cmd_line=argv)

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
        client.read_params_from_cmdline(cmd_line=argv)

    argv = [
        "test",
        "--job-id=42",
        "--cluster-utils-server=invalid_format",
        "--parameter-dict",
        "{'foo': 13}",
    ]
    with pytest.raises(RuntimeError, match="--cluster-utils-server"):
        client.read_params_from_cmdline(cmd_line=argv)

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
        client.read_params_from_cmdline(cmd_line=argv)

    argv = ["test", "--parameter-dict", "'notadictionary'"]
    with pytest.raises(
        ValueError,
        match=re.escape(
            "'parameter_file_or_dict' must be a dictionary (`--parameter-dict` is set)."
        ),
    ):
        client.read_params_from_cmdline(cmd_line=argv)


def test_read_params_from_cmdline__working_dir(tmp_path):
    # Add "working_dir" to config
    working_dir = tmp_path / "working_dir"
    working_dir.mkdir()

    base_config = {
        "test_resume": False,
        "max_sleep_time": 13,
        "fn_args.w": 1,
        "fn_args.x": 3.0,
        "fn_args.y": 0.1,
        "fn_args.sharp_penalty": False,
        "working_dir": str(working_dir),
    }

    # save config to file
    config_file = tmp_path / "config.json"
    with open(config_file, "w") as f:
        json.dump(base_config, f)

    cmd_line = ["test", str(config_file)]
    params = client.read_params_from_cmdline(
        cmd_line,
        verbose=False,
    )

    # just a basic check to see if the file was read
    assert params["max_sleep_time"] == 13

    # verify that settings file was written
    output_settings_file = working_dir / constants.JSON_SETTINGS_FILE
    assert output_settings_file.is_file()
    with open(output_settings_file, "r") as f:
        settings = json.load(f)
    assert settings["max_sleep_time"] == 13
