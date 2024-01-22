import time

from cluster_utils import read_params_from_cmdline

if __name__ == "__main__":
    params = read_params_from_cmdline()
    time.sleep(2)
    # Here we exit without sending result to cluster utils. We want cluster utils to count the job
    # as failed.
