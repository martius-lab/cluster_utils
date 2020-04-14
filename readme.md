# Cluster utils

This code has been powering my cluster runs since 2017. It has grown ever since and now it is a proper monster. Enjoy :).

## Run to install:

``python3 -m pip install git+https://gitlab.tuebingen.mpg.de/mrolinek/cluster_utils.git``

To enable pdf reporting add this line to your .bashrc (.zshrc) on the cluster

``export MPLBACKEND="agg"``

## Usage

There are two basic functionalities:

``python3 -m cluster.grid_search specification_of_grid_search.json``

and

``python3 -m cluster.hp_optimization specification_of_hp_opt.json``

for hyperparameter optimization

See `examples/basic` and `examples/rosenbrock` for simple demonstrations.

## Main features

A nonexhaustive list of features is the following:

* **Automatic condor usage** Jobs are submitted, monitored (with error reporting), and cleaned up in an automated and highly customizable way.

* **Integrated with git**. Jobs are run from a `git clone` with customizable branch and commit number.

* **Pdf&csv reporting** Both grid search and optimization produce a pdf report with the specification, basic summaries, and plots.

* **Advanced setting handling** Cluster utils offer a customized settings system based on JSON. Pointers within the JSON file and to other JSON files are supported.

* **A LOT OF ADDITIONAL SWEETNESS** Most are demonstrated in the examples. Also, read the code ;).