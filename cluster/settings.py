import ast
import collections
from datetime import datetime
import json
import os
import sys
from copy import deepcopy
from warnings import warn
import time
import pyuv
import pickle
from .optimizers import Metaoptimizer, NGOptimizer, GridSearchOptimizer
from .constants import *
from .utils import flatten_nested_string_dict, save_dict_as_one_line_csv, create_dir
import cluster.submission_state as submission_state

class ParamDict(dict):
  """ An immutable dict where elements can be accessed with a dot"""

  def __getattr__(self, *args, **kwargs):
    try:
      return self.__getitem__(*args, **kwargs)
    except KeyError as e:
      raise AttributeError(e)

  def __delattr__(self, item):
    raise TypeError("Setting object not mutable after settings are fixed!")

  def __setattr__(self, key, value):
    raise TypeError("Setting object not mutable after settings are fixed!")

  def __setitem__(self, key, value):
    raise TypeError("Setting object not mutable after settings are fixed!")

  def __deepcopy__(self, memo):
    """ In order to support deepcopy"""
    return ParamDict([(deepcopy(k, memo), deepcopy(v, memo)) for k, v in self.items()])

  def __repr__(self):
    return json.dumps(self, indent=4, sort_keys=True)

  def get_pickleable(self):
    return recursive_objectify(self, make_immutable=False)


def recursive_objectify(nested_dict, make_immutable=True):
  "Turns a nested_dict into a nested ParamDict"
  result = deepcopy(nested_dict)
  for k, v in result.items():
    if isinstance(v, collections.Mapping):
      result = dict(result)
      result[k] = recursive_objectify(v, make_immutable)
  if make_immutable:
    returned_result = ParamDict(result)
  else:
    returned_result = dict(result)
  return returned_result


def fstring_in_json(format_string, namespace):
  if type(format_string) != str:
    return format_string
  try:
    formatted = eval('f\"' + format_string + '\"', namespace)
  except:
    return format_string

  if formatted == format_string:
    return format_string

  try:
    return eval(formatted, dict(__builtins__=None))
  except:
    return formatted


def recursive_dynamic_json(nested_dict, namespace):
  "Evaluates each key in nested dict as an f-string within a given namespace"
  for k, v in nested_dict.items():
    if isinstance(v, collections.Mapping):
      recursive_dynamic_json(v, namespace)
    else:
      nested_dict[k] = fstring_in_json(v, namespace)


class SafeDict(dict):
  """ A dict with prohibiting init from a list of pairs containing duplicates"""

  def __init__(self, *args, **kwargs):
    if args and args[0] and not isinstance(args[0], dict):
      keys, _ = zip(*args[0])
      duplicates = [item for item, count in collections.Counter(keys).items() if count > 1]
      if duplicates:
        raise TypeError("Keys {} repeated in json parsing".format(duplicates))
    super().__init__(*args, **kwargs)


def load_json(file):
  """ Safe load of a json file (doubled entries raise exception)"""
  with open(file, 'r') as f:
    data = json.load(f, object_pairs_hook=SafeDict)
  return data


def update_recursive(d, u, defensive=False):
  for k, v in u.items():
    if defensive and k not in d:
      raise KeyError("Updating a non-existing key")
    if isinstance(v, collections.Mapping):
      d[k] = update_recursive(d.get(k, {}), v)
    else:
      d[k] = v
  return d


def save_settings_to_json(setting_dict, model_dir):
  filename = os.path.join(model_dir, JSON_SETTINGS_FILE)
  with open(filename, 'w') as file:
    file.write(json.dumps(setting_dict, sort_keys=True, indent=4))


def confirm_exit_at_server(metrics):
  print('Sending confirmation of exit to: ',
        (submission_state.communication_server_ip, submission_state.communication_server_port))
  loop = pyuv.Loop.default_loop()
  udp = pyuv.UDP(loop)
  udp.try_send((submission_state.communication_server_ip, submission_state.communication_server_port),
               pickle.dumps((2, (submission_state.job_id, metrics))))


