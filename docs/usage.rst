*****
Usage
*****

Run Batch of Jobs
=================

cluster_utils provides two main commands to run batches of jobs on the cluster:

- ``grid_search``:  Simple grid search over specified parameter ranges.
- ``hp_optimization``:  Uses sampling-based optimization to search for best combination
  of hyperparameters within the specified ranges.

They are both run as modules via ``python -m`` and expect a configuration file as
argument:

.. code-block:: bash

   python3 -m cluster_utils.grid_search config_for_grid_search.json

   python3 -m cluster_utils.hp_optimization config_for_hp_optim.json

See :doc:`configuration` for information on the expected structure of the config file
(note that there are differences between the two methods!).

Optionally, a list of key-value arguments can be provided in addition, to overwrite
single settings from the config file.  Use dot-notation to specify nested keys.  Example:

.. code-block:: bash

   python3 -m cluster_utils.hp_optimization config.json \
     'results_dir="/tmp"' 'optimization_setting.run_local=True'

Both commands can also be run with ``--help`` to get a complete list of arguments.

You can abort cluster_utils with Ctrl + C at any time. All running jobs are stopped, and
submitted jobs are removed from the cluster queue.


Interactive Mode
================

While cluster_utils is running, it is possible to enter a command prompt which allows to
get some information about finished and running jobs, as well as to stop running jobs.

To enter the command prompt, press ESC.  You should now see the following prompt:

::

   Enter command, e.g.  list_jobs, list_running_jobs, list_successful_jobs,
   list_idle_jobs, show_job, stop_remaining_jobs
   >>>

You now may enter one of the listed commands or simply press Enter to leave the prompt
without executing a command.

.. important::

   While the prompt is open, the main loop is blocked, i.e. no new jobs will be
   submitted during that time.


Commands
--------

.. I'm a bit misusing the confval directive here, but I think as long as there is no
   name collision with an actual config value, this should be fine and much easier than
   adding a dedicated directive.

.. confval:: list_jobs

   List IDs of all jobs that have been submitted so far (including finished ones).

.. confval:: list_running_jobs

   List IDs of all jobs that are currently running.

.. confval:: list_successful_jobs

   List IDs of all jobs that finished successfully.

.. confval:: list_idle_jobs

   List IDs of all jobs that have been submitted but not yet started.

.. confval:: show_job

   Will ask for a job ID and show information about this job.

.. confval:: stop_remaining_jobs

   Abort all currently running jobs as well as jobs that already have been submitted but
   didn't start yet.

   This will not stop submission of new jobs.  If you want to stop cluster_utils
   completely, press Ctrl + C instead.


