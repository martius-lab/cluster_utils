import numpy as np

from cluster import save_metrics_params, update_params_from_cmdline




def fn_to_optimize(*, u, v, w, x, y, sharp_penalty, noisy=True):
    """
    :param u: real variable
    :param v: integer variable living on logscale
    :param w: integer variable
    :param x: real variable
    :param y: real variable living on log-scale
    :param sharp_penalty: discrete variable
    :param noisy: flag for noise addition
    :return: result of some random computation
    """
    y_log = np.log(np.abs(y+1e-7))
    v_log = np.log(np.abs(v+1e-7))
    assert (type(w) == type(v) == int), "w and v have to be integers"

    result = (x - 3.14) ** 2 + (y_log - 2.78) ** 2 + (u * v_log * w + 1) ** 2 + (u + v_log + w - 5) ** 2
    if sharp_penalty and x > 3.20:
        result += 1

    if noisy:
        result += 0.5 * np.random.normal()

    return result


if __name__ == '__main__':
    params = update_params_from_cmdline()
    result = fn_to_optimize(**params.fn_args)

    metrics = {'result': result, 'noiseless_result': fn_to_optimize(**dict(**params.fn_args, noisy=False))}
    save_metrics_params(metrics, params)
    print(result)
