*******************************************
Tutorial: Basic Hyperparameter Optimization
*******************************************

In this tutorial, we reuse the script with the Rosenbrock function from
:doc:`grid_search`, but instead of a simple grid search, we run a more sophisticated
hyperparameter optimization on it.

Again, this tutorial does not cover all available options but instead shows the minimal
steps needed to get started.

.. note:: If you haven't done so, please read :doc:`grid_search` first.

--------


What is hyperparameter optimization
===================================

In the previous tutorial, we used ``grid_search`` to do an exhaustive search over a
discrete set of possible parameter values.  In this tutorial, we will use
``hp_optimization``, which instead samples parameter values them from continuous
distributions, based on results of previous jobs.

When given enough iterations, this ideally converges towards good values for the
hyperparameters (w.r.t. to the metric you specified).


Prepare your code
=================

Please see the corresponding section in :doc:`grid_search`.  The exact same job
script/git repository can be used here.



Write a cluster_utils configuration file
========================================

The configuration file generally has the same structure as for grid search but some
settings differ.

.. code-block:: toml

    # Name and base of the output directory.  With the given config, results will be
    # written to /tmp/rosenbrock_optimization/.
    optimization_procedure_name = "rosenbrock_optimization"
    results_dir = "/tmp"

    # Automatically generate a PDF report when finished
    generate_report = "when_finished"

    # Path to the job script.  Note that this is relative to the repositories root
    # directory, not to this config file!
    script_relative_path = "rosenbrock.py"

    # which optimizer to use
    optimizer_str = "cem_metaoptimizer"

    # keep data of the 5 best runs (for example useful, if checkpoints are saved)
    num_best_jobs_whose_data_is_kept = 5

    [git_params]
    # which repo/branch to check out
    url = "<url to your git repository>"
    branch = "main"

    [cluster_requirements]
    request_cpus = 1

    [environment_setup]
    # This section is required, even if no options are set here.

    [fixed_params]
    # Likewise required but may be empty.

    [optimizer_settings]
    with_restarts = false
    num_jobs_in_elite = 10

    [optimization_setting]
    # Which metric value to optimize on.  Refers to the metrics dictionary that is
    # returned in rosenbrock.py.
    metric_to_optimize = "rosenbrock_value"
    minimize = true

    # total number samples that are tested
    number_of_samples = 1_00
    # how many jobs to run in parallel
    n_jobs_per_iteration = 10

    [[optimized_params]]
    param = "x"
    distribution = "TruncatedNormal"
    bounds = [ -2, 2 ]

    [[optimized_params]]
    param = "y"
    distribution = "TruncatedNormal"
    bounds = [ -2, 2 ]



Compared to the configuration from the :doc:`grid search tutorial <grid_search>` the
``restarts`` and ``hyperparam_list`` settings are gone.  Instead a bunch of other
settings has been added, which we will go through in the following:


.. code-block:: toml

    optimizer_str = "cem_metaoptimizer"

The type of optimizer to use (see :confval:`optimizer_str` for available options).

.. code-block:: toml

    num_best_jobs_whose_data_is_kept = 5

With this setting, the full output of the best 5 jobs throughout the whole optimization
is kept.  This is mostly useful if your jobs store additional data (e.g. training
snapshots), which you might want to analyse when finished.


.. code-block:: toml

    [optimizer_settings]
    with_restarts = false
    num_jobs_in_elite = 10

Settings specific to the chosen optimizer.  See :ref:`config.optimizer_settings`.

.. code-block:: toml

    [optimization_setting]
    # Which metric value to optimize on.  Refers to the metrics dictionary that is
    # returned in rosenbrock.py.
    metric_to_optimize = "rosenbrock_value"
    minimize = true

    # total number samples that are tested
    number_of_samples = 1_00
    # how many jobs to run in parallel
    n_jobs_per_iteration = 10

These are general optimization settings that are valid for all optimizers.  Here we
specify which metric should be used for the optimization (in this tutorial, we only
return one value in ``rosenbrock.py`` but there could be multiple) and whether it should
be minimized or maximized.

Further the number of samples and iterations is configured here.  See
:ref:`config.optimization_settings` for more information.

.. code-block:: toml

    [[optimized_params]]
    param = "x"
    distribution = "TruncatedNormal"
    bounds = [ 0, 2 ]

    [[optimized_params]]
    param = "y"
    distribution = "TruncatedNormal"
    bounds = [ 0, 2 ]

Finally the hyperparmeters that should be optimized are specified.  In this example, we
use a normal distribution over the range [0, 2] for both variables.  See
:confval:`optimized_params` for a list of available distributions.

**Note:** You will need to adjust the settings in the ``[git_params]`` section to point
to the repository that contains the ``rosenbrock.py``.


Run the hyperparameter optimization
===================================

Now you can run the hyperparameter optimization locally:

.. code-block:: sh

    python3 -m cluster_utils.hp_optimization path/to/config.toml

The output during execution is similar to grid search.  However, after each
"iteration" (see :ref:`config.hp_optimization_iterations`), a list of current best
results is printed:

.. code-block:: text

           x     y  rosenbrock_value  job_restarts  rosenbrock_value__std
    20  1.00  1.00          0.000000             3                    0.0
    15  0.90  0.81          0.010000             1                    NaN
    18  0.96  1.00          0.616256             1                    NaN
    17  0.95  1.00          0.953125             1                    NaN
    10  0.85  0.82          0.973125             1                    NaN
    13  0.89  0.90          1.176341             1                    NaN
    8   0.80  0.50          2.000000             1                    NaN
    21  1.00  1.20          4.000000             1                    NaN
    14  0.90  0.60          4.420000             2                    0.0
    9   0.80  0.90          6.800000             1                    NaN


The result files in the output directory are also similar to grid search.  Most
important ones are:

- result.pdf:  The PDF report.
- all_data.csv:  Results of all runs as CSV file.
- cluster_run.log: Log of cluster_utils.  Useful for debugging if something goes wrong.


.. important::

   Every time you run cluster_utils, it creates a temporary working copy of the
   specified git repository.  This means, when you make changes to the code, you need to
   **commit and push** them before running cluster_utils again.
