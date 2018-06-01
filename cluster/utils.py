import collections
import csv
import copy
import itertools
import random
import os
import shutil
from copy import deepcopy
from collections import defaultdict
from .constants import *


def rm_dir_full(dir_name):
    if os.path.exists(dir_name):
        shutil.rmtree(dir_name, ignore_errors=True)

def create_dir(dir_name):
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)

class default_value_dict(defaultdict):
    def __init__(self, default):
        super().__init__(lambda: deepcopy(default))


def is_iterable_nonstring(obj):
    return isinstance(obj, collections.Iterable) and type(obj) is not str


def flatten_nested_string_dict(nested_dict, prepend=''):
    for key, value in nested_dict.items():
        if type(key) is not str:
            raise TypeError('Only strings as keys expected')
        if isinstance(value, dict):
            for sub in flatten_nested_string_dict(value, prepend=prepend+str(key)+OBJECT_SEPARATOR):
                yield sub
        else:
            yield prepend+str(key), value


def flatten_nested_dict(nested_dict):
    for key, value in nested_dict.items():
        if type(value) is dict:
            for sub in flatten_nested_dict(value):
                yield sub
        else:
            yield key, value


def flatten_nested_list_dict(object_structure):
    for item in object_structure:
        if type(item) is dict:
            for sub in flatten_nested_list_dict(item.values()):
                yield sub
        elif is_iterable_nonstring(item):
            for sub in flatten_nested_list_dict(item):
                yield sub
        else:
            yield item


def save_dict_as_one_line_csv(dct, filename):
    with open(filename, 'w') as f:
        writer = csv.DictWriter(f, fieldnames=dct.keys())
        writer.writeheader()
        writer.writerow(dct)


def flattened_values(nested_dict):
    for key, val in sorted(nested_dict.items()):
        if type(val) is dict:
            for inside_val in flattened_values(val):
                yield inside_val
        else:
            yield val


def rewrite_structured_dict_values_from_iter(nested_dict, itervalues):
    for key in sorted(nested_dict):
        if type(nested_dict[key]) is dict:
            rewrite_structured_dict_values_from_iter(nested_dict[key], itervalues)
        else:
            nested_dict[key] = next(itervalues)


def nested_dict_hyperparam_product(nested_dict_of_lists):
    value_lists = flattened_values(nested_dict_of_lists)
    for value_product_element in itertools.product(*list(value_lists)):
        template = copy.deepcopy(nested_dict_of_lists)
        iterator = iter(value_product_element)
        rewrite_structured_dict_values_from_iter(template, iterator)
        try:
            next(iterator)
            assert False
            # Iterator should be wasted
        except StopIteration:
            pass
        yield template

def sample_from_lists(*lists):
    return [random.choice(item) for item in lists]


def nested_dict_hyperparam_samples(nested_dict_of_lists, num_samples):
    value_lists = list(flattened_values(nested_dict_of_lists))
    for i in range(num_samples):
        value_sample = sample_from_lists(*value_lists)
        template = copy.deepcopy(nested_dict_of_lists)
        iterator = iter(value_sample)
        rewrite_structured_dict_values_from_iter(template, iterator)
        yield template


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
