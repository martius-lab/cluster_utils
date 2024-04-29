.. _example_slurm_timeout_signal:

**********************************
Get Signal Before Timeout on Slurm
**********************************

Slurm requires jobs to specify a maximum run duration.  Jobs that exceed this
duration will get killed.  This can be a problem in cases where you do not know
the exact run duration of your jobs in advance.  Fortunately, Slurm can be
configured to send a signal to the job a bit before the timeout.  This allows
the job to save a checkpoint with the current results and use cluster_utils'
:func:`~cluster_utils.exit_for_resume` to terminate.  cluster_utils will then
automatically restart the job, allowing it to load the previously saved checkpoint and
resume the computations.


Below is a small example on how to configure cluster_utils such that
timeout-warning signals are send.  Please note that it is still up to you to
catch that signal in your code and react accordingly.  An example on how this
can be done is shown below as well.


**grid_search.toml:**

.. literalinclude:: ../../examples/slurm_timeout_signal/grid_search.toml

The relevant part here is the definition of ``signal_seconds_to_timeout`` in the
``[cluster_requirements]`` section.  When defining it, Slurm will be configured to send a ``USR1`` signal to warn about the approaching timeout.  The value is the approximate time in seconds before the TIMEOUT at which the signal will be sent.  Make sure to choose a value large enough to allow your job to actually save the intermediate data before the timeout is reached.

The main script of the job can then look something like this:

**main.py:**

.. literalinclude:: ../../examples/slurm_timeout_signal/main.py


A signal handler is registered with ``signal.signal(signal.SIGUSR1,
timeout_signal_handler)``.  This means the given function will be called when
the process receives a ``USR1`` signal.  What this function does will then
depend on the actual application.  In the example, it simply sets a flag which
will be checked in each iteration of the dummy training loop.  If set True, a
checkpoint will be saved and the script terminates with
:func:`~cluster_utils.exit_for_resume`.


.. note::

   This example is included in ``cluster_utils/examples/slurm_timeout_signal``
   and can be directly run from there.

.. warning::

   In case you are using a wrapper script around your main.py (can for example be needed
   for some environment setup inside containers), the signal will only be sent to the
   wrapper script and not automatically be forwarded to the main.py process.
   So in this case, you need to catch the signal in the wrapper script as well and sent
   it to the child process from there.
