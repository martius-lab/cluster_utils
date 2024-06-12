import os
import time

import numpy as np

from cluster_utils import exit_for_resume, finalize_job, initialize_job


def fn_to_optimize(*, u, v, w, x, y, sharp_penalty, tuple_input=None):
    """
    A dummy function to test hpo.

    :param u: real variable
    :param v: integer variable living on logscale
    :param w: integer variable
    :param x: real variable
    :param y: real variable living on log-scale
    :param sharp_penalty: discrete variable
    :param tuple_input: a tuple (we only use its length here)
    :return: result of some random computation
    """
    tuple_input = tuple_input or tuple()
    tuple_len = len(tuple_input)
    y_log = np.log(np.abs(y + 1e-7))
    v_log = np.log(np.abs(v + 1e-7))
    assert isinstance(w, int), "w has to be integer"
    assert isinstance(v, int), "v has to be integer"

    result = (
        (x - 3.14) ** 2
        + (y_log - 2.78) ** 2
        + (u * v_log * w + 1) ** 2
        + (u + v_log + w - 5 + tuple_len) ** 2
    )
    if sharp_penalty and x > 3.20:
        result += 1

    if np.random.rand() < 0.1:
        raise ValueError("10 percent of all jobs die here on purpose")

    return result


if __name__ == "__main__":
    # Error before update_params (has separate handling)
    if np.random.rand() < 0.05:
        raise ValueError("5 percent of all jobs die early for testing")

    params = initialize_job()

    # simulate that the jobs take some time
    max_sleep_time = params.get("max_sleep_time", 10)
    time.sleep(np.random.randint(0, max_sleep_time))

    result_file = os.path.join(params.working_dir, "result.npy")
    os.makedirs(params.working_dir, exist_ok=True)
    # here we do a little simulation for checkpointing and resuming
    if os.path.isfile(result_file):
        # If there is a result to resume
        noiseless_result = np.load(result_file)
    else:
        # Otherwise compute result, checkpoint it and exit
        noiseless_result = fn_to_optimize(**params.fn_args)
        print(f"save result to {result_file}")
        np.save(result_file, noiseless_result)
        if "test_resume" in params and params.test_resume:
            exit_for_resume()

    noisy_result = noiseless_result + 0.5 * np.random.normal()
    metrics = {"result": noisy_result, "noiseless_result": noiseless_result}
    finalize_job(metrics, params)
    print(noiseless_result)
