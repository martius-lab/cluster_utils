import csv
import itertools
import os
import random
import re
import shutil
from collections import defaultdict
from copy import deepcopy

from .constants import *


def check_valid_name(string):
  pat = '[A-Za-z0-9_.-]*$'
  if type(string) is not str:
    raise TypeError(('Parameter \'{}\' not valid. String expected.'.format(string)))
  if not bool(re.compile(pat).match(string)):
    raise ValueError('Parameter \'{}\' not valid. Only \'[0-9][a-z][A-Z]_-.\' allowed.'.format(string))
  if string.endswith('.') or string.startswith('.'):
    raise ValueError('Parameter \'{}\' not valid. \'.\' not allowed at start/end'.format(string))


def rm_dir_full(dir_name):
  if os.path.exists(dir_name):
    shutil.rmtree(dir_name, ignore_errors=True)


def create_dir(dir_name):
  if not os.path.exists(dir_name):
    os.makedirs(dir_name)


class default_value_dict(defaultdict):
  def __init__(self, default):
    super().__init__(lambda: deepcopy(default))


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


def get_sample_generator(samples, hyperparam_dict, distribution_list):
  if bool(hyperparam_dict) == bool(distribution_list):
    raise TypeError('Exactly one of hyperparam_dict and distribution list must be provided')
  if distribution_list and not samples:
    raise TypeError('Number of samples not specified')
  if distribution_list:
    return distribution_list_sampler(distribution_list, samples)
  if samples:
    assert hyperparam_dict
    return hyperparam_dict_samples(hyperparam_dict, samples)
  else:
    return hyperparam_dict_product(hyperparam_dict)

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
