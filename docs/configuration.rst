*************
Configuration
*************

Both ``grid_search`` and ``hp_optimization`` expect as input a settings file
with the configuration.  The file can be any format that is supported by
smart_settings_ (currently JSON, YAML and TOML).


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
       - ``every_iteration``: Generate report of current state after every iteration
         (not supported by ``grid_search``).

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
     - Settings for the cluster (number of CPUs, bid, etc.).  See
       :ref:`config_cluster_requirements`.
   * - ``singularity``
     - Optional
     - See :ref:`config_singularity`.
   * - ``fixed_params``
     - Mandatory
     - TODO


.. _config_cluster_requirements:

Cluster Requirements
--------------------

When running on a cluster, you have to specify the resources needed for each job (number
of CPUs/GPUs, memory, etc.).  This is all configured in the section
``cluster_requirements``.  
.. note:: The cluster requirements are ignored when running on a local machine.

Some of the options are common among all supported cluster systems, some are
system-specific.  Note that all the options are per job, i.e. each job will get the
requested CPUs, memory, ..., it's not shared between jobs.

Simple example (in TOML):

.. code-block:: toml

   [cluster_requirements]
   request_cpus = 1
   request_gpus = 0
   memory_in_mb = 1_000
   bid = 1_000


Common Options
~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Name
     - Info
     - Description
   * - ``request_cpus``
     - int
     - Number of CPUs that is requested.
   * - ``request_gpus``
     - int
     - Number of GPUs that is requested.
   * - ``memory_in_mb``
     - int
     - Memory (in MB) that is requested.


Condor-specific Options
~~~~~~~~~~~~~~~~~~~~~~~

The following options are only used when running on Condor (i.e. the MPI cluster).

.. list-table::
   :header-rows: 1

   * - Name
     - Info
     - Description
   * - ``bid``
     - int
     - The amount of cluster money you are bidding for each job.  See documentation of
       the MPI-IS cluster on how the bidding system works.
   * - ``cuda_requirement``
     - ?
     - ``cuda_requirement`` has multiple behaviors. If it is a number, it specifies the
       *minimum* CUDA capability the GPU should have. If the number is prefixed with
       ``<`` or ``<=``, it specifies the *maximum* CUDA capability. Otherwise, the value
       is taken as a full requirement string, example (in TOML):

       .. code-block:: toml

          [cluster_requirements]
          # ...
          cuda_requirement = "TARGET.CUDACapability >= 5.0 && TARGET.CUDACapability <= 8.0"
          # ...

       Remember to prefix the constraints with ``TARGET.``. See
       https://atlas.is.localnet/confluence/display/IT/Specific+GPU+needs for the kind
       of constraints that are possible.

   * - ``gpu_memory_mb``
     - int
     - Minimum memory size the GPU should have, in megabytes.
   * - ``concurrency_limit`` / ``concurrency_limit_tag``
     - Optional
     - Limit the number of concurrent jobs. You can assign a resource (tag) to your jobs
       and specify how many tokens each jobs consumes. There is a total of 10,000 tokens
       per resource. If you want to run 10 concurrent jobs, each job has to consume
       1,000 tokens.

       To use this feature, it is as easy as adding (example in TOML)

       .. code-block:: toml

          [cluster_requirements]
          # ...
          concurrency_limit_tag = "gpu"
          concurrency_limit = 10
          # ...

       to the settings.

       You can assign different tags to different runs. In that way you can limit only
       the number of gpu jobs, for instance.
   * - ``hostname_list``
     - list of strings
     - Cluster nodes to exclusively use for running jobs.
   * - ``forbidden_hostnames``
     - list of strings
     - Cluster nodes to exclude from running jobs. Useful if nodes are malfunctioning.
   * - ``extra_submission_options``
     - dictionary, list or string
     - This allows to add additional lines to the `.sub` file used for submitting jobs
       to the cluster. Note that this setting is normally not needed, as cluster_utils
       automatically builds the submission file for you.


.. todo:: Is the list above complete?


Slurm-specific Options
~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Name
     - Info
     - Description
   * - ``partition``
     - string
     - Name of the partition to run the jobs on.  See documentation of the corresponding
       cluster on what partitions are available.

       Multiple partitions can be given as a comma-separated string
       (``partition1,partition2``), in this case jobs will be executed on any of them
       (depending on which has free capacity first).
   * - ``request_time``
     - string
     - Time limit for the jobs.  Jobs taking longer than this will be aborted, so make
       sure to request enough time (but don't exaggerate too much as shorter jobs can be
       scheduled more easily).

       From the `Slurm documentation <https://slurm.schedmd.com/sbatch.html>`_:

           Acceptable time formats include "minutes", "minutes:seconds",
           "hours:minutes:seconds", "days-hours", "days-hours:minutes" and
           "days-hours:minutes:seconds".

       So for example to request 1 hour per job use ``request_time = "1:00:00"``.

.. note::

   There are currently no options to restrict the type of GPU.  On the ML Cloud cluster
   of the University of Tübingen, this is currently done via the *partitions*.  See
   https://portal.mlcloud.uni-tuebingen.de/user-guide/batch for a list of available
   partitions.


.. _config_singularity:

Use Singularity/Apptainer Containers
------------------------------------

Jobs can be executed inside Singularity/Apptainer [#singularity1]_ containers to give
you full control over the environment, installed packages, etc.  To enable
containerisation of jobs, add a section ``singularity`` in the config file.  This
section can have the following parameters:

.. list-table::
   :header-rows: 1

   * - Name
     - Info
     - Description
   * - ``image``
     - **Mandatory**
     - Path to the container image.
   * - ``executable``
     - default=singularity
     - Specify the executable that is used to run the container (mostly useful if you
       want to explicitly use Apptainer instead of Singularity in an environment where
       both are installed).
   * - ``use_run``
     - default=false
     - Per default the container is run with ``singularity exec``.  Set this to true to
       use ``singularity run`` instead.  This is only useful for images that use a
       wrapper run script that executes the given command (sometimes needed for some
       environment initialisation).
   * - ``args``
     - default=[]
     - List of additional arguments that are passed to ``singularity exec|run``.  Use
       this to set flags like ``--nv``, ``--cleanenv``, ``--contain``, etc. if needed.

Example (in TOML):

.. code-block:: toml

   [singularity]
   image = "my_container.sif"
   args = ["--nv", "--cleanenv"]



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
       Supported methods are 

       - cem_metaoptimizer
       - nevergrad \*
       - gridsearch

       \* To use nevergrad, the optional dependencies from the "nevergrad" group are
       needed, see :ref:`optional_dependencies`.
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

.. note::

   To use nevergrad, the optional dependencies from the "nevergrad" group are needed,
   see :ref:`optional_dependencies`.

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



.. [#singularity1] `SingularityCE <https://sylabs.io/singularity/>`_ and `Apptainer
   <https://apptainer.org>`_ are both emerged from the original Singularity project.  So
   far they are still mostly compatible but their features may diverge over time.  So
   you may want to check which one is installed on the cluster you are using, e.g. by
   running ``singularity --version``.


.. _smart_settings: https://github.com/martius-lab/smart-settings
