***************************************
How to set up a Development Environment
***************************************

Setting Up a Development Environment
====================================

1. Create a development environment (e.g. using virtualenv)::

       python3 -m virtualenv .venv
       source .venv/bin/activate

2. Install ``cluster_utils`` in editable mode::

       pip install -e ".[dev]"

3. Register the pre-commit hooks::

       pre-commit install


Running Linters and Tests
=========================

We use nox to run various linters and tests.  You can simply call

.. code-block:: sh

   nox

in the root directory of the package to run everything.  However, you will
usually want to restrict a bit what is run.

Any merge request to master has to pass the continuous integration pipeline, which
basically runs ``nox``.
In order to make sure continuous integration passes, you can thus run this command
locally.

Python Versions
---------------

nox is configured to test with different Python versions.  You can limit it to a
specific version (e.g. because you only have that one installed locally) with
the ``-p`` option.  For example to run only with Python 3.10:

.. code-block:: sh

    nox -p "3.10"

Reuse Environment
-----------------

By default nox creates a fresh virtual environment every time you run it.  As this is
quite a slow process, you can reuse the virtual environment after you set it up once,
using the ``-r`` flag.  Example:

.. code-block:: sh

    nox -p "3.10" -r

Run Only Specific Checks
------------------------

You can restrict which checks (called "sessions") are run with `-s`.  For
example to run only the mypy check:

.. code-block:: sh

    nox -s mypy

You can get a list of all available sessions with

.. code-block:: sh

    nox --list

As an alternative to listing specific sessions, you can also run a group of related
sessions using tags with ``-t``.  Currently available tags are:

- **lint**:  All linter checks.
- **test**:  All tests (unit tests and integration tests)

Example: To run all linters with Python 3.10, reusing the environment:

.. code-block:: sh

    nox -p "3.10" -r -t lint



Workflow with pre-commit
========================

When you commit, pre-commit will run some checks on the files you are changing.
If one of them fails a check, the commit will be aborted. In this case, you
should fix and git add the file again, then repeat the commit. pre-commit also
runs some automatic formatting on the files (using black). When files are
changed this way, you can inspect the changes using git diff, and when
everything is okay, run git add to accept the formatted files.

You can also run the pre-commit checks manually on all files in the repository
using 

.. code-block:: sh

    pre-commit run -a

In fact, this is useful to make sure a commit runs through without any checks
failing.


