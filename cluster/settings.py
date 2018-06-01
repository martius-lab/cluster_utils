from copy import deepcopy
import os
import json
import collections
import ast
import sys
from .utils import flatten_nested_string_dict, save_dict_as_one_line_csv, create_dir
from .constants import *
from . import export


class ParamDict(dict):
  """ An immutable dict where elements can be accessed with a dot"""
  __getattr__ = dict.get

  def __delattr__(self, item):
    raise TypeError("Setting object not mutable after settings are fixed!")

  def __setattr__(self, key, value):
    raise TypeError("Setting object not mutable after settings are fixed!")

  def __setitem__(self, key, value):
    raise TypeError("Setting object not mutable after settings are fixed!")

  def __deepcopy__(self, memo):
    """ In order to support deepcopy"""
    return ParamDict([(deepcopy(k, memo), deepcopy(v, memo)) for k, v in self.items()])


def recursive_objectify(nested_dict):
  result = deepcopy(nested_dict)
  for k, v in result.items():
    if isinstance(v, collections.Mapping):
      result[k] = recursive_objectify(v)
  return ParamDict(result)


def load_json(file):
  with open(file, 'r') as f:
    data = json.load(f)
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
    file.write(json.dumps(setting_dict))


@export
def save_metrics_params(metrics, params, model_dir):
  create_dir(model_dir)
  save_settings_to_json(params, model_dir)

  param_file = os.path.join(model_dir, CLUSTER_PARAM_FILE)
  flattened_params = dict(flatten_nested_string_dict(params))
  save_dict_as_one_line_csv(flattened_params, param_file)

  metric_file = os.path.join(model_dir, CLUSTER_METRIC_FILE)
  save_dict_as_one_line_csv(metrics, metric_file)


def is_json_file(cmd_line):
  try:
    return os.path.isfile(cmd_line)
  except Exception as e:
    print('JSON parsing suppressed exception: ', e)
    return False


def is_parseable_dict(cmd_line):
  try:
    res = ast.literal_eval(cmd_line)
    return isinstance(res, dict)
  except Exception as e:
    print('Dict literal eval suppressed exception: ', e)
    return False


@export
def update_params_from_cmdline(cmd_line=None, default_params=None, custom_parser=None, verbose=True):
  """

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
      print('WARNING: JSON file referencing another JSON! Ignoring...')
    update_recursive(default_params, json_params)

  update_recursive(default_params, cmd_params)
  final_params = recursive_objectify(default_params)
  if verbose:
    print(json.dumps(final_params, indent=4, sort_keys=True))
  return final_params
