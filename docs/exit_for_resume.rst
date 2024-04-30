.. _exit_for_resume:

****************************************
Restart jobs using ``exit_for_resume()``
****************************************

When using cluster systems, it can often be beneficial to split long-running jobs into
multiple shorter jobs.  Reasons for this are:

- Jobs with lower time requirements can potentially be scheduled sooner (e.g. on Slurm).
- On some systems the cost for running jobs increases non-linearly over time, so
  multiple short jobs are cheaper than one long one.
- On systems where one needs to specify time limits (e.g. Slurm), restarting can be used
  to avoid timeouts if the duration needed for the job is not known in advance.
- Stopping from time to time gives other users a chance to start their jobs in between,
  so it's more friendly to your colleagues.


cluster_utils supports this via the function :func:`~cluster_utils.exit_for_resume`.
Calling it will send a resume-request to the cluster_utils main process and then
terminate the job.  The main process will then re-submit the job with the same settings
and same output directory.  This allows the job to load previously saved intermediate
results and proceed working on them.


So the high level structure of a job script using
:func:`~cluster_utils.exit_for_resume` looks like this:

1. In the beginning of your script check if there are intermediate results saved in the
   output directory by a previous job.  If yes, load them.
2. Start/proceed your computations.
3. Based on some criterion (e.g. after a certain number of iterations or when receiving
   a timeout-signal by Slurm) save current results to the output directory and terminate
   the job by calling :func:`~cluster_utils.exit_for_resume`.


.. hint::

   It may be useful to report intermediate results using
   :func:`~cluster_utils.announce_early_results` before exiting for resume.


Usage Examples
==============

- :ref:`example_checkpointing`
- :ref:`example_slurm_timeout_signal` (combines restarting with Slurm's timeout signal)
