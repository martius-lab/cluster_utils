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


.. confval:: optimization_procedure_name

    **Required.**

    Name of the setup.


.. confval:: results_dir

    **Required.**

    Result files will be written to ``{results_dir}/optimization_procedure_name``.

.. confval:: run_in_working_dir = false

    If true, :confval:`git_params` are ignored and the script specified in
    :confval:`script_relative_path` is expected to be in the current working directory.
    Otherwise see :confval:`git_params`.

.. confval:: git_params

    If :confval:`run_in_working_dir` is false, the specified git repository is cloned to
    the job directory and the script specified in :confval:`script_relative_path` is
    expected to be found there.

    .. confval:: git_params.branch: str

        The git branch to use.

    .. confval:: git_params.commit

        Hash of a specific commit that should be used.

        Note: The current implementation still needs a valid branch to be set as it first
        clones the repo using that branch and only afterwards checks out the specified
        commit.

    .. confval:: git_params.url

        URL to the repo.  If not set, the application expects the current working
        directory to be inside a git repository and uses the origin URL of this repo.

    .. confval:: git_params.depth: int

        Create a shallow clone with a history truncated to the specified number of
        commits. 

    .. confval:: git_params.remove_local_copy: bool = true

        Remove the local working copy when finished.

.. confval:: script_relative_path

    **Required.**

    Python script that is executed.  If :confval:`run_in_working_dir` = true, the path
    is resolved relative to the working directory, otherwise relative to the root of the
    git repository specified in :confval:`git_params`.

.. confval:: remove_jobs_dir: bool = true

    Whether to remove the data stored in ``${HOME}/.cache`` once finished or not.  Note
    that when running on the cluster this directory also contains the stdout/stderr of
    the jobs (but not when running locally).

.. confval:: remove_working_dirs: bool = {grid_search: false, hp_optimization: true}

    Remove the working directories of the jobs (including the parameters used for that
    job, saved metrics and potentially other output files like checkpoints) once they
    are finished.

    For *hp_optimization* the directories of the best jobs kept independent of this
    setting, see :confval:`num_best_jobs_whose_data_is_kept`.

.. confval:: generate_report: str = "never"

    Specifies whether a report should be generated automatically. Can be one of the
    following values:

    - ``never``: Do not generate report automatically.
    - ``when_finished``: Generate once when the optimization has finished.
    - ``every_iteration``: Generate report of current state after every iteration
      (not supported by ``grid_search``).

    If enabled, the report is saved as ``result.pdf`` in the results directory (see
    ``results_dir``).  Note that independent of the setting here, the report can always
    be generated manually, see :ref:`manual_report_generation`.

    *Added in version 3.0.  Set to "every_iteration" to get the behaviour of versions
    <=2.5*

.. confval:: environment_setup

    **Required.**

    Note: while the ``environment_setup`` argument itself is mandatory, all its
    content are optional (i.e. it can be empty).

    .. confval:: environment_setup.pre_job_script: str

        Path to an executable (e.g. bash script) that is executed before the main script
        runs.

    .. confval:: environment_setup.virtual_env_path: str

        Path of folder of virtual environment to activate.

    .. confval:: environment_setup.conda_env_path: str

        Name of conda environment to activate (this option might be broken).

    .. confval:: environment_setup.variables: dict[str]

        Environment variables to set. Variables are set *after* a virtual/conda environment 
        is activated, thus override environment variables set before. They are also set 
        *before* the :confval:`environment_setup.pre_job_script`: this can be useful to pass 
        parameters to the script, e.g. to setup a generic script that changes its behavior based 
        on the values defined in the cluster_utils config file.

    .. confval:: environment_setup.is_python_script: bool = true

        Whether the target to run is a Python script.

    .. confval:: environment_setup.run_as_module: bool = false

        Whether to run the script as a Python module
        (``python -m my_package.my_module``) or as a script
        (``python my_package/my_module.py``).

.. confval:: cluster_requirements

    **Required.**

    Settings for the cluster (number of CPUs, bid, etc.).  See
    :ref:`config_cluster_requirements`.

.. confval:: singularity

    See :ref:`config_singularity`.

