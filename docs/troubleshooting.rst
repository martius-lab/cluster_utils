***************
Troubleshooting
***************

Below is a list of error messages that may occur with potential solutions.

------

**Pandas DataError: No numeric types to aggregate**

If one of the values stored with :func:`~cluster_utils.finalize_job` has a non-numeric
type (e.g. string).


------

**ValueError in sklearn: Input contains NaN/Inf or value too big for float 32**

This happens during creation of the PDF report if there are less than two
successful jobs in an iteration.  May happen, for example, when testing with a
very small number of jobs per iteration and then some of them fail.
