import os

import numpy as np
from cluster import cluster_main


@cluster_main # function needs to contain working_dir
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
    y_log = np.log(np.abs(y+1e-7))
    v_log = np.log(np.abs(v+1e-7))
    assert (type(w) == type(v) == int), "w and v have to be integers"

    result = (x - 3.14) ** 2 + (y_log - 2.78) ** 2 + (u * v_log * w + 1) ** 2 + (u + v_log + w - 5 + len(tuple_input)) ** 2
    if sharp_penalty and x > 3.20:
        result += 1

    if np.random.rand() < 0.1:
        raise ValueError("10 percent of all jobs die here on purpose")

    return {"metric": result}


if __name__ == "__main__":

    metrics = fn_to_optimize() # the decorator updates the parameters of the function
    print(metrics)
