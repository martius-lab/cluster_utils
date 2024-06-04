from __future__ import annotations

import argparse
import ast
import atexit
import enum
import functools
import json
import os
import pathlib
import pickle
import socket
import sys
import time
import traceback
from typing import Any, NamedTuple, Optional

import pyuv
import smart_settings

from . import constants, submission_state
from .communication_server import MessageTypes
from .optimizers import GridSearchOptimizer, Metaoptimizer, NGOptimizer
from .utils import (
    check_import_in_fixed_params,
    flatten_nested_string_dict,
    rename_import_promise,
    save_dict_as_one_line_csv,
)


class SettingsError(Exception):
    """Custom error for anything related to the settings."""

    ...


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


class SingularitySettings(NamedTuple):
    #: Path to time Singularity image
    image: str

    #: Singularity executable.  Defaults to "singularity" but can, for example, be used
    #: to explicitly use Apptainer instead.
    executable: str = "singularity"

    #: Per default the container is run with `singularity exec`.  Set this to True to
    #: use `singularity run` instead (for images that use a run script for environment
    #: setup before executing the given command).
    use_run: bool = False

    #: List of additional arguments to Singularity.
    args: list[str] = []

    @classmethod
    def from_settings(cls, settings: dict[str, Any]) -> SingularitySettings:
        try:
            obj = cls(**settings)
        except TypeError as e:
            raise ValueError(f"Failed to process Singularity settings: {e}") from e

        # some additional checks
        if not os.path.exists(os.path.expanduser(obj.image)):
            raise FileNotFoundError(f"Singularity image {obj.image} not found.")

        return obj


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
    """Send a "resume"-request to the cluster_utils server and exit with returncode 3.

    Use this to split a single long-running job into multiple shorter jobs by frequently
    saving intermediate results and restarting by calling this function.
    """
    if not submission_state.connection_active:
        # TODO: shouldn't it at least sys.exit() in any case?
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


def init_main_script_argument_parser(description: str) -> argparse.ArgumentParser:
    """Initialise ArgumentParser with the base arguments

    Basic construction of an ArgumentParser with everything that is common between the
    cluster_utils main scripts (i.e. grid_search and hp_optimization).

    Args:
        description: Used in the help text shown when run with ``--help``.

    Returns:
        ArgumentParser instance with basic arguments already configured.
        Script-specific additional options can still be added.
    """
    parser = argparse.ArgumentParser(
        description=description, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "settings_file", type=pathlib.Path, help="Path to the settings file."
    )
    parser.add_argument(
        "settings",
        nargs="*",
        type=str,
        metavar="KEY_VALUE",
        help="""Additional settings in the format '<key>=<value>'.  This will overwrite
            settings in the settings file.  Key has to match a configuration option,
            value has to be valid Python.  Example: 'results_dir="/tmp"'
            'optimization_setting.run_local=True'
        """,
    )
    return parser


def read_main_script_params_from_args(args: argparse.Namespace):
    """Read settings for grid_search/hp_optimization from command line args.

    Args:
        args: Arguments parsed by ArgumentParser which was created using
            :function:`init_main_script_argument_parser`.

    Returns:
        smart_settings parameter structure.
    """
    return read_main_script_params_with_smart_settings(
        settings_file=args.settings_file,
        cmdline_settings=args.settings,
        pre_unpack_hooks=[check_import_in_fixed_params],
        post_unpack_hooks=[
            rename_import_promise,
            GenerateReportSetting.parse_generate_report_setting_hook,
        ],
    )


def check_reserved_params(orig_dict: dict) -> None:
    """Check if the given dict contains reserved keys.  If yes, raise ValueError."""
    for key in orig_dict:
        if key in constants.RESERVED_PARAMS:
            msg = f"'{key}' is a reserved param name"
            raise ValueError(msg)


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


def read_main_script_params_with_smart_settings(
    settings_file: pathlib.Path,
    cmdline_settings: Optional[list[str]] = None,
    make_immutable: bool = True,
    dynamic: bool = True,
    pre_unpack_hooks: Optional[list] = None,
    post_unpack_hooks: Optional[list] = None,
) -> smart_settings.AttributeDict:
    """Read parameters for the cluster_utils main script using smart_settings.

    Args:
        settings_file:  Path to the settings file.
        cmdline_settings:  List of additional parameters provided via command line.
        make_immutable:  See ``smart_settings.load()``
        dynamic:  See ``smart_settings.load()``
        pre_unpack_hooks:  See ``smart_settings.load()``
        post_unpack_hooks:  See ``smart_settings.load()``

    Returns:
        Parameters as loaded by smart_settings.
    """
    cmdline_settings = cmdline_settings or []
    pre_unpack_hooks = pre_unpack_hooks or []
    post_unpack_hooks = post_unpack_hooks or []

    if not is_settings_file(os.fspath(settings_file)):
        raise ValueError(f"{settings_file} is not a supported settings file.")

    def add_cmd_params(orig_dict):
        add_cmd_line_params(orig_dict, cmdline_settings)

    return smart_settings.load(
        os.fspath(settings_file),
        make_immutable=make_immutable,
        dynamic=dynamic,
        post_unpack_hooks=([add_cmd_params, check_reserved_params] + post_unpack_hooks),
        pre_unpack_hooks=pre_unpack_hooks,
    )


