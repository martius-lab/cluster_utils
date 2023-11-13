*****************
Report Generation
*****************

A report in PDF format can be generated to give an overview over the optimisation
results.

.. important::

   Generating the report requires optional dependencies from the "report" group.  See
   :ref:`optional_dependencies`.

.. _manual_report_generation:

Manual Report Generation
========================

At the end of each iteration, the relevant statistics are written to files in the output
directory from which the report can be generated with

.. code-block:: bash

   python3 -m cluster.scripts.generate_report <results_directory> <output_file>

Use ``--help`` to get a list of all options.


Automatic Report Generation
===========================

The report can also be generated automatically either in every iteration or only once at
the very end.  See the ``generate_report`` option in :ref:`config.general_settings`.


.. note::

   To enable pdf reporting add this line to your .bashrc (.zshrc) on the cluster

   .. code-block:: bash

      export MPLBACKEND="agg"
