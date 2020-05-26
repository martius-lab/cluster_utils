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

## Settings

Some clarification what some of the optimization settings do:

- `optimization_setting.number_of_samples`: the total number of jobs that will be run
- `optimization_setting.n_jobs_per_iteration`: the number of jobs submitted to the cluster concurrently, and also the number of finished jobs per report iteration

For `optimizer_str="cem_metaoptimizer"`:

- `optimizer_settings.with_restarts`: whether a specific set of settings can be run multiple times. This can be useful to automatically verify if good runs were just lucky runs because of e.g. the random seed, making the found solutions more robust.

## Usage Mindset and Rules of Thumb

Generally, the usage mindset should be *"obtain some interpretable understanding of the influence of the hyperparameters"* rather than *"blackbox optimizer just tells me the best setting"*.
Usually, early in the project many of the hyperparameters are more like ideas, or strategies. 
Cluster utils can then tell you which ideas (or their combinations) make sense. 
Later in a project, there only tend to be actual hyperparameters (i.e. transfering a working architecture to a new dataset), which can then be fit to this specific setting using cluster utils.

Here are some rules of thumbs to set the configuration values that can help you to get started. Keep in mind that following these does not necessarily lead to optimal results on your specific problem.

**Which optimizer should I use for optimizing hyperparameters of neural networks (depth, width, learning rate, etc.)?**

`cem_metaoptimizer` is a good default recommendation for this case.

**How many jobs should I run? How many concurrently?**

It depends. The number of concurrent jobs (`n_jobs_per_iteration`) should be as high as achievable with the current load on the cluster. 
For CPU jobs, this could be 100 concurrent jobs; for GPU jobs, maybe around 40. 
The total number of jobs (`number_of_samples`) can be lower if you only want to get an initial impression of the behaviour of the hyperparameter; in this case, 3-5 times the number of jobs per iteration is a good number.
If you want to get a more precise result, or if you have a high number of hyperparameters, up to 10 times the number of jobs per iteration can be used.

**How many hyperparameters can I optimize over at the same time?**

This depends on the number of jobs and number of parallely running jobs. For 5x100 jobs, 5-6 hyperparameters are okay to be optimized. For 5x40 jobs, 3-4 are okay. For a larger scale, e.g. 10x200 jobs, it might be reasonable to optimize up to 10 hyperparameters at the same time.

**How to deal with overfitting?**

You can keep the best validation error achieved over the epochs and report this instead of the error achieved in the last epoch.

