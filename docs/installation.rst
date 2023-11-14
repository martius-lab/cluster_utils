************
Installation
************


Basic Installation
==================

.. code-block:: bash

   pip install git+https://gitlab.tuebingen.mpg.de/mrolinek/cluster_utils.git


.. _optional_dependencies:

Optional Dependencies
=====================

Some features require additional dependencies that are not installed by default.  They
can be installed by specifying the corresponding "optional dependencies group" like
this:

.. code-block:: bash

   pip install "cluster[EXTRA] @ git+https://gitlab.tuebingen.mpg.de/mrolinek/cluster_utils.git"

where ``EXTRA`` should be replaced by one of the following identifiers (or multiple,
separated by commas):


.. list-table::
   :header-rows: 1

   * - Identifier
     - Needed for
   * - **report**
     - For generating PDF reports (see :doc:`report`).
   * - **nevergrad**
     - To use the *nevergrad* optimizer in ``hp_optimization``.
   * - **docs**
     - For building the documentation.
   * - **dev**
     - For development of the package (installs linters and test tools).
   * - **mypy**
     - For development of the package (for type-checking with mypy).
