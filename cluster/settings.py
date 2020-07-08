import ast
import atexit
import json
import os
import pickle
import sys
import time
import traceback
import socket
from datetime import datetime

import pyuv

import cluster.submission_state as submission_state
from cluster.utils import recursive_objectify, recursive_dynamic_json, load_json, update_recursive
from .communication_server import MessageTypes
from .constants import *
from .optimizers import Metaoptimizer, NGOptimizer, GridSearchOptimizer
from .utils import flatten_nested_string_dict, save_dict_as_one_line_csv


def save_settings_to_json(setting_dict, model_dir):
    filename = os.path.join(model_dir, JSON_SETTINGS_FILE)
    with open(filename, 'w') as file:
        file.write(json.dumps(setting_dict, sort_keys=True, indent=4))


def send_results_to_server(metrics):
    print('Sending results to: ',
          (submission_state.communication_server_ip, submission_state.communication_server_port))
    send_message(MessageTypes.JOB_SENT_RESULTS, message=(submission_state.job_id, metrics))


def send_message(message_type, message):
    loop = pyuv.Loop.default_loop()
    udp = pyuv.UDP(loop)
    udp.try_send((submission_state.communication_server_ip, submission_state.communication_server_port),
                 pickle.dumps((message_type, message)))


def announce_fraction_finished(fraction_finished):
    if not submission_state.connection_active:
        return

    print('Sending time estimate to: ',
          (submission_state.communication_server_ip, submission_state.communication_server_port))
    send_message(MessageTypes.JOB_PROGRESS_PERCENTAGE, message=(submission_state.job_id, fraction_finished))


def announce_early_results(metrics):
    if not submission_state.connection_active:
        return

    sanitized = {key: sanitize_numpy_torch(value) for key, value in metrics.items()}

    print('Sending early results to: ',
          (submission_state.communication_server_ip, submission_state.communication_server_port))
    send_message(MessageTypes.METRIC_EARLY_REPORT, message=(submission_state.job_id, sanitized))


def exit_for_resume():
    if not submission_state.connection_active:
        return
    atexit.unregister(report_exit_at_server)  # Disable exit reporting
    send_message(MessageTypes.EXIT_FOR_RESUME, message=(submission_state.job_id,))
    sys.exit(3)  # With exit code 3 for resume


def sanitize_numpy_torch(possibly_np_or_tensor):
    if str(type(possibly_np_or_tensor)) == "<class 'torch.Tensor'>":  # Hacky check for torch tensors without importing torch
        return possibly_np_or_tensor.item()  # silently convert to float
    if str(type(possibly_np_or_tensor)) == "<class 'numpy.ndarray'>":
        return float(possibly_np_or_tensor)
    return possibly_np_or_tensor


def save_metrics_params(metrics, params, save_dir=None):
    if save_dir is None:
        save_dir = params.model_dir
    os.makedirs(save_dir, exist_ok=True)
    save_settings_to_json(params, save_dir)

    param_file = os.path.join(save_dir, CLUSTER_PARAM_FILE)
    flattened_params = dict(flatten_nested_string_dict(params))
    save_dict_as_one_line_csv(flattened_params, param_file)

    time_elapsed = time.time() - update_params_from_cmdline.start_time
    if 'time_elapsed' not in metrics.keys():
        metrics['time_elapsed'] = time_elapsed
    else:
        print('WARNING: \'time_elapsed\' metric already taken. Automatic time saving failed.')
    metric_file = os.path.join(save_dir, CLUSTER_METRIC_FILE)

    for key, value in metrics.items():
        metrics[key] = sanitize_numpy_torch(value)

    save_dict_as_one_line_csv(metrics, metric_file)
    if submission_state.connection_active:
        send_results_to_server(metrics)


def is_json_file(cmd_line):
    if cmd_line.endswith('.json'):
        if not os.path.isfile(cmd_line):
            raise FileNotFoundError(f"{cmd_line}: No such JSON script found")
        return True
    else:
        return False


def is_parseable_dict(cmd_line):
    try:
        res = ast.literal_eval(cmd_line)
        return isinstance(res, dict)
    except Exception as e:
        print('WARNING: Dict literal eval suppressed exception: ', e)
        return False


