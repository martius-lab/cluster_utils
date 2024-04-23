# cluster_utils

*cluster_utils* is a Python package that simplifies interacting with compute clusters. 
It is geared towards tasks typical for *machine learning research*, for example running multiple seeds, grid searches, and hyperparameter optimization.
The package was developed in the [Autonomous Learning group](https://al.is.mpg.de/) at the University of Tübingen.

**A note on support.**
*cluster_utils* was initially developed for inhouse use.
In particular, this means that documentation is sparse, and the user experience is suboptimal in some places.
We are open sourcing the package now because we think it could also be useful for other people in the machine learning community.
However, we can only provide limited support for user questions and requests.

**A note on stability.**
This package is in stable beta mode.
*cluster_utils* has been powering the experiments behind many machine learning projects, and has been battle tested a lot.
However, there are many rough edges and bugs that remain; you have been warned!
If you encounter any bugs or have suggestions for improvements, please submit an issue and we will try to work on it.

## Features

- **Parametrized jobs and hyperparameter optimization**: run grid searches or multi-stage hyperparameter optimization.
- **Supports several cluster backends**: currently, [Slurm](https://slurm.schedmd.com/) and [HTCondor](https://htcondor.org/), as well as local (single machine runs) are supported. 
- **Automatic job management**: jobs are submitted, monitored (with error reporting), and cleaned up in an automated way.
- **Timeouts & restarting of failed jobs**: jobs can be stopped and resubmitted after some time; failed jobs can be (manually) restarted.
- **Integrated with git**: jobs are run from a `git clone` with customizable branch and commit number to enhance reproducility.
- **Reporting**: results are summarized in CSV files, and optionally PDF reports with basic summaries and plots.

## Installation

```
pip install git+https://github.com/martius-lab/cluster_utils.git
```

See also [docs/installation.rst](docs/installation.rst) for more details.

## Documentation

A more detailed documentation is included in the `docs/` folder of the repository.
There is not yet a publicly hosted version of the documentation but they are rendered relatively well when viewed on Github.
See [docs/README.md](docs/README.md) for a table of contents.

You can also build the documentation locally with the following commands:

```bash
git clone https://github.com/martius-lab/cluster_utils.git
cd cluster_utils
# install package with the additional dependencies needed to build the documentation
pip install ".[docs]"
cd docs/
make html  # build documentation
```
When the build is finished, open ``docs/_build/html/index.html`` with the browser of your choice.

## Quick Start

First, the code that should be executed with *cluster_utils* needs to be instrumented to communicate with the cluster_utils server process.

The simplest way to do so is to wrap the main function with the `cluster_main` decorator:

```python
from cluster_utils import cluster_main

@cluster_main
def main(
    working_dir,    # Path to a directory for storing results and checkpoints
    id,             # Id of the job
    **kwargs        # Other parameters passed by cluster_utils
):
    results = ...   # Code that computes something interesting

    return results  # Results are sent to the cluster_utils server
```

If you don't want to use a decorator, use the following:

```python
from cluster_utils import read_params_from_cmdline, save_metrics_params

def main(params):
    results = ...  # Code that computes something interesting
    return results

if __name__ == "__main__":
    # Dictionary that contains parameters passed by cluster_utils. This call also establishes 
    # communication with the cluster_utils server. Also contains "working_dir" and "id", as above.
    params = read_params_from_cmdline()

    results = main(params)

    # Report results back to cluster_utils.
    save_metrics_params(results)
```

To start a cluster run, start the cluster_utils server on the login node of the cluster.
There are two basic functionalities:

```bash
python3 -m cluster_utils.grid_search specification_of_grid_search.json
```

for grid search, and

```bash
python3 -m cluster_utils.hp_optimization specification_of_hp_opt.json
```

for hyperparameter optimization. 
Both receive a configuration file that specifies the compute environment, the script to be called, 
parameters to pass and more.

See `examples/basic` and `examples/rosenbrock` for simple demonstrations.

## Usage

### Environment Setup

The simplest way to specify your Python environment is to activate it (using virtualenv, pipenv, conda, etc.) before calling `python -m cluster_utils.grid_search` or `python -m cluster_utils.hp_optimization`.
The jobs will automatically inherit this environment.
A caveat of this approach is that if you *installed your local package in the environment*, this package *might override* the repository cluster_utils clones using git, i.e. you are not using a clean clone of your project.

There are multiple options to further customize the environment in the `environment_setup` configuration section, see [docs/configuration.rst](docs/configuration.rst).

### Slurm & Condor Cluster Systems

See [docs/configuration.rst](docs/configuration.rst), Section "Cluster Requirements".

### Hyperparameter Optimization Settings

See [docs/configuration.rst](docs/configuration.rst), Section "Optimizer Settings".

## Hyperparameter Optimization Mindset and Rules of Thumb

See [docs/usage_mindset_and_rule_of_thumb.rst](docs/usage_mindset_and_rule_of_thumb.rst).

## Development

See [docs/setup_devel_env.rst](docs/setup_devel_env.rst).
