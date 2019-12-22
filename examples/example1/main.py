import numpy as np
import time
from cluster import save_metrics_params, update_params_from_cmdline, exit_for_resume



def fn_to_optimize(*, u, v, w, x, y, sharp_penalty):
    """
    A dummy function to test hpo.

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

    if np.random.rand()>0.05:
        raise ValueError("5 percent of all jobs die here on purpose")

    return result


if __name__ == '__main__':
    params = update_params_from_cmdline()

    # simulate that the jobs take some time
    time.sleep(np.random.randint(0, 10))

    noiseless_result = fn_to_optimize(**params.fn_args)
    noisy_result = noiseless_result + 0.5 * np.random.normal()

    if np.random.rand() > 0.50:
        # Half of the jobs exit here just to be resubmitted (to be used with checkpointing)
        exit_for_resume(only_on_cluster_submissions=True)

    metrics = {'result': noisy_result, 'noiseless_result': noiseless_result}
    save_metrics_params(metrics, params)
    print(noiseless_result)
