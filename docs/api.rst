*************
API Reference
*************

Job Script API
==============

The following functions may be used in your job scripts that are executed via
cluster_utils.

.. autofunction:: cluster_utils.initialize_job

.. autofunction:: cluster_utils.finalize_job

.. autofunction:: cluster_utils.exit_for_resume

.. autofunction:: cluster_utils.announce_early_results

.. autofunction:: cluster_utils.announce_fraction_finished

.. autofunction:: cluster_utils.cluster_main


Output Filenames
================

The constants listed below define names of output files that are written by
cluster_utils.  They are listed here, so that other parts of the documentation can
reference them.

.. automodule:: cluster_utils.base.constants
   :members:


Deprecated API
==============

The following functions can still be used but are deprecated and may be removed in a
future release.  Do not use them anymore in new code!  Also see the description of the
individual functions on how using code should be updated.

.. autofunction:: cluster_utils.read_params_from_cmdline

.. autofunction:: cluster_utils.save_metrics_params
