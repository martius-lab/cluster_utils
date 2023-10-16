*************
Configuration
*************

Both ``grid_search`` and ``hp_optimization`` expect as input a JSON file with
the configuration.


.. _config.general_settings:

General Parameters
==================

.. todo::

    Explain the "job directory"
    (``${HOME}/.cache/cluster_utils-${optimization_procedure_name}-*``)
    somewhere in a central place.

These parameters are the same for ``grid_search`` and ``hp_optimization``.

.. list-table::
   :header-rows: 1

   * - Name
     - Info
     - Description
   * - ``optimization_procedure_name``
     - Mandatory
     - Name of the setup.
   * - ``results_dir``
     - Mandatory
     - Result files will be written to
       ``results_dir/optimization_procedure_name``.
   * - ``run_in_working_dir``
     - Optional, default=false
     - If true, ``git_params`` are ignored and the script specified in
       ``script_relative_path`` is expected to be in the current working
       directory.  Otherwise see ``git_params``.
   * - ``git_params``
     - Optional
     - If ``run_in_working_dir`` is false, the specified git repository is
       cloned to the job directory and the script specified in
       ``script_relative_path`` is expected to be found there.

       - ``branch``: Obviously the git branch to use.
       - ``commit``: TODO
       - ``url``: [Optional] URL to the repo.  If not set, the application
         expects the current working directory to be inside a git repository
         and uses the origin URL of this repo.
       - TODO: are there more options?
   * - ``script_relative_path``
     - Mandatory
     - Python script that is executed.  If ``run_in_working_dir=true``, the
       path is resolved relative to the working directory, otherwise relative
       to the root of the git repository specified in ``git_params``.
   * - ``remove_jobs_dir``
     - Optional, bool, default=true
     - Whether to remove the data stored in ``${HOME}/.cache`` once finished or
       not.  Note that when running on the cluster this directory also contains
       the stdout/stderr of the jobs (but not when running locally).
   * - ``remove_working_dirs``
     - Optional, bool, default={grid_search: False, hp_optimization: True}
     - TODO
   * - ``generate_report``
     - Optional, default=never
     - Specifies whether a report should be generated automatically. Can be one of the
       following values:

       - ``never``: Do not generate report automatically.
       - ``when_finished``: Generate once when the optimization has finished.
       - ``every_iteration``: Generate report of current state after every iteration.

       If enabled, the report is saved as ``result.pdf`` in the results directory (see
       ``results_dir``).  Note that independent of the setting here, the report can
       always be generated manually, see :ref:`manual_report_generation`.

       *Added in version 3.0.  Set to "every_iteration" to get the behaviour of
       versions <=2.5*
   * - ``environment_setup``
     - Mandatory
     - TODO.
       Note: while the ``environment_setup`` argument itself is mandatory, all
       its content seems to be optional (i.e. it can be empty).

       - ``pre_job_script``:  Probably a script that is run before the actual
         job.
   * - ``cluster_requirements``
     - Mandatory
     - Settings for the cluster (number of CPUs, bid, etc.).  See cluster
       documentation for meaning of the options.  Important: A separate job is
       submitted for each set of parameters, consider this when specifying the
       cluster requirements (especially the bid!).

       - TODO: Complete list of options
       - ``request_cpus``: int
       - ``request_gpus``: int
       - ``cuda_requirement``:  Can be "null".  TODO probably version?
       - ``memory_in_mb``: int
       - ``bid``: int
   * - ``fixed_params``
     - Mandatory
     - TODO


Specific for hp_optimization
============================

