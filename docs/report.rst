***********************
How to Generate Reports
***********************

A report in PDF format can be generated (either manually or automatically) to give an
overview over the optimisation results.

.. important::

   Generating the report requires optional dependencies from the "report" group.  See
   :ref:`optional_dependencies`.

   Further it requires ``pdflatex`` and a number of LaTeX packages installed,
   which cannot be specified as Python dependencies.  In case those are missing
   on your cluster system, see section :ref:`report_generation_without_pdflatex`.

.. _manual_report_generation:

Manual Report Generation
========================

At the end of each iteration, the relevant statistics are written to files in the output
directory from which the report can be generated with

.. code-block:: bash

   python3 -m cluster_utils.scripts.generate_report <results_directory> <output_file>

Use ``--help`` to get a list of all options.


Automatic Report Generation
===========================

The report can also be generated automatically either in every iteration or only once at
the very end.  See the ``generate_report`` option in :ref:`config.general_settings`.


.. _report_generation_without_pdflatex:

Report Generation on Clusters without LaTeX
===========================================

The report generator uses ``pdflatex`` and requires a number of LaTeX packages
which are used in the report template.  This means that on cluster systems
where those packages are not installed, the report generation will fail.

One workaround is to copy the results directory from the cluster to a
workstation where you can install the required packages and generate the report
manually (see :ref:`manual_report_generation`).  Automatic report generation
should be disabled in this case.

Assuming the cluster provides either Apptainer or Singularity, another option
is to create a container with ``pdflatex`` and all required packages and use
that as drop-in-replacement for the actual ``pdflatex`` executable.
The actual steps for this are:

1. Save the following definition file as ``pdflatex.def``

   .. code-block:: singularity

      bootstrap: docker
      from: ubuntu:22.04

      %post
          set -e
          export DEBIAN_FRONTEND=noninteractive

          echo "deb http://us.archive.ubuntu.com/ubuntu focal universe" >> /etc/apt/sources.list
          apt-get update
          apt-get install -y texlive-latex-base texlive-latex-extra

          # cleanup to reduce container size
          apt-get clean

      %runscript
          pdflatex "$@"

2. Build a container called ``pdflatex`` (without the ``.sif`` extension!):

   .. code-block:: bash

      singularity build pdflatex pdflatex.def
      # or
      apptainer build pdflatex pdflatex.def

3. Copy it to a directory on the cluster, which is listed in the ``PATH`` environment variable.
   When you now call ``pdflatex``, it will run the container.
   Thanks to the runscript defined in the definition file, it will simply forward all arguments to the ``pdflatex`` executable inside the container.
   So it will behave more or less the same as when ``pdflatex`` would be installed directly.

With this, cluster_utils should automatically use the pdflatex-container, thus being
able to generate the report.
