import csv
import inspect
import itertools
import os
import random
import re
import shutil
from collections import defaultdict
import tempfile

from .constants import *


def shorten_string(string, max_len):
  if len(string) > max_len - 3:
    return '...' + string[-max_len + 3:]
  return string


def get_caller_file(depth=2):
  _, filename, _, _, _, _ = inspect.stack()[depth]
  return filename


def check_valid_name(string):
  pat = '[A-Za-z0-9_.-]*$'
  if type(string) is not str:
    raise TypeError(('Parameter \'{}\' not valid. String expected.'.format(string)))
  if string in RESERVED_PARAMS:
    raise ValueError('Parameter name {} is reserved'.format(string))
  if string.endswith(STD_ENDING):
    raise ValueError('Parameter name \'{}\' not valid.'
                     'Ends with \'{}\' (may cause collisions)'.format(string, STD_ENDING))
  if not bool(re.compile(pat).match(string)):
    raise ValueError('Parameter name \'{}\' not valid. Only \'[0-9][a-z][A-Z]_-.\' allowed.'.format(string))
  if string.endswith('.') or string.startswith('.'):
    raise ValueError('Parameter name \'{}\' not valid. \'.\' not allowed at start/end'.format(string))


def rm_dir_full(dir_name):
  if os.path.exists(dir_name):
    shutil.rmtree(dir_name, ignore_errors=True)


def create_dir(dir_name):
  if not os.path.exists(dir_name):
    os.makedirs(dir_name)


def flatten_nested_string_dict(nested_dict, prepend=''):
  for key, value in nested_dict.items():
    if type(key) is not str:
      raise TypeError('Only strings as keys expected')
    if isinstance(value, dict):
      for sub in flatten_nested_string_dict(value, prepend=prepend + str(key) + OBJECT_SEPARATOR):
        yield sub
    else:
      yield prepend + str(key), value


def save_dict_as_one_line_csv(dct, filename):
  with open(filename, 'w') as f:
    writer = csv.DictWriter(f, fieldnames=dct.keys())
    writer.writeheader()
    writer.writerow(dct)


def get_sample_generator(samples, hyperparam_dict, distribution_list, extra_settings=None):
  if bool(hyperparam_dict) == bool(distribution_list):
    raise TypeError('Exactly one of hyperparam_dict and distribution list must be provided')
  if distribution_list and not samples:
    raise TypeError('Number of samples not specified')
  if distribution_list:
    ans = distribution_list_sampler(distribution_list, samples)
  elif samples:
    assert hyperparam_dict
    ans = hyperparam_dict_samples(hyperparam_dict, samples)
  else:
    ans = hyperparam_dict_product(hyperparam_dict)
  if extra_settings is not None:
    return itertools.chain(extra_settings, ans)
  else:
    return ans





def process_other_params(other_params, hyperparam_dict, distribution_list):
  if hyperparam_dict:
    name_list = hyperparam_dict.keys()
  else:
    name_list = [distr.param_name for distr in distribution_list]
  for name, value in other_params.items():
    check_valid_name(name)
    if name in name_list:
      raise ValueError('Duplicate setting \'{}\' in other params!'.format(name))
    if not any([isinstance(value, allowed_type) for allowed_type in PARAM_TYPES]):
      raise TypeError('Settings must from the following types: {}, not {}'.format(PARAM_TYPES, type(value)))
  nested_items = [(name.split('.'), value) for name, value in other_params.items()]
  return nested_to_dict(nested_items)


def validate_hyperparam_dict(hyperparam_dict):
  for name, option_list in hyperparam_dict.items():
    check_valid_name(name)
    if type(option_list) is not list:
      raise TypeError('Entries in hyperparam dict must be type list (not {}: {})'.format(name, type(option_list)))
    for item in option_list:
      if not any([isinstance(item, allowed_type) for allowed_type in PARAM_TYPES]):
        raise TypeError('Settings must from the following types: {}, not {}'.format(PARAM_TYPES, type(item)))


def hyperparam_dict_samples(hyperparam_dict, num_samples):
  validate_hyperparam_dict(hyperparam_dict)
  nested_items = [(name.split(OBJECT_SEPARATOR), options) for name, options in hyperparam_dict.items()]

  for i in range(num_samples):
    nested_samples = [(nested_path, random.choice(options)) for nested_path, options in nested_items]
    yield nested_to_dict(nested_samples)


def hyperparam_dict_product(hyperparam_dict):
  validate_hyperparam_dict(hyperparam_dict)

  nested_items = [(name.split(OBJECT_SEPARATOR), options) for name, options in hyperparam_dict.items()]
  nested_names, option_lists = zip(*nested_items)

  for sample_from_product in itertools.product(*list(option_lists)):
    yield nested_to_dict(zip(nested_names, sample_from_product))


def default_to_regular(d):
  if isinstance(d, defaultdict):
    d = {k: default_to_regular(v) for k, v in d.items()}
  return d


def nested_to_dict(nested_items):
  nested_dict = lambda: defaultdict(nested_dict)
  result = nested_dict()
  for nested_key, value in nested_items:
    ptr = result
    for key in nested_key[:-1]:
      ptr = ptr[key]
    ptr[nested_key[-1]] = value
  return default_to_regular(result)


def distribution_list_sampler(distribution_list, num_samples):
  for distr in distribution_list:
    distr.prepare_samples(howmany=num_samples)
  for i in range(num_samples):
    nested_items = [(distr.param_name.split(OBJECT_SEPARATOR), distr.sample()) for distr in distribution_list]
    yield nested_to_dict(nested_items)

from pathlib2 import Path
home = str(Path.home())

def mkdtemp(prefix='cluster_utils', suffix=''):
  new_prefix = prefix + ('' if not suffix else '-' + suffix + '-')
  return tempfile.mkdtemp(prefix=new_prefix, dir=os.path.join(home, '.cache'))


def temp_directory(prefix='cluster_utils', suffix=''):
  new_prefix = prefix + ('' if not suffix else '-' + suffix + '-')
  return tempfile.TemporaryDirectory(prefix=new_prefix, dir=os.path.join(home, '.cache'))