.. list-table::
   :header-rows: 1

   * - Name
     - Info
     - Description
   * - ``num_best_jobs_whose_data_is_kept``
     - Mandatory
     - Obvious
   * - ``kill_bad_jobs_early``
     - Optional, bool, default=False
     - TODO
   * - ``early_killing_params``
     - Optional
     - TODO
   * - ``optimizer_str``
     - Mandatory
     - The optimisation method that is used to find good hyperparameters.
       Supported methods are "cem_metaoptimizer", "nevergrad" and "gridsearch".
   * - ``optimizer_settings``
     - Mandatory
     - Settings specific to the optimiser selected in ``optimizer_str``.
       See :ref:`config.optimizer_settings`.
   * - ``optimization_setting``
     - Mandatory
     - General settings for the optimisation (independent of the optimisation
       method).  See :ref:`config.optimization_settings`.
   * - ``optimized_params``
     - Mandatory
     - Probably defines the parameters that are optimised over.  It is a list
       of dicts with each entry having the following elements:

       - ``param``:  Name of the parameter.  Apparently can have
         object/attribute structure, e.g. "fn_args.x".
       - ``distribution``: Distribution that is used for sampling.  Options
         are:

           - TruncatedNormal
           - TruncatedLogNormal
           - IntLogNormal
           - IntNormal
           - Discrete
           - TODO: more?
       - ``bounds``:  List ``[min_value, max_value]``
       - ``options``:  List of possible values (used instead of bounds for
         "Discrete" distribution.


.. _config.optimization_settings:

General Optimisation Settings
-----------------------------

The ``optimization_setting`` parameter defines the general optimisation
settings (i.e. the ones independent of the optimisation method set in
``optimizer_str``).  A dictionary with the following values is expected:

.. list-table::
   :header-rows: 1

   * - Name
     - Info
     - Description
   * - ``metric_to_optimize``
     - Mandatory, string
     - Name of the metric that is used for the optimisation.  Has to match the
       name of one of the metrics that are saved with
       :func:`cluster.save_metrics_params`.
   * - ``minimize``
     - Mandatory, bool
     - Specify whether the metric shall be minimized (true) or maximised
       (false).
   * - ``number_of_samples``
     - Mandatory, int
     - The total number of jobs that will be run.
   * - ``n_jobs_per_iteration``
     - Mandatory, int
     - The number of jobs submitted to the cluster concurrently, and also the
       number of finished jobs per report iteration.
   * - ``n_completed_jobs_before_resubmit``
     - Optional, int, default=1
     - The number of jobs that have to be finished before another
       ``n_completed_jobs_before_resubmit`` jobs are submitted.  Defaults to 1
       (i.e. submit new job immediately when one finishes).
   * - ``run_local``
     - Optional, bool
     - Specify if the optimisation shall be run locally if the cluster is not
       detected.  If not set, the user will be asked at runtime in this case.


About Iterations
~~~~~~~~~~~~~~~~

The exact meaning of one "iteration" of the hp_optimization mode is a bit
complicated and depends on the configuration.

Relevant are the following parameters from the ``optimization_setting``
section:

- ``number_of_samples``
- ``n_jobs_per_iteration``
- ``n_completed_jobs_before_resubmit`` (default: 1)

``number_of_samples`` is simply the total number of jobs that are run.
``n_jobs_per_iteration`` says how many jobs can be executed in parallel.

From this a number of iterations is derived.  Basically an iteration counter is
used that is incremented by one whenever another ``n_jobs_per_iteration`` jobs
has been completed (resulting in ``number_of_samples / n_jobs_per_iteration``
iterations in the end).  However, it does *not* necessarily mean that the
optimisation is split into distinct iterations where the next iteration only
starts when the previous one has finished. Instead, whenever a job completes,
the optimiser is updated with the results and the next one is started
immediately, so that always ``n_jobs_per_iteration`` jobs are running at the
same time. The notion of "iterations" is only used to have a regular update of
the report every ``n_jobs_per_iteration`` jobs.

The behaviour can be changed by setting ``n_completed_jobs_before_resubmit``.
The meaning of this parameter is as follows:  Always wait until
``n_completed_jobs_before_resubmit`` jobs have finished, then submit another
``n_completed_jobs_before_resubmit`` jobs. Its default value is 1, resulting in
the behaviour described in the previous paragraph.  However, setting it to a
larger value results in the optimisation to wait for several jobs to have
finished before sampling new parameters. Setting
``n_completed_jobs_before_resubmit = n_jobs_per_iteration`` results in what one
would intuitively assume regarding iterations, i.e. the optimisation would wait
for ``n_jobs_per_iteration`` to be finished and only then start the next
iteration with another ``n_jobs_per_iteration`` jobs.


.. _config.optimizer_settings:

Optimiser Settings
------------------

``optimizer_settings`` expects as value a dictionary with configuration specific
to the method that is specified in ``optimizer_str``.  Below are the
corresponding parameters for each method.

cem_metaoptimizer
~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Name
     - Info
     - Description
   * - ``with_restarts``
     - Mandatory, bool
     - Whether a specific set of settings can be run multiple times. This can be
       useful to automatically verify if good runs were just lucky runs because
       of e.g. the random seed, making the found solutions more robust.

       If enabled, new settings are sampled for the first ``num_jobs_in_elite``
       jobs.  After that each new job has a 20% chance to use the same settings
       as a previous job (drawn from the set of best jobs).
   * - ``num_jobs_in_elite``
     - Mandatory, int
     - TODO


nevergrad
~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Name
     - Info
     - Description
   * - ``opt_alg``
     - Mandatory
     - TODO

gridsearch
~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Name
     - Info
     - Description
   * - ``restarts``
     - Mandatory
     - TODO


Specific for grid_search
========================

.. list-table::
   :header-rows: 1

   * - Name
     - Info
     - Description
   * - ``local_run``
     - Optional
     - TODO
   * - ``load_existing_results``
     - Optional, bool, default=False
     - TODO
   * - ``restarts``
     - Mandatory
     - How often to run each configuration (useful if there is some randomness
       in the result).
   * - ``samples``
     -
     - TODO:  Does not seem to be used in grid_search
   * - ``hyperparam_list``
     - Mandatory
     - Probably list of parameters over which the grid search is performed.
       List of dicts:

       - ``param``:  Parameter name (e.g. "fn_args.x").
       - ``values``:  List of values.  Be careful with types, ``42`` will be passed as
         int, use ``42.0`` if you want float instead.


Overwriting Parameters on the Command Line
==========================================

When executing ``grid_search`` or ``hp_optimization`` it is possible to
overwrite one or more parameters of the config file by providing values on the
command line.

The general syntax for this is ``parameter_name=value`` given after the
config file.  Note, however, that ``value`` is evaluated as Python code.  This
means that string values need to be quoted in a way that is preserved by the
shell.  So for example to use a custom name for the output directory:

::

    python3 -m cluster.grid_search config.json 'optimization_procedure_name="foo"'


Nested parameters can be set using dots:

::

    python3 -m cluster.grid_search config.json 'git_params.branch="foo"'
