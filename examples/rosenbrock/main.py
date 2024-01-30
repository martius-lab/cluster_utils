import time

import numpy as np
import torch

from cluster_utils import (
    announce_early_results,
    announce_fraction_finished,
    cluster_main,
)


def rosenbrock(x, y):
    return (1 - x) ** 2 + 100 * (y - x**2) ** 2


dct = {
    "Adam": torch.optim.Adam,
    "SGD": torch.optim.SGD,
    "Adagrad": torch.optim.Adagrad,
    "RMSprop": torch.optim.RMSprop,
}


def get_optimizer(parameters, name, opt_params):
    return dct[name](parameters, **opt_params)


@cluster_main
def main(working_dir, optimizer, optimizer_params, iterations):
    x_0 = torch.Tensor(np.array(0.0))
    y_0 = torch.Tensor(np.array(0.0))
    x, y = torch.nn.Parameter(x_0), torch.nn.Parameter(y_0)

    opt = get_optimizer([x, y], optimizer, optimizer_params)
    loss = rosenbrock(x, y)

    for i in range(iterations):
        loss = rosenbrock(x, y)
        loss.backward()
        opt.step()
        time.sleep(3)

        if torch.isnan(loss) or loss > 1e5:
            raise ValueError("Optimization failed")

        announce_fraction_finished((i + 1) / iterations)
        announce_early_results({"final_value": loss})

    metrics = {"final_value": loss}
    return metrics


if __name__ == "__main__":
    main()
