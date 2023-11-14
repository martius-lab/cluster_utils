from __future__ import annotations

import ast
import atexit
import enum
import functools
import json
import os
import pickle
import socket
import sys
import time
import traceback
from typing import Any

import pyuv
import smart_settings

from cluster import constants, submission_state
from cluster.communication_server import MessageTypes
from cluster.optimizers import GridSearchOptimizer, Metaoptimizer, NGOptimizer
from cluster.utils import flatten_nested_string_dict, save_dict_as_one_line_csv


class GenerateReportSetting(enum.Enum):
    """The possible values for the "generate_report" setting."""

    #: Do not generate report automatically.
    NEVER = 0
    #: Generate report once when the optimization has finished.
    WHEN_FINISHED = 1
    #: Generate report after every iteration of the optimization.
    EVERY_ITERATION = 2

    @staticmethod
    def parse_generate_report_setting_hook(settings: dict[str, Any]) -> None:
        """Parse the "generate_report" parameter in the settings dict.

        Check if a key "generate_report" exists in the settings dictionary and parse its
        value to replace it with the proper enum value.  If no entry exists in settings,
        it will be added with default value ``NEVER``.

        Raises:
            ValueError: if the value in settings cannot be mapped to one of the enum
                values.
        """
        key = "generate_report"
        value_str: str = settings.get(key, GenerateReportSetting.NEVER.name)
        value_str = value_str.upper()
        try:
            value_enum = GenerateReportSetting[value_str]
        except KeyError as e:
            options = (
                GenerateReportSetting.NEVER.name,
                GenerateReportSetting.WHEN_FINISHED.name,
                GenerateReportSetting.EVERY_ITERATION.name,
            )
            raise ValueError(
                f"Invalid value {e} for setting {key}.  Valid options are {options}."
            ) from None

        settings[key] = value_enum