def register_at_server(final_params):
    print('Sending registration to: ',
          (submission_state.communication_server_ip, submission_state.communication_server_port))
    send_message(MessageTypes.JOB_STARTED, message=(submission_state.job_id, socket.gethostname()))


def report_error_at_server(exctype, value, tb):
    print('Sending errors to: ',
          (submission_state.communication_server_ip, submission_state.communication_server_port))
    send_message(MessageTypes.ERROR_ENCOUNTERED, message=(
        submission_state.job_id, traceback.format_exception(exctype, value, tb)))


def report_exit_at_server():
    print('Sending confirmation of exit to: ',
          (submission_state.communication_server_ip, submission_state.communication_server_port))
    send_message(MessageTypes.JOB_CONCLUDED, message=(submission_state.job_id,))

def add_cmd_line_params(base_dict, extra_flags):
    for extra_flag in extra_flags:
        lhs, eq, rhs = extra_flag.rpartition('=')
        parsed_lhs = lhs.split('.')
        new_lhs = "base_dict" + "".join([f'[\"{item}\"]' for item in parsed_lhs])
        cmd = new_lhs + eq + rhs
        try:
            exec(cmd)
        except:
            raise RuntimeError(f"Command {cmd} failed")



def update_params_from_cmdline(cmd_line=None, default_params=None, custom_parser=None, make_immutable=True,
                               verbose=True, dynamic_json=True):
    """ Updates default settings based on command line input.

    :param cmd_line: Expecting (same format as) sys.argv
    :param default_params: Dictionary of default params
    :param custom_parser: callable that returns a dict of params on success
    and None on failure (suppress exceptions!)
    :param verbose: Boolean to determine if final settings are pretty printed
    :return: Immutable nested dict with (deep) dot access. Priority: default_params < default_json < cmd_line
    """

    if not cmd_line:
        cmd_line = sys.argv

    if default_params is None:
        default_params = {}

    try:
        connection_details = ast.literal_eval(cmd_line[1])
        submission_state.communication_server_ip = connection_details['ip']
        submission_state.communication_server_port = connection_details['port']
        submission_state.job_id = connection_details['id']
        del cmd_line[1]
        submission_state.connection_details_available = True
        submission_state.connection_active = False
    except:
        # If no network connection is given, try fail silently.
        pass

    if len(cmd_line) < 2:
        cmd_params = {}
    elif custom_parser and custom_parser(cmd_line):  # Custom parsing, typically for flags
        cmd_params = custom_parser(cmd_line)
    elif is_json_file(cmd_line[1]):
        cmd_params = load_json(cmd_line[1])
        add_cmd_line_params(cmd_params, cmd_line[2:])
    elif len(cmd_line) == 2 and is_parseable_dict(cmd_line[1]):
        cmd_params = ast.literal_eval(cmd_line[1])
    else:
        raise ValueError('Failed to parse command line')

    update_recursive(default_params, cmd_params)

    if JSON_FILE_KEY in default_params:
        json_params = load_json(default_params[JSON_FILE_KEY])
        if JSON_FILE_KEY in json_params:
            json_base = load_json(json_params[JSON_FILE_KEY])
        else:
            json_base = {}
        update_recursive(json_base, json_params)
        update_recursive(default_params, json_base)

    update_recursive(default_params, cmd_params)

    if "__timestamp__" in default_params:
        raise ValueError("Parameter name __timestamp__ is reserved!")

    if dynamic_json:
        objectified = recursive_objectify(default_params, make_immutable=make_immutable)
        timestamp = datetime.now().strftime('%H:%M:%S-%d%h%y')
        namespace = dict(__timestamp__=timestamp, **objectified)
        recursive_dynamic_json(default_params, namespace)
    final_params = recursive_objectify(default_params, make_immutable=make_immutable)

    if verbose:
        print(json.dumps(final_params, indent=4, sort_keys=True))

    if submission_state.connection_details_available and not submission_state.connection_active:
        register_at_server(final_params.get_pickleable())
        sys.excepthook = report_error_at_server
        atexit.register(report_exit_at_server)
        submission_state.connection_active = True
    update_params_from_cmdline.start_time = time.time()
    return final_params


update_params_from_cmdline.start_time = None

optimizer_dict = {'cem_metaoptimizer': Metaoptimizer,
                  'nevergrad': NGOptimizer,
                  'gridsearch': GridSearchOptimizer}
