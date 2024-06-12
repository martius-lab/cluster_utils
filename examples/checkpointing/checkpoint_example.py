import os
import sys

import torch

from cluster_utils import (
    exit_for_resume,
    finalize_job,
    initialize_job,
)


def save_checkpoint(save_path, model, optim, iteration):
    """Save a dict with all variables necessary for a resume in a file.
    Make sure to also save the optimizer state if it uses an adaptive
    learning rate!"""
    torch.save(
        {
            "model_weights": model.state_dict(),
            "optimizer_weights": optim.state_dict(),
            "iteration": iteration,
        },
        save_path,
    )


def load_checkpoint(load_path, model, optim):
    """Load all previoulsy saved variables. The program starts clean
    after a resume, so we have to look if a checkpoint file exists in the
    current folder. If not, then we assume the program runs for the first
    time."""
    iteration = 0
    if os.path.isfile(load_path):
        checkpoint = torch.load(load_path)
        model.load_state_dict(checkpoint.get("model_weights"))
        optim.load_state_dict(checkpoint.get("optimizer_weights"))
        iteration = checkpoint.get("iteration")
        print(f"Resuming from checkpoint at iteration {iteration}")
    return iteration


if __name__ == "__main__":
    # parameters are loaded from json file
    params = initialize_job()
    # a folder for each run is created
    os.makedirs(params.working_dir, exist_ok=True)
    checkpoint_path = os.path.join(params.working_dir, "checkpoint.pt")
    # these are taken from json file for illustration
    total_iterations = params.total_iterations

    # initialize toy model and optimizer
    model = torch.nn.Linear(10, 20)
    optim = torch.optim.Adam(model.parameters(), lr=1e-4)
    target = torch.ones(size=(128, 20))

    # if a checkpoint.pt file exists, it is loaded
    iteration = load_checkpoint(checkpoint_path, model, optim)
    # redirect output to log file for easier understanding what happens
    # the log file is written after the program ends.
    sys.stdout = open(f"{params.working_dir}/log_{iteration}.txt", "w")  # noqa: SIM115

    while True:
        # do some training
        x = torch.normal(0, 1.0, size=(128, 10))
        y = model(x)

        loss = torch.nn.functional.mse_loss(y, target)
        optim.zero_grad()
        loss.backward()
        optim.step()
        print(f"loss {loss} episode {iteration}")
        iteration += 1

        # It is best to replace the iteration- with a time-constraint, jobs grow in
        # cost based on runtime by (0.1 * running_bid * n_compute_units) every hour!
        if iteration == 100:
            # we first save the necessary data to restart our job
            save_checkpoint(checkpoint_path, model, optim, iteration)
            # then we exit the job by calling a special function
            # htcondor internally restarts the job in the same cluster_utils working_dir
            # you will not see this in the utils progress bar, check
            # /working_directories/0/log.txt after the job
            print(f"Exit job at iteration {iteration}")
            exit_for_resume()

        if iteration >= total_iterations:
            break

    metrics = {"loss": loss, "iterations": iteration}
    # save final metrics, you will only see the resuming in the cluster_run.log file
    finalize_job(metrics, params)
    print(f"Training finished, final loss {loss} at episode {iteration}")
