***************************
Cluster Utils Documentation
***************************


`cluster_utils`_ is a tool for easily running hyperparameter optimization or grid search
on a Slurm or HTCondor [1]_ cluster.  It takes care of submitting and monitoring the
jobs as well as aggregating the results.

It is geared towards tasks typical for *machine learning research*, for example running
multiple seeds, grid searches, and hyperparameter optimization.

cluster_utils is developed by the `Autonomous Learning group`_ at the University of
Tübingen.


Main Features
=============

A non-exhaustive list of features is the following:

- **Parametrized jobs and hyperparameter optimization**: run grid searches or
  multi-stage hyperparameter optimization.
- **Supports several cluster backends**: currently, Slurm_ and HTCondor_ [1]_, as well
  as local (single machine runs) are supported. 
- **Automatic job management**: jobs are submitted, monitored (with error reporting),
  and cleaned up in an automated way.
- **Timeouts & restarting of failed jobs**: jobs can be stopped and resubmitted after
  some time; failed jobs can be (manually) restarted.
- **Integrated with git**: jobs are run from a `git clone` with customizable branch and
  commit number to enhance reproducility.
- **Reporting**: results are summarized in CSV files, and optionally PDF reports with
  basic summaries and plots.


Basic Usage
===========

There are two basic functionalities:

.. code-block:: bash

   python3 -m cluster_utils.grid_search specification_of_grid_search.json

for grid search and

.. code-block:: bash

   python3 -m cluster_utils.hp_optimization specification_of_hp_opt.json

for hyperparameter optimization.

For more information see :doc:`usage` and the examples in the ``examples/basic/`` and
``examples/rosenbrock/`` for simple demonstrations.



.. TABLE OF CONTENTS (all hidden, so they only appear in the navigation bar)

.. toctree::
   :caption: Basics
   :maxdepth: 1
   :hidden:

   installation
   usage


.. toctree::
   :caption: How-to Guides
   :maxdepth: 1
   :hidden:

   report
   troubleshooting
   setup_devel_env
   exit_for_resume.rst
   examples/index.rst


.. toctree::
   :maxdepth: 1
   :caption: Topic Guides
   :hidden:

   usage_mindset_and_rule_of_thumb
   architecture


.. toctree::
   :maxdepth: 1
   :caption: References
   :hidden:

   configuration
   api
   changelog


.. [1] Note that the implementation for HTCondor is tailored specifically for the
   cluster of the Max Planck Institute of Intelligent Systems and may not work as-is on
   other HTCondor clusters.

.. _cluster_utils: https://github.com/martius-lab/cluster_utils
.. _Autonomous Learning group: https://uni-tuebingen.de/fakultaeten/mathematisch-naturwissenschaftliche-fakultaet/fachbereiche/informatik/lehrstuehle/distributed-intelligence
.. _Slurm: https://slurm.schedmd.com/
.. _HTCondor: https://htcondor.org/