.. confval:: fixed_params

    **Required.**

    TODO


.. _config_cluster_requirements:

Cluster Requirements
--------------------

When running on a cluster, you have to specify the resources needed for each job (number
of CPUs/GPUs, memory, etc.).  This is all configured in the section
:confval:`cluster_requirements`.  

.. note:: The cluster requirements are ignored when running on a local machine.

Some of the options are common among all supported cluster systems, some are
system-specific.  Note that all the options are per job, i.e. each job will get the
requested CPUs, memory, ..., it's not shared between jobs.

Simple example (in TOML):

.. code-block:: toml

   [cluster_requirements]
   request_cpus = 1
   request_gpus = 0
   memory_in_mb = 1000
   bid = 1000


Common Options
~~~~~~~~~~~~~~

.. confval:: cluster_requirements.request_cpus: int

    Number of CPUs that is requested.

.. confval:: cluster_requirements.request_gpus: int

    Number of GPUs that is requested.

.. confval:: cluster_requirements.memory_in_mb: int

    Memory (in MB) that is requested.

.. confval:: cluster_requirements.forbidden_hostnames: list[str]

    Cluster nodes to exclude from running jobs. Useful if nodes are malfunctioning.


Condor-specific Options
~~~~~~~~~~~~~~~~~~~~~~~

The following options are only used when running on Condor (i.e. the MPI cluster).

.. confval:: cluster_requirements.bid: int

    The amount of cluster money you are bidding for each job.  See documentation of the
    MPI-IS cluster on how the bidding system works.

.. confval:: cluster_requirements.cuda_requirement

    ``cuda_requirement`` has multiple behaviors. If it is a number, it specifies the
    *minimum* CUDA capability the GPU should have. If the number is prefixed with ``<``
    or ``<=``, it specifies the *maximum* CUDA capability. Otherwise, the value is taken
    as a full requirement string, example (in TOML):

    .. code-block:: toml

       [cluster_requirements]
       # ...
       cuda_requirement = "TARGET.CUDACapability >= 5.0 && TARGET.CUDACapability <= 8.0"
       # ...

    Remember to prefix the constraints with ``TARGET.``. See
    https://atlas.is.localnet/confluence/display/IT/Specific+GPU+needs for the kind
    of constraints that are possible.

.. confval:: cluster_requirements.gpu_memory_mb: int

    Minimum memory size the GPU should have, in megabytes.

.. confval:: cluster_requirements.concurrency_limit

    Limit the number of concurrent jobs. You can assign a resource (tag) to your jobs
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

.. confval:: cluster_requirements.concurrency_limit_tag

    See :confval:`cluster_requirements.concurrency_limit`

.. confval:: cluster_requirements.hostname_list: list[str]

    Cluster nodes to exclusively use for running jobs.

.. confval:: cluster_requirements.extra_submission_options: dict | list | str

    This allows to add additional lines to the `.sub` file used for submitting jobs to
    the cluster. Note that this setting is normally not needed, as cluster_utils
    automatically builds the submission file for you.


.. todo:: Is the list above complete?


Slurm-specific Options
~~~~~~~~~~~~~~~~~~~~~~

.. confval:: cluster_requirements.partition: str

    **Required.**

    Name of the partition to run the jobs on.  See documentation of the corresponding
    cluster on what partitions are available.

    Multiple partitions can be given as a comma-separated string
    (``partition1,partition2``), in this case jobs will be executed on any of them
    (depending on which has free capacity first).

.. confval:: cluster_requirements.request_time: str

    **Required.**

    Time limit for the jobs.  Jobs taking longer than this will be aborted, so make
    sure to request enough time (but don't exaggerate too much as shorter jobs can be
    scheduled more easily).

    From the `Slurm documentation <https://slurm.schedmd.com/sbatch.html>`_:

        Acceptable time formats include "minutes", "minutes:seconds",
        "hours:minutes:seconds", "days-hours", "days-hours:minutes" and
        "days-hours:minutes:seconds".

    So for example to request 1 hour per job use ``request_time = "1:00:00"``.

