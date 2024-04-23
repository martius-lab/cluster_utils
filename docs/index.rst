***************************
Cluster Utils Documentation
***************************


`cluster_utils`_ is a tool for easily running hyperparameter optimization or
grid search on a HTCondor or Slurm cluster.  It takes care of submitting and
monitoring the jobs as well as aggregating the results.

Note that the implementation for HTCondor is tailored specifically for the
cluster of the Max Planck Institute of Intelligent Systems.  The Slurm
implementation is more generic but not as feature-complete yet.


Main Features
=============

A non-exhaustive list of features is the following:

- **Automatic Condor/Slurm usage** Jobs are submitted, monitored (with error
  reporting), and cleaned up in an automated and highly customizable way.
- **Integrated with git**. Jobs are run from a ``git clone`` with customizable
  branch and commit number.
- **PDF & CSV reporting** Both grid search and optimization produce a pdf report
  with the specification, basic summaries, and plots.
- **Advanced setting handling** Cluster utils offer a customized settings system
  based on JSON. Pointers within the JSON file and to other JSON files are
  supported.
- **A LOT OF ADDITIONAL SWEETNESS** Most are demonstrated in the examples. Also,
  read the code ;).


Basic Usage
===========

There are two basic functionalities:

.. code-block:: bash

   python3 -m cluster_utils.grid_search specification_of_grid_search.json

and

.. code-block:: bash

   python3 -m cluster_utils.hp_optimization specification_of_hp_opt.json

for hyperparameter optimization

See ``examples/basic`` and ``examples/rosenbrock`` for simple demonstrations.


Documentation Content
=====================

.. If something is changed here, please also update docs/README.md

.. toctree::
   :caption: How-to Guides
   :maxdepth: 1

   installation
   report
   troubleshooting
   setup_devel_env


.. toctree::
   :maxdepth: 1
   :caption: Topic Guides

   usage_mindset_and_rule_of_thumb


.. toctree::
   :maxdepth: 1
   :caption: References

   configuration



.. _cluster_utils: https://github.com/martius-lab/cluster_utils
