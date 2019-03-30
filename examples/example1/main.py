import numpy as np

from cluster import save_metrics_params, update_params_from_cmdline


def fn_to_optimize(*, u, v, w, x, y, z, flag, **kwargs):
  result = (x - 3.14) ** 2 + (y - 2.78) ** 2 + (u * v * w + 1) ** 2 + (u + v + w + z - 5) ** 2
  result += 0.5 * np.random.normal()
  #if (x-3.14) ** 2 < 0.5 and flag:
  #  result += 3.0
  return result


# Default values of params
default_params = {'model_dir': '.',
                  'u': 0.0,
                  'v': 0.0,
                  'w': 0.0,
                  'x': 0.0,
                  'y': 0.0,
                  'z': 0.0,
                  }

params = update_params_from_cmdline(default_params=default_params)

result = fn_to_optimize(**params)

metrics = {'result': result}
save_metrics_params(metrics, params)