.. confval:: cluster_requirements.signal_seconds_to_timeout: int

    Time in seconds before timeout at which Slurm sends a USR1 signal to the job (see
    ``--signal`` of ``sbatch``).  If not set, no signal is sent.

    See example :doc:`examples/slurm_timeout_signal`.
.. confval:: cluster_requirements.extra_submission_options: list[str]

    List of additional options for ``sbatch``.  Can be used if a specific
    setting is needed which is not already covered by the options above.
    Expects a list with arguments as they are passed to ``sbatch``, for example:

    .. code-block:: toml

       extra_submission_options = ["--gpu-freq=high", "--begin=2010-01-20T12:34:00"]

.. note::

   There are currently no options to restrict the type of GPU.  On the ML Cloud cluster
   of the University of Tübingen, this is currently done via the *partitions*.  See
   https://portal.mlcloud.uni-tuebingen.de/user-guide/batch for a list of available
   partitions.

   If needed, e.g. when using cluster_utils on a different Slurm cluster, missing
   options can always be provided via ``extra_submission_options``.


.. _config_singularity:

Use Singularity/Apptainer Containers
------------------------------------

Jobs can be executed inside Singularity/Apptainer [#singularity1]_ containers to give
you full control over the environment, installed packages, etc.  To enable
containerisation of jobs, add a section :confval:`singularity` in the config file.  This
section can have the following parameters:


.. confval:: singularity.image

    **Required.**

    Path to the container image.

.. confval:: singularity.executable: str = "singularity"

    Specify the executable that is used to run the container (mostly useful if you want
    to explicitly use Apptainer instead of Singularity in an environment where both are
    installed).

.. confval:: singularity.use_run: bool = false

    Per default the container is run with ``singularity exec``.  Set this to true to use
    ``singularity run`` instead.  This is only useful for images that use a wrapper run
    script that executes the given command (sometimes needed for some environment
    initialisation).

.. confval:: singularity.args: list[str] = []

    List of additional arguments that are passed to ``singularity exec|run``.  Use this
    to set flags like ``--nv``, ``--cleanenv``, ``--contain``, etc. if needed.

Example (in TOML):

.. code-block:: toml

   [singularity]
   image = "my_container.sif"
   args = ["--nv", "--cleanenv"]



Specific for hp_optimization
============================

.. confval:: num_best_jobs_whose_data_is_kept: int

    **Required.**

    Keep copies of the working directories of the given number of best jobs.  They are
    stored in ``{results_dir}/best_jobs/``.

.. confval:: kill_bad_jobs_early: bool = false

    TODO

.. confval:: early_killing_params

    TODO

.. confval:: optimizer_str

    **Required.**

    The optimisation method that is used to find good hyperparameters.
    Supported methods are

    - cem_metaoptimizer
    - nevergrad \*
    - gridsearch

    \* To use nevergrad, the optional dependencies from the "nevergrad" group are
    needed, see :ref:`optional_dependencies`.

.. confval:: optimizer_settings

    **Required.**

    Settings specific to the optimiser selected in :confval:`optimizer_str`. See
    :ref:`config.optimizer_settings`.

.. confval:: optimization_setting

    **Required.**

    General settings for the optimisation (independent of the optimisation method).  See
    :ref:`config.optimization_settings`.

.. confval:: optimized_params

    **Required.**

    Defines the parameters that are optimised over.  Expectes a list
    of dictionaries with each entry having the following elements:

    - ``param``:  Name of the parameter.  Apparently can have
      object/attribute structure, e.g. "fn_args.x".
    - ``distribution``: Distribution that is used for sampling.  Options
      are:

      .. list-table::

         * - TruncatedNormal
           - Normal distribution using floats.
         * - TruncatedLogNormal
           - Log-normal distribution using floats.
         * - IntNormal
           - Normal distribution using integer values.
         * - IntLogNormal
           - Log-normal distribution using integer values.
         * - Discrete
           - Discrete list of values.
    - ``bounds``:  List ``[min_value, max_value]``
    - ``options``:  List of possible values (used instead of bounds for
      "Discrete" distribution).

    Example (in TOML):

    .. code-block:: toml

        [[optimized_params]]
        param = "fn_args.w"
        distribution = "IntNormal"
        bounds = [ -5, 5 ]

        [[optimized_params]]
        param = "fn_args.y"
        distribution = "TruncatedLogNormal"
        bounds = [ 0.01, 100.0 ]

        [[optimized_params]]
        param = "fn_args.sharp_penalty"
        distribution = "Discrete"
        options = [ false, true ]


.. _config.optimization_settings:

General Optimisation Settings
-----------------------------

The :confval:`optimization_setting` parameter defines the general optimisation
settings (i.e. the ones independent of the optimisation method set in
:confval:`optimizer_str`).  A dictionary with the following values is expected:


.. confval:: optimization_setting.metric_to_optimize: str

    **Required.**

    Name of the metric that is used for the optimisation.  Has to match the name of one
    of the metrics that are saved with :func:`~cluster_utils.finalize_job`.

.. confval:: optimization_setting.minimize: bool

    **Required.**

    Specify whether the metric shall be minimized (true) or maximised (false).

.. confval:: optimization_setting.number_of_samples: int

    **Required.**

    The total number of jobs that will be run.

.. confval:: optimization_setting.n_jobs_per_iteration: int

    **Required.**

    The number of jobs submitted to the cluster concurrently, and also the number of
    finished jobs per report iteration.

.. confval:: optimization_setting.n_completed_jobs_before_resubmit: int = 1

    The number of jobs that have to be finished before another
    ``n_completed_jobs_before_resubmit`` jobs are submitted.  Defaults to 1 (i.e. submit
    new job immediately when one finishes).

.. confval:: optimization_setting.run_local: bool

    Specify if the optimisation shall be run locally if the cluster is not detected.  If
    not set, the user will be asked at runtime in this case.


About Iterations
~~~~~~~~~~~~~~~~

The exact meaning of one "iteration" of the hp_optimization mode is a bit
complicated and depends on the configuration.

Relevant are the following parameters from the :confval:`optimization_setting`
section:

- :confval:`optimization_setting.number_of_samples`
- :confval:`optimization_setting.n_jobs_per_iteration`
- :confval:`optimization_setting.n_completed_jobs_before_resubmit`  (default: 1)


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

Optimizer Settings
------------------

``optimizer_settings`` expects as value a dictionary with configuration specific
to the method that is specified in :confval:`optimizer_str`.  Below are the
corresponding parameters for each method.

cem_metaoptimizer
~~~~~~~~~~~~~~~~~

.. confval:: with_restarts: bool

    **Required.**

    Whether a specific set of settings can be run multiple times. This can be useful to
    automatically verify if good runs were just lucky runs because of e.g. the random
    seed, making the found solutions more robust.

    If enabled, new settings are sampled for the first ``num_jobs_in_elite`` jobs.
    After that each new job has a 20% chance to use the same settings as a previous job
    (drawn from the set of best jobs).

.. confval:: num_jobs_in_elite: int

    **Required.**

    TODO


nevergrad
~~~~~~~~~

.. note::

   To use nevergrad, the optional dependencies from the "nevergrad" group are needed,
   see :ref:`optional_dependencies`.

.. confval:: opt_alg

    **Required.**

    TODO


Specific for grid_search
========================

.. confval:: local_run

    TODO

.. confval:: load_existing_results: bool = false

    TODO

.. confval:: restarts

    **Required.**

    How often to run each configuration (useful if there is some randomness in the
    result).

.. confval:: samples

    TODO

.. confval:: hyperparam_list

    **Required.**

    Probably list of parameters over which the grid search is performed.
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

    python3 -m cluster_utils.grid_search config.json 'optimization_procedure_name="foo"'


Nested parameters can be set using dots:

::

    python3 -m cluster_utils.grid_search config.json 'git_params.branch="foo"'



.. [#singularity1] `SingularityCE <https://sylabs.io/singularity/>`_ and `Apptainer
   <https://apptainer.org>`_ are both emerged from the original Singularity project.  So
   far they are still mostly compatible but their features may diverge over time.  So
   you may want to check which one is installed on the cluster you are using, e.g. by
   running ``singularity --version``.


.. _smart_settings: https://github.com/martius-lab/smart-settings
