import logging

from pathlib2 import Path
import collections
import csv
import inspect
import itertools
import json
import os
import random
import re
import shutil
from collections import defaultdict
import tempfile
from copy import deepcopy
from time import sleep
import git

from .constants import *


logger = logging.getLogger('cluster_utils')


def shorten_string(string, max_len):
    if len(string) > max_len - 3:
        return '...' + string[-max_len + 3:]
    return string


def check_valid_name(string):
    pat = '[A-Za-z0-9_.-:]*$'
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
        check_valid_name(name)
        if name in name_list:
            raise ValueError('Duplicate setting \'{}\' in other params!'.format(name))
        value = tuple(value) if isinstance(value,list) else value
        if not any([isinstance(value, allowed_type) for allowed_type in PARAM_TYPES]):
            raise TypeError('Settings must from the following types: {}, not {}'.format(PARAM_TYPES, type(value)))
    nested_items = [(name.split('.'), value) for name, value in other_params.items()]
    return nested_to_dict(nested_items)


def validate_hyperparam_dict(hyperparam_dict):
    for name, option_list in hyperparam_dict.items():
        check_valid_name(name)
        if type(option_list) is not list:
            raise TypeError('Entries in hyperparam dict must be type list (not {}: {})'.format(name, type(option_list)))
        option_list = [ o if not isinstance(o, list) else tuple(o) for o in option_list]
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

    nested_items = [(name.split(OBJECT_SEPARATOR), options) for name, options in hyperparam_dict.items()]
    nested_names, option_lists = zip(*nested_items)

    for sample_from_product in itertools.product(*list(option_lists)):
        yield nested_to_dict(zip(nested_names, sample_from_product))


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


def get_git_url():
    try:
        repo = git.Repo(search_parent_directories=True)
    except git.exc.InvalidGitRepositoryError:
        return None

    url_list = list(repo.remotes.origin.urls)
    if url_list:
        logger.info(f"Auto-detected git repository with remote url: {url_list[0]}")
        return url_list[0]

    return None


def dict_to_dirname(setting, id, smart_naming=True):
    vals = ['{}={}'.format(str(key)[:3], str(value)[:6])
            for key, value in setting.items() if not isinstance(value, dict)]
    res = '{}_{}'.format(id, '_'.join(vals))
    if len(res) < 35 and smart_naming:
        return res
    return str(id)


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


def recursive_dynamic_json(nested_dict_or_list, namespace):
    "Evaluates each key in nested dict as an f-string within a given namespace"
    if isinstance(nested_dict_or_list, collections.Mapping):
        for k, v in nested_dict_or_list.items():
            if isinstance(v, collections.Mapping) or isinstance(v, list):
                recursive_dynamic_json(v, namespace)
            else:
                nested_dict_or_list[k] = fstring_in_json(v, namespace)
    elif isinstance(nested_dict_or_list, list):
        for i, item in enumerate(nested_dict_or_list):
            if isinstance(item, collections.Mapping) or isinstance(item, list):
                recursive_dynamic_json(item, namespace)
            else:
                nested_dict_or_list[i] = fstring_in_json(item, namespace)


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
