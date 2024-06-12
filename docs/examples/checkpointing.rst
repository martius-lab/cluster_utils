.. _example_checkpointing:

********************************************
Use checkpointing with ``exit_for_resume()``
********************************************


This is an example how to use checkpointing and restarting jobs using
:func:`~cluster_utils.exit_for_resume()` when training a neural network with PyTorch.

For more information on :func:`~cluster_utils.exit_for_resume()` see
:ref:`exit_for_resume`.


.. literalinclude:: ../../examples/checkpointing/checkpoint_example.py


The corresponding cluster_utils config file:

.. literalinclude:: ../../examples/checkpointing/grid_search_checkpointing.json


.. note::

   This example is included in ``cluster_utils/examples/checkpointing`` and can be
   directly run from there.
