************
Installation
************

Requirements
============

cluster_utils requires Python version >= 3.8.

.. _basic_installation:

Basic Installation
==================

**Important:** cluster_utils by default only installs the dependencies that are needed
for the job scripts.  This is to avoid unnecessary dependencies in your user code
(assuming you are using a separate virtual environment for it).
**To be able to run the cluster_utils applications, you need to install it with the
optional "runner" dependencies:**

.. code-block:: bash

   pip install "cluster_utils[runner]"


.. _optional_dependencies:

Optional Dependencies
=====================

Some features require additional dependencies that are not installed by default.  They
can be installed by specifying the corresponding "optional dependencies group".  Keep in
mind that you should always also include the "runner" group:

.. code-block:: bash

   pip install "cluster_utils[runner,EXTRA]"

where ``EXTRA`` should be replaced by one of the following identifiers (or multiple,
separated by commas):


.. list-table::
   :header-rows: 1

   * - Identifier
     - Needed for
   * - **runner**
     - Basic dependencies for running cluster_utils applications (see
       :ref:`basic_installation`).
   * - **report**
     - For generating PDF reports (see :doc:`report`).
   * - **nevergrad**
     - To use the *nevergrad* optimizer in ``hp_optimization``.
   * - **all**
     - Alias for 'runner,report,nevergrad'.
   * - **docs**
     - For building the documentation.
   * - **dev**
     - For development of the package (installs linters and test tools).
   * - **mypy**
     - For development of the package (for type-checking with mypy).
