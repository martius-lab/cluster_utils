import sys
from time import sleep
import numpy as np

## Do NOT INCLUDE this in your code ... just my testing
sys.path = ['/is/sg/mrolinek/Projects/Cluster_utils'] + sys.path

from cluster import save_metrics_params, update_params_from_cmdline

# Default values of params
default_params = {'model_dir': '.',
                  'x': 1.0,
                  'y': 2.0,
                  'z': -7.5,
                  'w': 2.4,
                  'dc': {'num1': 1,'num2': 1}}


params = update_params_from_cmdline(default_params=default_params)
x, y, z, w = params.x, params.y, params.z, params.w

result = (x-2.0) ** 2 + (y-4.66) ** 2 + (z*w - 6) ** 2 + (z+w-5) ** 2
result += np.random.normal()

num1, num2 = params.dc.num1, params.dc.num2
dummy = num1/num2 + num2/num1

metrics = {'result': result}
save_metrics_params(metrics, params, model_dir=params.model_dir)


"""
def parse_args(cmd_line=None):
    parser = argparse.ArgumentParser()

    parser.add_argument('--epoch', type=int, default=20, help='The number of epochs to run')
    parser.add_argument('--batch_size', type=int, default=64, help='The size of batch')

    try:
        return vars(parser.parse_args())
    except SystemExit:
        print('Flag parsing failed')
        return None
"""