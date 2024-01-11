# Cluster utils

This code has been powering my cluster runs since 2017. It has grown ever since and now it is a proper monster. Enjoy :).


## Main features

A non-exhaustive list of features is the following:

* **Automatic condor usage** Jobs are submitted, monitored (with error reporting), and cleaned up in an automated and highly customizable way.

* **Integrated with git**. Jobs are run from a `git clone` with customizable branch and commit number.

* **PDF & CSV reporting**. Both grid search and optimization produce a pdf report with the specification, basic summaries, and plots.

* **Advanced setting handling**. Cluster utils offer a customized settings system based on JSON. Pointers within the JSON file and to other JSON files are supported.

* **A LOT OF ADDITIONAL SWEETNESS**. Most are demonstrated in the examples. Also, read the code ;).


## Documentation

A more detailed documentation is included in the `docs/` folder of the repository.
There is not yet a publicly hosted version of the documentation but they are rendered
relatively well when viewed on GitLab.  See [docs/README.md](docs/README.md) for a table
of contents.

You can also build the documentation locally with the following commands:

```bash
git clone https://gitlab.tuebingen.mpg.de/mrolinek/cluster_utils.git
cd cluster_utils
# install package with the additional dependencies needed to build the documentation
pip install ".[docs]"
cd docs/
make html  # build documentation
```
When the build is finished, open ``docs/_build/html/index.html`` with the browser of
your choice.

Below there are several links to parts of the documentation, which can also be
viewed relatively well in GitLab.



## Installation

See [docs/installation.rst](docs/installation.rst)


## Quick Start

There are two basic functionalities:

```bash
python3 -m cluster.grid_search specification_of_grid_search.json
```

and

```bash
python3 -m cluster.hp_optimization specification_of_hp_opt.json
```

for hyperparameter optimization

See `examples/basic` and `examples/rosenbrock` for simple demonstrations.

## Usage

### Environment Setup

The simplest way to specify your Python environment is to activate it (using virtualenv, pipenv, conda, etc.) before calling `python -m cluster.grid_search` or `python -m cluster.hp_optimization`.
The jobs will automatically inherit this environment.
A caveat of this approach is that if you *installed your local package in the environment*, this package *might override* the repository cluster_utils clones using git, i.e. you are not using a clean clone of your project.

There are multiple options to further customize the environment in the
`environment_setup` configuration section, see
[docs/configuration.rst](docs/configuration.rst).

### Condor Cluster System

See [docs/configuration.rst](docs/configuration.rst), Section "Cluster
Requirements".

### Hyperparameter Optimization Settings

Some clarification what some of the optimization settings do:

- `optimization_setting.number_of_samples`: the total number of jobs that will be run
- `optimization_setting.n_jobs_per_iteration`: the number of jobs submitted to the cluster concurrently, and also the number of finished jobs per report iteration

For `optimizer_str="cem_metaoptimizer"`:

- `optimizer_settings.with_restarts`: whether a specific set of settings can be run multiple times. This can be useful to automatically verify if good runs were just lucky runs because of e.g. the random seed, making the found solutions more robust.

See also [docs/configuration.rst](docs/configuration.rst).

## Hyperparameter Optimization Mindset and Rules of Thumb

See [docs/usage_mindset_and_rule_of_thumb.rst](docs/usage_mindset_and_rule_of_thumb.rst)

## Development

See [docs/setup_devel_env.rst](docs/setup_devel_env.rst)
