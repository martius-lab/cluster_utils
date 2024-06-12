import time

from cluster_utils import initialize_job

if __name__ == "__main__":
    params = initialize_job()
    time.sleep(2)
    # Here we exit without sending result to cluster utils. We want cluster utils to count the job
    # as failed.