def init_job_script_argument_parser() -> argparse.ArgumentParser:
    """Initialise ArgumentParser for job scripts."""

    def server_info(ip_and_port: str) -> dict[str, str | int]:
        """Split and validate string in "ip:port" format.  For use with argparse."""
        ip, port = ip_and_port.rsplit(":", maxsplit=1)
        if not port.isdigit():
            raise ValueError("Invalid port")
        return {"ip": ip, "port": int(port)}

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "parameter_file_or_dict",
        type=str,
        help="""
        Path to a configuration file or (if `--parameter-dict` is set) a string defining
        a Python dictionary with the parameters.
    """,
    )
    parser.add_argument(
        "parameter_overwrites",
        nargs="*",
        type=str,
        default=[],
        metavar="<key>=<value>",
        help="""Additional parameters in the format '<key>=<value>'.  Values provided
            here overwrite parameters provided via `parameter_file_or_dict`.  Key has to
            match a configuration option, value has to be a valid Python literal.
            Example: `'results_dir="/tmp"' 'optimization_setting.run_local=True'`
        """,
    )
    parser.add_argument(
        "--parameter-dict",
        action="store_true",
        help="""If set, `parameter_file_or_dict` is expected to be a dictionary instead
            of a file path.
        """,
    )
    parser.add_argument(
        "--job-id",
        type=int,
        metavar="<id>",
        help="""ID of the cluster_utils job (needed only if `--cluster-utils-server` is
            set).
        """,
    )
    parser.add_argument(
        "--cluster-utils-server",
        type=server_info,
        metavar="<host>:<port>",
        help="IP and port used to connect to the cluster_utils main process.",
    )

    return parser


def read_params_from_cmdline(
    cmd_line: Optional[list[str]] = None,
    make_immutable: bool = True,
    verbose: bool = True,
    dynamic: bool = True,
    save_params: bool = True,
) -> smart_settings.AttributeDict:
    """Read parameters based on command line input.

    Args:
        cmd_line:  Command line arguments (defaults to sys.argv).
        make_immutable:  See ``smart_settings.loads()``
        verbose:  If true, print the loaded parameters.
        dynamic:  See ``smart_settings.loads()``
        save_params:  If true, save the settings as JSON file in the working_dir.

    Returns:
        Parameters as loaded by smart_settings.
    """
    if not cmd_line:
        cmd_line = sys.argv

    parser = init_job_script_argument_parser()
    args = parser.parse_args(cmd_line[1:])

    # some argument validation which cannot be done by argparse directly
    if args.cluster_utils_server and args.job_id is None:
        parser.error("--job-id is required when --cluster-utils-server is set.")

    if args.cluster_utils_server:
        submission_state.communication_server_ip = args.cluster_utils_server["ip"]
        submission_state.communication_server_port = args.cluster_utils_server["port"]
        submission_state.job_id = args.job_id
        submission_state.connection_details_available = True
        submission_state.connection_active = False

    def add_cmd_params(orig_dict):
        add_cmd_line_params(orig_dict, args.parameter_overwrites)

    if args.parameter_dict:
        parameter_dict = ast.literal_eval(args.parameter_file_or_dict)
        if not isinstance(parameter_dict, dict):
            msg = (
                "'parameter_file_or_dict' must be a dictionary"
                " (`--parameter-dict` is set)."
            )
            raise ValueError(msg)

        final_params = smart_settings.loads(
            json.dumps(parameter_dict),
            make_immutable=make_immutable,
            dynamic=dynamic,
            post_unpack_hooks=([add_cmd_params, check_reserved_params]),
        )
    else:
        parameter_file = pathlib.Path(args.parameter_file_or_dict)
        if not parameter_file.is_file():
            msg = f"'{parameter_file}' does not exist or is not a file."
            raise FileNotFoundError(msg)

        final_params = smart_settings.load(
            os.fspath(parameter_file),
            make_immutable=make_immutable,
            dynamic=dynamic,
            post_unpack_hooks=([add_cmd_params, check_reserved_params]),
        )

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

    read_params_from_cmdline.start_time = time.time()  # type: ignore

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
