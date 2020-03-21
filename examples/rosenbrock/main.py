import os

import numpy as np
import torch
import time
from cluster import save_metrics_params, update_params_from_cmdline

def rosenbrock(x, y):
    return (1 - x) ** 2 + 100 * (y - x ** 2) ** 2


dct = {'Adam': torch.optim.Adam,
       'SGD': torch.optim.SGD,
       'Adagrad': torch.optim.Adagrad,
       'RMSProp': torch.optim.RMSprop}


def get_optimizer(parameters, name, opt_params):
    return dct[name](parameters, **opt_params)


x_0 = torch.Tensor(np.array(0.0))
y_0 = torch.Tensor(np.array(0.0))
x, y = torch.nn.Parameter(x_0), torch.nn.Parameter(y_0)

params = update_params_from_cmdline()

opt = get_optimizer([x,y], params.optimizer, params.optimizer_params)
loss = rosenbrock(x, y)

for i in range(params.iterations):
    loss = rosenbrock(x, y)
    loss.backward()
    opt.step()
    time.sleep(0.1)

metrics = {'final_value': loss}
save_metrics_params(metrics, params)