def save_metrics_params(metrics, params, save_dir=None):
  if save_dir is None:
    save_dir = params.model_dir
  create_dir(save_dir)
  save_settings_to_json(params, save_dir)

  param_file = os.path.join(save_dir, CLUSTER_PARAM_FILE)
  flattened_params = dict(flatten_nested_string_dict(params))
  save_dict_as_one_line_csv(flattened_params, param_file)

  time_elapsed = time.time() - update_params_from_cmdline.start_time
  if 'time_elapsed' not in metrics.keys():
    metrics['time_elapsed'] = time_elapsed
  else:
    warn('\'time_elapsed\' metric already taken. Automatic time saving failed.')
  metric_file = os.path.join(save_dir, CLUSTER_METRIC_FILE)
  save_dict_as_one_line_csv(metrics, metric_file)
  confirm_exit_at_server(metrics)


def is_json_file(cmd_line):
  try:
    return os.path.isfile(cmd_line)
  except Exception as e:
    warn('JSON parsing suppressed exception: ', e)
    return False


def is_parseable_dict(cmd_line):
  try:
    res = ast.literal_eval(cmd_line)
    return isinstance(res, dict)
  except Exception as e:
    warn('Dict literal eval suppressed exception: ', e)
    return False


def register_at_server(final_params):
  print('Sending registration to: ',
        (submission_state.communication_server_ip, submission_state.communication_server_port))
  loop = pyuv.Loop.default_loop()
  udp = pyuv.UDP(loop)
  udp.try_send((submission_state.communication_server_ip, submission_state.communication_server_port),
               pickle.dumps((0, (submission_state.job_id,))))

def report_error_at_server(exctype, value, tb):
  print('Sending errors to: ',
        (submission_state.communication_server_ip, submission_state.communication_server_port))
  loop = pyuv.Loop.default_loop()
  udp = pyuv.UDP(loop)
  udp.try_send((submission_state.communication_server_ip, submission_state.communication_server_port),
               pickle.dumps((1, (submission_state.job_id, exctype, value, tb))))


def update_params_from_cmdline(cmd_line=None, default_params=None, custom_parser=None, make_immutable=True,
                               verbose=True, dynamic_json=True):
  """ Updates default settings based on command line input.

  :param cmd_line: Expecting (same format as) sys.argv
  :param default_params: Dictionary of default params
  :param custom_parser: callable that returns a dict of params on success
  and None on failure (suppress exceptions!)
  :param register_job: Boolean whether to register the job to the communication server
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
    register_job = True
  except:
    print("Could not parse connection info, presuming the job to be run locally")
    e = sys.exc_info()[0]
    print(str(e))
    register_job = False

  if len(cmd_line) < 2:
    cmd_params = {}
  elif custom_parser and custom_parser(cmd_line):  # Custom parsing, typically for flags
    cmd_params = custom_parser(cmd_line)
  elif len(cmd_line) == 2 and is_json_file(cmd_line[1]):
    cmd_params = load_json(cmd_line[1])
  elif len(cmd_line) == 2 and is_parseable_dict(cmd_line[1]):
    cmd_params = ast.literal_eval(cmd_line[1])
  else:
    raise ValueError('Failed to parse command line')

  update_recursive(default_params, cmd_params)

  if JSON_FILE_KEY in default_params:
    json_params = load_json(default_params[JSON_FILE_KEY])
    if 'default_json' in json_params:
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

  if register_job:
    register_at_server(final_params.get_pickleable())
    sys.excepthook = report_error_at_server
  update_params_from_cmdline.start_time = time.time()
  return final_params


update_params_from_cmdline.start_time = None

optimizer_dict = {'cem_metaoptimizer': Metaoptimizer,
                  'ng': NGOptimizer,
                  'gridsearch': GridSearchOptimizer}
