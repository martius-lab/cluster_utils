import ast
import sys
import os
import random
import csv

def create_dir(dir_name):
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)

def save_dict_as_one_line_csv(dct, filename):
    with open(filename, 'w') as f:
        writer = csv.DictWriter(f, fieldnames=dct.keys())
        writer.writeheader()
        writer.writerow(dct)

def flatten_nested_string_dict(nested_dict, prepend=''):
    for key, value in nested_dict.items():
        if type(key) is not str:
            raise TypeError('Only strings as keys expected')
        if type(value) is dict:
            for sub in flatten_nested_string_dict(value, prepend=prepend + str(key) + '-'):
                yield sub
        else:
            yield prepend + str(key), value


# Default values of params
params = {'caro': 'not that hot',
          'x': 0.0,
          'y': 0.0,
          'z': 0.0,
          'w': 0.0}

if len(sys.argv) > 1:
    arg = sys.argv[1]
    read_params = ast.literal_eval(arg)
    params.update(read_params)
    out_dir = params['model_dir']
    create_dir(out_dir)
    param_file = os.path.join(out_dir, 'param_choice.csv')

    flattened_params = dict(flatten_nested_string_dict(params))
    save_dict_as_one_line_csv(flattened_params, param_file)

    #x, y, z, w = params['x'], params['y'], params['z'], params['w']
    x, y = params['num']['x'], params['num']['y']
    z, w = params['num']['num']['x'], params['num']['num']['y']
    result = (x-2.0) ** 2 + (y-4.66) ** 2 + (z*w - 6) ** 2 + (z+w-5) ** 2
    metrics = {'result': -result}

    metric_file = os.path.join(out_dir, 'metrics.csv')
    save_dict_as_one_line_csv(metrics, metric_file)
else:
    raise ValueError('Give me some parameters, you fucker!')

sys.exit(0)
