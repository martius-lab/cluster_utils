import collections
import csv
import itertools
import logging
import os
import random
import re
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path
from time import sleep

from .constants import *



def shorten_string(string, max_len):
    if len(string) > max_len - 3:
        return '...' + string[-max_len + 3:]
    return string

def list_to_tuple(maybe_list):
    if isinstance(maybe_list,list):
        return tuple(maybe_list)
    else:
        return maybe_list

def check_valid_param_name(string):
    pat = '[A-Za-z0-9_.-:]*$'
    if type(string) is not str:
        raise TypeError(('Parameter \'{}\' not valid. String expected.'.format(string)))
    if string in RESERVED_PARAMS + [WORKING_DIR]:  # working_dir cannot be injected in grid_search/hpo
        raise ValueError('Parameter name {} is reserved, cannot be overwritten from outside.'.format(string))
    if string.endswith(STD_ENDING):
        raise ValueError('Parameter name \'{}\' not valid.'
                         'Ends with \'{}\' (may cause collisions)'.format(string, STD_ENDING))
    if not bool(re.compile(pat).match(string)):
        raise ValueError('Parameter name \'{}\' not valid. Only \'[0-9][a-z][A-Z]_-.\' allowed.'.format(string))
    if string.startswith('.') or string.endswith('.'):
        raise ValueError('Parameter name \'{}\' not valid. \'.\' not allowed the end'.format(string))


def rm_dir_full(dir_name):
    logger = logging.getLogger('cluster_utils')
    sleep(0.5)
    if os.path.exists(dir_name):
        shutil.rmtree(dir_name, ignore_errors=True)

    # filesystem is sometimes slow to response
    if os.path.exists(dir_name):
        sleep(1.0)
        shutil.rmtree(dir_name, ignore_errors=True)

    if os.path.exists(dir_name):
        logger.warning(f'Removing of dir {dir_name} failed')


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
    logger = logging.getLogger('cluster_utils')
    if hyperparam_dict and distribution_list:
        raise TypeError('At most one of hyperparam_dict and distribution list can be provided')
    if not hyperparam_dict and not distribution_list:
        logger.warning('No hyperparameters vary. Only running restarts')
        return iter([{}])
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
    elif distribution_list:
        name_list = [distr.param_name for distr in distribution_list]
    else:
        name_list = []
    for name, value in other_params.items():
        check_valid_param_name(name)
        if name in name_list:
            raise ValueError('Duplicate setting \'{}\' in other params!'.format(name))
        value = list_to_tuple(value)
        if not any([isinstance(value, allowed_type) for allowed_type in PARAM_TYPES]):
            raise TypeError('Settings must from the following types: {}, not {}'.format(PARAM_TYPES, type(value)))
    nested_items = [(list(filter(lambda x: x, name.split('.'))), value) for name, value in other_params.items()]
    return nested_to_dict(nested_items)


def validate_hyperparam_dict(hyperparam_dict):
    for name, option_list in hyperparam_dict.items():
        if isinstance(name, tuple):
            [check_valid_param_name(n) for n in name]
        else:
            check_valid_param_name(name)
        if type(option_list) is not list:
            raise TypeError('Entries in hyperparam dict must be type list (not {}: {})'.format(name, type(option_list)))
        option_list = [ list_to_tuple(o) for o in option_list]
        hyperparam_dict[name]=option_list
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
    names, option_lists = zip(*hyperparam_dict.items())

    for sample_from_product in itertools.product(*list(option_lists)):
        list_of_samples = []
        for name_or_tuple, option_or_tuple in zip(names, sample_from_product):
            if isinstance(name_or_tuple, tuple):  # in case we specify a tuple/list of keys and values we unzip them here
                list_of_samples.extend(zip(name_or_tuple, option_or_tuple))
            else:
                list_of_samples.append((name_or_tuple, option_or_tuple))
        nested_items = [(name.split(OBJECT_SEPARATOR), options) for name, options in list_of_samples]
        yield nested_to_dict(nested_items)

def default_to_regular(d):
    if isinstance(d, defaultdict):
        d = {k: default_to_regular(v) for k, v in d.items()}
    return d


def nested_to_dict(nested_items):
    def nested_dict(): return defaultdict(nested_dict)
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


home = str(Path.home())


def make_red(text):
    return f"\x1b[1;31m{text}\x1b[0m"


def mkdtemp(prefix='cluster_utils', suffix=''):
    new_prefix = prefix + ('' if not suffix else '-' + suffix + '-')
    return tempfile.mkdtemp(prefix=new_prefix, dir=os.path.join(home, '.cache'))


def temp_directory(prefix='cluster_utils', suffix=''):
    new_prefix = prefix + ('' if not suffix else '-' + suffix + '-')
    return tempfile.TemporaryDirectory(prefix=new_prefix, dir=os.path.join(home, '.cache'))


def dict_to_dirname(setting, id, smart_naming=True):
    vals = ['{}={}'.format(str(key)[:3], str(value)[:6])
            for key, value in setting.items() if not isinstance(value, dict)]
    res = '{}_{}'.format(id, '_'.join(vals))
    if len(res) < 35 and smart_naming:
        return res
    return str(id)


def update_recursive(d, u, defensive=False):
    for k, v in u.items():
        if defensive and k not in d:
            raise KeyError("Updating a non-existing key")
        if isinstance(v, collections.Mapping):
            d[k] = update_recursive(d.get(k, {}), v)
        else:
            d[k] = v
    return d


def check_import_in_fixed_params(setting_dict):
    if "fixed_params" in setting_dict:
        if "__import__" in setting_dict['fixed_params']:
            raise ImportError("Cannot import inside fixed params. Did you mean __import_promise__?")

def rename_import_promise(setting_dict):
    if "fixed_params" in setting_dict:
        if "__import_promise__" in setting_dict['fixed_params']:
            setting_dict['fixed_params']['__import__'] = setting_dict['fixed_params']['__import_promise__']
            del setting_dict['fixed_params']['__import_promise__']


def log_and_print(logger, msg):
    logger.info(msg)
    print(msg)
