"""Minimal example on how to use the timeout signal sent by Slurm."""

import json
import pathlib
import signal
import sys
import time

import cluster_utils

received_timeout_signal = False


def timeout_signal_handler(sig, frame):
    global received_timeout_signal

    print("Received timeout signal")
    # simply set a flag here, which is checked in the training loop
    received_timeout_signal = True


def main() -> int:
    """Main function."""
    params = cluster_utils.initialize_job()

    n_training_iterations = 60
    start_iteration = 0

    # register signal handler for the USR1 signal
    signal.signal(signal.SIGUSR1, timeout_signal_handler)

    checkpoint_file = pathlib.Path(params.working_dir) / "checkpoint.json"

    # load existing checkpoint
    if checkpoint_file.exists():
        print("Load checkpoint")
        with open(checkpoint_file) as f:
            chkpnt = json.load(f)
            start_iteration = chkpnt["iteration"]

    for i in range(start_iteration, n_training_iterations):
        print(f"Training iteration {i} with x = {params.x}, y = {params.y}")
        time.sleep(10)  # dummy sleep instead of an actual training

        if received_timeout_signal:
            print("Save checkpoint and exit for resume.")
            # save checkpoint
            with open(checkpoint_file, "w") as f:
                json.dump({"iteration": i + 1}, f)

            # exit and ask cluster_utils to restart this job
            cluster_utils.exit_for_resume()

    # just return some dummy metric value here
    metrics = {"result": params.x + params.y, "n_iterations": i}
    cluster_utils.finalize_job(metrics, params)

    return 0


if __name__ == "__main__":
    sys.exit(main())
