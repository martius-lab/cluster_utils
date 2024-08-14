"""Client API of cluster_utils.

The cluster_utils client API is used in the job scripts implemented by the user and are
used to communicate with the cluster_utils server process.  Most important are
:func:`initialize_job`, which has to be called in the beginning to register with the
server, and :func:`finalize_job`, which is called in the end to send the results in the
end.
"""

# NOTE FOR DEVELOPERS: Since this sub-package is needed by the client, try to keep
# third-party dependencies here as minimal as possible.

from __future__ import annotations

import argparse
import ast
import atexit
import csv
import enum
import functools
import json
import os
import pathlib
import sys
import time
import warnings
from typing import Any, Mapping, MutableMapping, Optional

import smart_settings

from cluster_utils.base import constants
from cluster_utils.base.communication import MessageTypes
from cluster_utils.base.settings import add_cmd_line_params, check_reserved_params
from cluster_utils.base.utils import flatten_nested_string_dict

from . import server_communication as comm
from . import submission_state


class SettingsJsonEncoder(json.JSONEncoder):
    """JSON encoder that handles custom types used in the settings structure."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, enum.Enum):
            return obj.name

        return json.JSONEncoder.default(self, obj)


def _init_job_script_argument_parser() -> argparse.ArgumentParser:
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


def _save_settings_to_json(setting_dict, working_dir):
    filename = os.path.join(working_dir, constants.JSON_SETTINGS_FILE)
    with open(filename, "w") as file:
        json.dump(setting_dict, file, sort_keys=True, indent=4, cls=SettingsJsonEncoder)


def _sanitize_numpy_torch(possibly_np_or_tensor):
    # Hacky check for torch tensors without importing torch
    if str(type(possibly_np_or_tensor)) == "<class 'torch.Tensor'>":
        return possibly_np_or_tensor.item()  # silently convert to float
    if str(type(possibly_np_or_tensor)) == "<class 'numpy.ndarray'>":
        return float(possibly_np_or_tensor)
    return possibly_np_or_tensor


def _save_dict_as_one_line_csv(
    dct: Mapping[str, float], filename: str | os.PathLike
) -> None:
    with open(filename, "w") as f:
        writer = csv.DictWriter(f, fieldnames=dct.keys())
        writer.writeheader()
        writer.writerow(dct)


def read_params_from_cmdline(
    cmd_line: Optional[list[str]] = None,
    make_immutable: bool = True,
    verbose: bool = True,
    dynamic: bool = True,
    save_params: bool = True,
) -> smart_settings.param_classes.AttributeDict:
    """Alias for :func:`initialize_job`.

    Deprecated:
        This function is deprecated and will be removed in a future release.  Use
        :func:`initialize_job` instead.
    """
    warnings.warn(
        "`read_params_from_cmdline` is deprecated!  Use `initialize_job` instead.",
        FutureWarning,
        stacklevel=2,
    )

    if not make_immutable:
        msg = (
            "The option `make_immutable=False` is not supported anymore."
            " You can create a mutable copy of the parameters with"
            " `smart_settings.param_classes.AttributeDict(params)`"
        )
        raise RuntimeError(msg)

    if not save_params:
        msg = (
            "The option `save_params=False` is not supported anymore."
            " Parameters will always be saved."
        )
        raise RuntimeError(msg)

    return initialize_job(cmd_line, verbose=verbose, dynamic=dynamic)


def initialize_job(
    cmd_line: Optional[list[str]] = None,
    verbose: bool = True,
    dynamic: bool = True,
) -> smart_settings.param_classes.AttributeDict:
    """Read parameters from command line and register at cluster_utils server.

    This function is intended to be called at the beginning of your job scripts.  It
    does two things at once:

    1. parse the command line arguments to get the parameters for the job, and
    2. if server information is provided via command line arguments, register at the
       cluster_utils server (i.e. the main process, that orchestrates the job
       execution).

    Args:
        cmd_line:  Command line arguments (defaults to sys.argv).
        verbose:  If true, print the loaded parameters.
        dynamic:  See ``smart_settings.loads()``

    Returns:
        Parameters as loaded from the command line arguments with smart_settings.
    """
    if not cmd_line:
        cmd_line = sys.argv

    parser = _init_job_script_argument_parser()
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
            make_immutable=True,
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
            make_immutable=True,
            dynamic=dynamic,
            post_unpack_hooks=([add_cmd_params, check_reserved_params]),
        )

    if verbose:
        print(final_params)

    if (
        submission_state.connection_details_available
        and not submission_state.connection_active
    ):
        comm.register_at_server(final_params)
        sys.excepthook = comm.report_error_at_server
        atexit.register(comm.report_exit_at_server)
        comm.submission_state.connection_active = True

    submission_state.start_time = time.time()

    # TODO should probably rather be an assert, there should always be a working dir
    if "working_dir" in final_params:
        os.makedirs(final_params.working_dir, exist_ok=True)
        _save_settings_to_json(final_params, final_params.working_dir)

    return final_params


def save_metrics_params(metrics: MutableMapping[str, float], params) -> None:
    """Alias for :func:`finalize_job`.

    Deprecated:
        This function is deprecated and will be removed in a future release.  Use
        :func:`finalize_job` instead.
    """
    warnings.warn(
        "`save_metric_params` is deprecated!  Use `finalize_job` instead.",
        FutureWarning,
        stacklevel=2,
    )

    finalize_job(metrics, params)


def finalize_job(metrics: MutableMapping[str, float], params) -> None:
    """Save metrics and parameters and send metrics to the cluster_utils server.

    Save the used parameters and resulting metrics to CSV files (filenames defined by
    :attr:`~cluster_utils.base.constants.CLUSTER_PARAM_FILE` and
    :attr:`~cluster_utils.base.constants.CLUSTER_METRIC_FILE`) in the job's working
    directory and report the metrics to the cluster_utils main process.

    Make sure to call this function at the end of your job script, otherwise
    cluster_utils will not receive the resulting metrics and will consider the job as
    failed.

    Args:
        metrics:  Dictionary with metrics that should be sent to the server.
        params:  Parameters that were used to run the job (given by
            :func:`initialize_job`).
    """
    param_file = os.path.join(params.working_dir, constants.CLUSTER_PARAM_FILE)
    flattened_params = dict(flatten_nested_string_dict(params))
    _save_dict_as_one_line_csv(flattened_params, param_file)

    time_elapsed = time.time() - submission_state.start_time
    if "time_elapsed" not in metrics:
        metrics["time_elapsed"] = time_elapsed
    else:
        print(
            "WARNING: 'time_elapsed' metric already taken. Automatic time saving"
            " failed."
        )
    metric_file = os.path.join(params.working_dir, constants.CLUSTER_METRIC_FILE)

    for key, value in metrics.items():
        metrics[key] = _sanitize_numpy_torch(value)

    _save_dict_as_one_line_csv(metrics, metric_file)
    if submission_state.connection_active:
        comm.send_results_to_server(metrics)


def announce_early_results(metrics):
    """Report intermediate results to cluster_utils.

    Results reported with this function are by hyperparameter optimization to stop bad
    jobs early (see :confval:`kill_bad_jobs_early` option).

    Args:
        metrics:  Dictionary with metrics that should be sent to the server.
    """
    if not submission_state.connection_active:
        return

    sanitized = {key: _sanitize_numpy_torch(value) for key, value in metrics.items()}

    print(
        "Sending early results to: ",
        (
            submission_state.communication_server_ip,
            submission_state.communication_server_port,
        ),
    )
    comm.send_message(
        MessageTypes.METRIC_EARLY_REPORT, message=(submission_state.job_id, sanitized)
    )


def announce_fraction_finished(fraction_finished: float) -> None:
    """Report job progress to cluster_utils.

    You may use this function to report the progress of the job.  If done, the
    information is used by cluster_utils to estimate the remaining duration of the job.

    Args:
        fraction_finished: Value between 0 and 1, indicating the progress of the job.
    """
    if not submission_state.connection_active:
        return

    print(
        "Sending time estimate to: ",
        (
            submission_state.communication_server_ip,
            submission_state.communication_server_port,
        ),
    )
    comm.send_message(
        MessageTypes.JOB_PROGRESS_PERCENTAGE,
        message=(submission_state.job_id, fraction_finished),
    )


def exit_for_resume() -> None:
    """Send a "resume"-request to the cluster_utils server and exit with return code 3.

    Use this to split a single long-running job into multiple shorter jobs by frequently
    saving the state of the job (e.g. checkpoints) and restarting by calling this
    function.

    See :ref:`exit_for_resume` for more information.
    """
    if not submission_state.connection_active:
        # TODO: shouldn't it at least sys.exit() in any case?
        return
    atexit.unregister(comm.report_exit_at_server)  # Disable exit reporting
    comm.send_message(MessageTypes.EXIT_FOR_RESUME, message=(submission_state.job_id,))
    sys.exit(constants.RETURN_CODE_FOR_RESUME)


def cluster_main(main_func=None, **read_params_args):
    """Decorator for your main function to automatically register with cluster_utils.

    Use this as a decorator to automatically wrap a function (usually ``main``) with
    calls to :func:`initialize_job` and :func:`finalize_job`.

    The parameters read by :func:`initialize_job` will be passed as kwargs to the
    function.  Further, the function is expected to return the metrics dictionary as
    expected by :func:`finalize_job`.

    See :ref:`example_cluster_main_decorator` for an usage example.
    """
    if main_func is None:
        return functools.partial(cluster_main, **read_params_args)

    @functools.wraps(main_func)
    def wrapper():
        """Saves settings file on beginning, calls wrapped function with params from cmd
        and saves metrics to working_dir
        """
        params = initialize_job(**read_params_args)
        metrics = main_func(**params)
        finalize_job(metrics, params)
        return metrics

    return wrapper


__all__ = [
    "announce_early_results",
    "announce_fraction_finished",
    "cluster_main",
    "exit_for_resume",
    "finalize_job",
    "initialize_job",
    "save_metrics_params",
    "read_params_from_cmdline",
]
