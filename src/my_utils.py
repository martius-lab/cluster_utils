import collections
import csv
import copy
import itertools
import random
from copy import deepcopy


class default_value_dict(collections.defaultdict):
    def __init__(self, default):
        super().__init__(lambda: deepcopy(default))


def is_iterable_nonstring(obj):
    return isinstance(obj, collections.Iterable) and type(obj) is not str


def flatten_nested_string_dict(nested_dict, prepend=''):
    for key, value in nested_dict.items():
        if type(key) is not str:
            raise TypeError('Only strings as keys expected')
        if type(value) is dict:
            for sub in flatten_nested_string_dict(value, prepend=prepend+str(key)+'-'):
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

def distribution_list_sampler(distribution_list, num_samples):
    for i in range(num_samples):
        yield {distr.param_name: distr.sample() for distr in distribution_list}
