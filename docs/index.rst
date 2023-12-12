*****************************************
Welcome to cluster_utils's documentation!
*****************************************


`cluster_utils`_ has been powering my cluster runs since 2017. It has grown ever
since and now it is a proper monster. Enjoy :).


Content
=======

.. toctree::
   :caption: How-to Guides
   :maxdepth: 1

   installation
   report
   troubleshooting


.. toctree::
   :maxdepth: 1
   :caption: References

   configuration
   changelog


.. todo:: Add more in-depth explanations

.. todo:: Add a basic getting-started tutorial



Basic Usage
===========

There are two basic functionalities:

.. code-block:: bash

   python3 -m cluster.grid_search specification_of_grid_search.json

and

.. code-block:: bash

   python3 -m cluster.hp_optimization specification_of_hp_opt.json

for hyperparameter optimization

See ``examples/basic`` and ``examples/rosenbrock`` for simple demonstrations.


Main features
=============

A non-exhaustive list of features is the following:

- **Automatic condor usage** Jobs are submitted, monitored (with error
  reporting), and cleaned up in an automated and highly customizable way.
- **Integrated with git**. Jobs are run from a `git clone` with customizable
  branch and commit number.
- **PDF&CSV reporting** Both grid search and optimization produce a pdf report
  with the specification, basic summaries, and plots.
- **Advanced setting handling** Cluster utils offer a customized settings system
  based on JSON. Pointers within the JSON file and to other JSON files are
  supported.
- **A LOT OF ADDITIONAL SWEETNESS** Most are demonstrated in the examples. Also,
  read the code ;).


Usage Mindset and Rules of Thumb
================================

Generally, the usage mindset should be *"obtain some interpretable understanding
of the influence of the hyperparameters"* rather than *"blackbox optimizer just
tells me the best setting"*.  Usually, early in the project many of the
hyperparameters are more like ideas, or strategies.  Cluster utils can then tell
you which ideas (or their combinations) make sense.  Later in a project, there
only tend to be actual hyperparameters (i.e. transferring a working architecture
to a new dataset), which can then be fit to this specific setting using cluster
utils.

Here are some rules of thumbs to set the configuration values that can help you
to get started. Keep in mind that following these does not necessarily lead to
optimal results on your specific problem.

**Which optimizer should I use for optimizing hyperparameters of neural networks
(depth, width, learning rate, etc.)?**

``cem_metaoptimizer`` is a good default recommendation for this case.

**How many jobs should I run? How many concurrently?**

It depends. The number of concurrent jobs (``n_jobs_per_iteration``) should be
as high as achievable with the current load on the cluster.  For CPU jobs, this
could be 100 concurrent jobs; for GPU jobs, maybe around 40.  The total number
of jobs (``number_of_samples``) can be lower if you only want to get an initial
impression of the behaviour of the hyperparameter; in this case, 3-5 times the
number of jobs per iteration is a good number.  If you want to get a more
precise result, or if you have a high number of hyperparameters, up to 10 times
the number of jobs per iteration can be used.

**How many hyperparameters can I optimize over at the same time?**

This depends on the number of jobs and number of parallely running jobs. For
5x100 jobs, 5-6 hyperparameters are okay to be optimized. For 5x40 jobs, 3-4 are
okay. For a larger scale, e.g. 10x200 jobs, it might be reasonable to optimize
up to 10 hyperparameters at the same time.

**How to deal with overfitting?**

You can keep the best validation error achieved over the epochs and report this
instead of the error achieved in the last epoch.


Development
===========

Setting Up a Development Environment
------------------------------------

1. Create a development environment (e.g. using virtualenv)::

       python3 -m virtualenv .venv
       source .venv/bin/activate

2. Install ``cluster_utils`` in editable mode::

       pip install -e ".[dev]"

3. Register the pre-commit hooks::

       pre-commit install


Running Tests
-------------

cluster_utils currently only has simple tests that just run some of the
examples. You can run the tests using ``nox -s tests``. This will setup
a new virtual environment, install cluster_utils and its dependencies,
and run the tests. As this is quite a slow process, you can reuse the
virtual environment after you set it up once, using the ``-r`` flag:
``nox -r -s tests``.

Any merge request to master has to pass the continuous integration
pipeline, which basically runs ``nox``. In order to make sure continuous
integration passes, you can thus run this command locally.

Workflow with pre-commit
------------------------

When you commit, pre-commit will run some checks on the files you are
changing. If one of them fails a check, the commit will be aborted. In
this case, you should fix and git add the file again, then repeat the
commit. pre-commit also runs some automatic formatting on the files
(using black). When files are changed this way, you can inspect the
changes using git diff, and when everything is okay, run git add to
accept the formatted files.

You can also run the pre-commit checks manually on all files in the
repository using ``pre-commit run -a``. In fact, this is useful to make
sure a commit runs through without any checks failing.


.. _cluster_utils: https://gitlab.tuebingen.mpg.de/mrolinek/cluster_utils