class SettingsJsonEncoder(json.JSONEncoder):
    """JSON encoder that handles custom types used in the settings structure."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, enum.Enum):
            return obj.name

        return json.JSONEncoder.default(self, obj)


def cluster_main(main_func=None, **read_params_args):
    if main_func is None:
        return functools.partial(cluster_main, **read_params_args)

    @functools.wraps(main_func)
    def wrapper():
        """Saves settings file on beginning, calls wrapped function with params from cmd
        and saves metrics to working_dir
        """
        params = read_params_from_cmdline(**read_params_args)
        metrics = main_func(**params)
        save_metrics_params(metrics, params)
        return metrics

    return wrapper


def save_settings_to_json(setting_dict, working_dir):
    filename = os.path.join(working_dir, constants.JSON_SETTINGS_FILE)
    with open(filename, "w") as file:
        json.dump(setting_dict, file, sort_keys=True, indent=4, cls=SettingsJsonEncoder)


def send_results_to_server(metrics):
    print(
        "Sending results to: ",
        (
            submission_state.communication_server_ip,
            submission_state.communication_server_port,
        ),
    )
    send_message(
        MessageTypes.JOB_SENT_RESULTS, message=(submission_state.job_id, metrics)
    )


def send_message(message_type, message):
    loop = pyuv.Loop.default_loop()
    udp = pyuv.UDP(loop)
    udp.try_send(
        (
            submission_state.communication_server_ip,
            submission_state.communication_server_port,
        ),
        pickle.dumps((message_type, message)),
    )


def announce_fraction_finished(fraction_finished):
    if not submission_state.connection_active:
        return

    print(
        "Sending time estimate to: ",
        (
            submission_state.communication_server_ip,
            submission_state.communication_server_port,
        ),
    )
    send_message(
        MessageTypes.JOB_PROGRESS_PERCENTAGE,
        message=(submission_state.job_id, fraction_finished),
    )


def announce_early_results(metrics):
    if not submission_state.connection_active:
        return

    sanitized = {key: sanitize_numpy_torch(value) for key, value in metrics.items()}

    print(
        "Sending early results to: ",
        (
            submission_state.communication_server_ip,
            submission_state.communication_server_port,
        ),
    )
    send_message(
        MessageTypes.METRIC_EARLY_REPORT, message=(submission_state.job_id, sanitized)
    )


def exit_for_resume():
    if not submission_state.connection_active:
        return
    atexit.unregister(report_exit_at_server)  # Disable exit reporting
    send_message(MessageTypes.EXIT_FOR_RESUME, message=(submission_state.job_id,))
    sys.exit(3)  # With exit code 3 for resume


def sanitize_numpy_torch(possibly_np_or_tensor):
    # Hacky check for torch tensors without importing torch
    if str(type(possibly_np_or_tensor)) == "<class 'torch.Tensor'>":
        return possibly_np_or_tensor.item()  # silently convert to float
    if str(type(possibly_np_or_tensor)) == "<class 'numpy.ndarray'>":
        return float(possibly_np_or_tensor)
    return possibly_np_or_tensor


def save_metrics_params(metrics, params):
    param_file = os.path.join(params.working_dir, constants.CLUSTER_PARAM_FILE)
    flattened_params = dict(flatten_nested_string_dict(params))
    save_dict_as_one_line_csv(flattened_params, param_file)

    time_elapsed = time.time() - read_params_from_cmdline.start_time
    if "time_elapsed" not in metrics:
        metrics["time_elapsed"] = time_elapsed
    else:
        print(
            "WARNING: 'time_elapsed' metric already taken. Automatic time saving"
            " failed."
        )
    metric_file = os.path.join(params.working_dir, constants.CLUSTER_METRIC_FILE)

    for key, value in metrics.items():
        metrics[key] = sanitize_numpy_torch(value)

    save_dict_as_one_line_csv(metrics, metric_file)
    if submission_state.connection_active:
        send_results_to_server(metrics)


def is_settings_file(cmd_line):
    if (
        cmd_line.endswith(".json")
        or cmd_line.endswith(".yml")
        or cmd_line.endswith(".yaml")
        or cmd_line.endswith(".toml")
    ):
        if not os.path.isfile(cmd_line):
            raise FileNotFoundError(f"{cmd_line}: No such settings file found")
        return True
    else:
        return False


def is_parseable_dict(cmd_line):
    try:
        res = ast.literal_eval(cmd_line)
        return isinstance(res, dict)
    except Exception as e:
        print("WARNING: Dict literal eval suppressed exception: ", e)
        return False


def register_at_server(final_params):
    print(
        "Sending registration to: ",
        (
            submission_state.communication_server_ip,
            submission_state.communication_server_port,
        ),
    )
    send_message(
        MessageTypes.JOB_STARTED,
        message=(submission_state.job_id, socket.gethostname()),
    )


def report_error_at_server(exctype, value, tb):
    print(
        "Sending errors to: ",
        (
            submission_state.communication_server_ip,
            submission_state.communication_server_port,
        ),
    )
    send_message(
        MessageTypes.ERROR_ENCOUNTERED,
        message=(
            submission_state.job_id,
            traceback.format_exception(exctype, value, tb),
        ),
    )


def report_exit_at_server():
    print(
        "Sending confirmation of exit to: ",
        (
            submission_state.communication_server_ip,
            submission_state.communication_server_port,
        ),
    )
    send_message(MessageTypes.JOB_CONCLUDED, message=(submission_state.job_id,))


def add_cmd_line_params(base_dict, extra_flags):
    for extra_flag in extra_flags:
        lhs, eq, rhs = extra_flag.rpartition("=")
        parsed_lhs = lhs.split(".")
        new_lhs = "base_dict" + "".join([f'["{item}"]' for item in parsed_lhs])
        cmd = new_lhs + eq + rhs
        try:
            exec(cmd)
        except Exception as e:
            raise RuntimeError(f"Command {cmd} failed") from e


def read_params_from_cmdline(
    cmd_line=None,
    make_immutable=True,
    verbose=True,
    dynamic=True,
    pre_unpack_hooks=None,
    post_unpack_hooks=None,
    save_params=True,
):
    """Updates default settings based on command line input.

    :param cmd_line: Expecting (same format as) sys.argv
    :param verbose: Boolean to determine if final settings are pretty printed
    :return: Settings object with (deep) dot access.
    """
    pre_unpack_hooks = pre_unpack_hooks or []
    post_unpack_hooks = post_unpack_hooks or []

    if not cmd_line:
        cmd_line = sys.argv

    try:
        connection_details = ast.literal_eval(cmd_line[1])
    except (SyntaxError, ValueError):
        connection_details = {}
        pass

    if set(connection_details.keys()) == {constants.ID, "ip", "port"}:
        submission_state.communication_server_ip = connection_details["ip"]
        submission_state.communication_server_port = connection_details["port"]
        submission_state.job_id = connection_details[constants.ID]
        del cmd_line[1]
        submission_state.connection_details_available = True
        submission_state.connection_active = False

    def check_reserved_params(orig_dict):
        for key in orig_dict:
            if key in constants.RESERVED_PARAMS:
                raise ValueError(f"{key} is a reserved param name")

    if len(cmd_line) < 2:
        final_params = {}
    elif is_settings_file(cmd_line[1]):

        def add_cmd_params(orig_dict):
            add_cmd_line_params(orig_dict, cmd_line[2:])

        final_params = smart_settings.load(
            cmd_line[1],
            make_immutable=make_immutable,
            dynamic=dynamic,
            post_unpack_hooks=(
                [add_cmd_params, check_reserved_params] + post_unpack_hooks
            ),
            pre_unpack_hooks=pre_unpack_hooks,
        )

    elif len(cmd_line) == 2 and is_parseable_dict(cmd_line[1]):
        final_params = ast.literal_eval(cmd_line[1])
        final_params = smart_settings.loads(
            json.dumps(final_params),
            make_immutable=make_immutable,
            dynamic=dynamic,
            post_unpack_hooks=[check_reserved_params] + post_unpack_hooks,
            pre_unpack_hooks=pre_unpack_hooks,
        )
    else:
        raise ValueError("Failed to parse command line")

    if verbose:
        print(final_params)

    if (
        submission_state.connection_details_available
        and not submission_state.connection_active
    ):
        register_at_server(final_params)
        sys.excepthook = report_error_at_server
        atexit.register(report_exit_at_server)
        submission_state.connection_active = True
    read_params_from_cmdline.start_time = time.time()

    if save_params and "working_dir" in final_params:
        os.makedirs(final_params.working_dir, exist_ok=True)
        save_settings_to_json(final_params, final_params.working_dir)

    return final_params


# TODO This doesn't look like a good use case for a function attribute. Maybe it should
# be done differently?
read_params_from_cmdline.start_time = None  # type: ignore[attr-defined]

optimizer_dict = {
    "cem_metaoptimizer": Metaoptimizer,
    "nevergrad": NGOptimizer,
    "gridsearch": GridSearchOptimizer,
}
